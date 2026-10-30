"""News ingestion, deduplication, story grouping, and evidence retrieval.

Sources are explicitly configured by the operator. We respect feed terms, send
a descriptive User-Agent, and never bypass authentication or paywalls. All
ingested content is treated strictly as untrusted data.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.logging import get_logger
from app.models import Article, IngestionSource, SourceType, Story, utcnow
from app.services.claims import EvidenceItem, _tokenize, determine_stance

logger = get_logger("sentinel.news")

STORY_SIMILARITY_THRESHOLD = 0.18
STORY_WINDOW_HOURS = 72


# --------------------------------------------------------------------------- #
# Normalization & dedup
# --------------------------------------------------------------------------- #
def normalize_title(title: str) -> str:
    t = re.sub(r"\s+", " ", (title or "").lower()).strip()
    t = re.sub(r"[^a-z0-9 ]", "", t)
    return t


_TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "igshid", "ref", "ref_src"}


def canonical_url(url: str) -> str:
    """Normalize a URL for robust deduplication.

    Lowercases scheme/host, drops tracking query params (utm_*, fbclid, …),
    sorts remaining params, trims a trailing slash, and removes the fragment.
    """
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    url = (url or "").strip()
    if not url:
        return url
    parts = urlsplit(url)
    kept = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not (k.lower().startswith("utm_") or k.lower() in _TRACKING_PARAMS)
    ]
    kept.sort()
    path = parts.path.rstrip("/") or parts.path
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, urlencode(kept), "")
    )


def content_hash(title: str, url: str) -> str:
    key = f"{normalize_title(title)}|{canonical_url(url)}"
    return hashlib.sha256(key.encode()).hexdigest()


# --------------------------------------------------------------------------- #
# RSS parsing
# --------------------------------------------------------------------------- #
def parse_feed(raw_bytes: bytes | str) -> list[dict]:
    """Parse an RSS/Atom feed body into normalized article dicts.

    Separated from fetching so tests can feed fixture bytes without network.
    """
    import feedparser  # lazy import

    parsed = feedparser.parse(raw_bytes)
    out: list[dict] = []
    for entry in parsed.entries:
        title = getattr(entry, "title", None)
        link = getattr(entry, "link", None)
        if not title or not link:
            continue
        published = None
        if getattr(entry, "published_parsed", None):
            try:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                published = None
        summary = getattr(entry, "summary", None)
        if summary:
            # Strip HTML tags from summaries defensively.
            summary = re.sub(r"<[^>]+>", " ", summary)
            summary = re.sub(r"\s+", " ", summary).strip()[: settings.max_article_length_chars]
        publisher = None
        if getattr(parsed, "feed", None):
            publisher = getattr(parsed.feed, "title", None)
        out.append({
            "headline": title.strip()[:512],
            "url": link.strip(),
            "published_at": published,
            "summary": summary,
            "publisher": publisher,
            "language": getattr(parsed.feed, "language", None) if getattr(parsed, "feed", None) else None,
        })
    return out


def fetch_feed_bytes(url: str) -> bytes:
    """Fetch a feed over HTTP with a descriptive UA and timeout."""
    import httpx

    headers = {"User-Agent": settings.http_user_agent}
    with httpx.Client(timeout=settings.http_timeout_seconds, follow_redirects=True) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.content


# --------------------------------------------------------------------------- #
# Story grouping
# --------------------------------------------------------------------------- #
def _article_tokens(article: Article) -> set[str]:
    return _tokenize(f"{article.headline} {article.summary or ''}")


def assign_story(db: Session, article: Article) -> Story:
    """Group an article into an existing story or create a new one.

    Uses token Jaccard similarity against representative articles of recent
    stories. Source diversity (distinct publishers) is tracked, so duplicated
    syndicated content does not masquerade as independent corroboration.
    """
    since = utcnow() - timedelta(hours=STORY_WINDOW_HOURS)
    recent_stories = db.scalars(
        select(Story).where(Story.last_updated >= since).order_by(Story.last_updated.desc())
    ).all()

    art_tokens = _article_tokens(article)
    best_story: Story | None = None
    best_sim = 0.0
    for story in recent_stories:
        rep = db.scalar(
            select(Article).where(Article.story_id == story.id).limit(1)
        )
        if rep is None:
            continue
        sim = _jaccard(art_tokens, _article_tokens(rep))
        if sim > best_sim:
            best_sim = sim
            best_story = story

    if best_story is not None and best_sim >= STORY_SIMILARITY_THRESHOLD:
        story = best_story
    else:
        story = Story(
            title=article.headline[:512],
            topic=article.topic,
            first_seen=utcnow(),
        )
        db.add(story)
        db.flush()

    article.story_id = story.id
    db.flush()
    _recompute_story_stats(db, story)
    return story


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _recompute_story_stats(db: Session, story: Story) -> None:
    arts = db.scalars(select(Article).where(Article.story_id == story.id)).all()
    story.article_count = len(arts)
    story.source_diversity = len({a.publisher for a in arts if a.publisher})
    story.last_updated = utcnow()
    db.flush()


# --------------------------------------------------------------------------- #
# Ingestion orchestration
# --------------------------------------------------------------------------- #
def ingest_articles(
    db: Session,
    source: IngestionSource,
    articles: Iterable[dict],
    *,
    is_demo: bool = False,
) -> dict:
    """Persist articles with dedup + story grouping. Returns a summary."""
    new_count = 0
    dup_count = 0
    for a in articles:
        chash = content_hash(a["headline"], a["url"])
        exists = db.scalar(select(Article).where(Article.content_hash == chash))
        if exists is not None:
            dup_count += 1
            continue
        topic = classify_topic(f"{a['headline']} {a.get('summary') or ''}")
        article = Article(
            source_id=source.id,
            headline=a["headline"][:512],
            url=canonical_url(a["url"])[:1024],
            publisher=(a.get("publisher") or source.name)[:256] if (a.get("publisher") or source.name) else None,
            published_at=a.get("published_at"),
            language=a.get("language"),
            summary=a.get("summary"),
            content=a.get("content"),
            topic=topic,
            content_hash=chash,
        )
        db.add(article)
        db.flush()
        assign_story(db, article)
        new_count += 1
    source.last_ingested_at = utcnow()
    source.last_status = "ok"
    source.last_error = None
    db.commit()
    return {"new": new_count, "duplicates": dup_count, "source": source.name}


TOPIC_KEYWORDS = {
    "politics": ["election", "government", "senate", "parliament", "president", "policy", "vote"],
    "health": ["health", "disease", "vaccine", "covid", "hospital", "diet", "cancer", "medical"],
    "technology": ["ai", "technology", "software", "chip", "cyber", "startup", "app", "data"],
    "business": ["market", "economy", "stocks", "inflation", "company", "trade", "revenue"],
    "science": ["study", "research", "climate", "space", "scientists", "experiment"],
    "world": ["war", "conflict", "treaty", "border", "united nations", "diplomatic"],
    "sports": ["match", "tournament", "championship", "league", "player", "olympic"],
}


def classify_topic(text: str) -> str:
    tokens = _tokenize(text)
    best_topic = "general"
    best_hits = 0
    for topic, kws in TOPIC_KEYWORDS.items():
        hits = sum(1 for k in kws if k in tokens or k in text.lower())
        if hits > best_hits:
            best_hits = hits
            best_topic = topic
    return best_topic


# --------------------------------------------------------------------------- #
# Evidence retrieval
# --------------------------------------------------------------------------- #
def retrieve_local_evidence(
    db: Session, claim_text: str, *, exclude_article_id: int | None = None, limit: int = 8
) -> list[EvidenceItem]:
    """Retrieve evidence from the local article corpus via token overlap.

    Distinct publishers only count once per stance via upstream handling; here
    we return the most relevant distinct articles.
    """
    claim_tokens = _tokenize(claim_text)
    if not claim_tokens:
        return []
    # Pull a bounded recent window to score in Python (fine for typical sizes).
    arts = db.scalars(
        select(Article).order_by(Article.ingested_at.desc()).limit(500)
    ).all()
    scored: list[tuple[float, Article]] = []
    for art in arts:
        if exclude_article_id and art.id == exclude_article_id:
            continue
        text = f"{art.headline} {art.summary or ''}"
        sim = _jaccard(claim_tokens, _tokenize(text))
        if sim >= 0.1:
            scored.append((sim, art))
    scored.sort(key=lambda x: x[0], reverse=True)

    seen_publishers: set[str] = set()
    out: list[EvidenceItem] = []
    for sim, art in scored:
        pub = art.publisher or "unknown"
        # Count each publisher once to avoid syndication inflation.
        if pub in seen_publishers:
            continue
        seen_publishers.add(pub)
        text = f"{art.headline} {art.summary or ''}"
        stance = determine_stance(claim_text, text)
        out.append(EvidenceItem(
            url=art.url,
            title=art.headline,
            publisher=art.publisher,
            snippet=(art.summary or art.headline)[:300],
            stance=stance,
            relevance=round(sim, 4),
            provider="local_corpus",
            evidence_timestamp=art.published_at or art.ingested_at,
        ))
        if len(out) >= limit:
            break
    return out


def retrieve_factcheck_evidence(claim_text: str) -> list[EvidenceItem]:
    """Query Google Fact Check Tools API if a key is configured.

    Returns [] when no key is set. Never fabricates results; on error returns
    an empty list and logs the failure.
    """
    if not settings.google_factcheck_api_key:
        return []
    import httpx

    url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
    params = {"query": claim_text[:200], "key": settings.google_factcheck_api_key}
    try:
        with httpx.Client(timeout=settings.http_timeout_seconds) as client:
            resp = client.get(url, params=params, headers={"User-Agent": settings.http_user_agent})
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("FactCheck API error", extra={"extra_fields": {"error": str(exc)}})
        return []

    out: list[EvidenceItem] = []
    for claim in data.get("claims", [])[:8]:
        for review in claim.get("claimReview", [])[:2]:
            rating = (review.get("textualRating") or "").lower()
            stance = "context"
            if any(w in rating for w in ["false", "pants on fire", "misleading", "incorrect"]):
                stance = "contradict"
            elif any(w in rating for w in ["true", "correct", "accurate"]):
                stance = "support"
            ts = None
            if review.get("reviewDate"):
                try:
                    ts = datetime.fromisoformat(review["reviewDate"].replace("Z", "+00:00"))
                except ValueError:
                    ts = None
            out.append(EvidenceItem(
                url=review.get("url", ""),
                title=review.get("title") or claim.get("text"),
                publisher=(review.get("publisher") or {}).get("name"),
                snippet=f"Rating: {review.get('textualRating', 'n/a')}",
                stance=stance,
                relevance=0.9,
                provider="google_factcheck",
                evidence_timestamp=ts,
            ))
    return out
