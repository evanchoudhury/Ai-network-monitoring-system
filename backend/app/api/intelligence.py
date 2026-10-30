"""News, claim verification, and spam analysis endpoints."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.ratelimit import rate_limit
from app.core.security import require_admin
from app.database import get_db
from app.models import (
    Article,
    Claim,
    ClaimAssessment,
    ClaimLabel,
    Evidence,
    IngestionSource,
    SourceType,
    SpamAssessment,
    Story,
    User,
    utcnow,
)
from app.schemas.schemas import (
    ClaimAnalyzeIn,
    ClaimReviewIn,
    SpamAnalyzeIn,
    SpamResultOut,
)
from app.services import news as news_svc
from app.services import pipeline
from app.services import spam as spam_mod

router = APIRouter(tags=["intelligence"])


# --------------------------- News ----------------------------------------- #
@router.get("/news/articles")
def list_articles(
    topic: str | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Article).order_by(Article.ingested_at.desc())
    if topic:
        stmt = stmt.where(Article.topic == topic)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Article.headline.ilike(like))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.limit(limit).offset(offset)).all()
    return {
        "total": int(total or 0),
        "items": [_article_dict(a) for a in rows],
    }


def _article_dict(a: Article) -> dict:
    return {
        "id": a.id, "headline": a.headline, "publisher": a.publisher,
        "url": a.url, "topic": a.topic, "language": a.language,
        "summary": a.summary, "story_id": a.story_id,
        "published_at": a.published_at.isoformat() if a.published_at else None,
        "ingested_at": a.ingested_at.isoformat(),
    }


@router.get("/news/stories")
def list_stories(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Story).order_by(Story.last_updated.desc()).limit(limit)
    ).all()
    return [
        {
            "id": s.id, "title": s.title, "topic": s.topic,
            "article_count": s.article_count,
            "source_diversity": s.source_diversity,
            "first_seen": s.first_seen.isoformat(),
            "last_updated": s.last_updated.isoformat(),
        }
        for s in rows
    ]


@router.get("/news/stories/{story_id}")
def get_story(story_id: int, db: Session = Depends(get_db)):
    s = db.get(Story, story_id)
    if not s:
        raise HTTPException(status_code=404, detail="Story not found")
    arts = db.scalars(select(Article).where(Article.story_id == story_id)).all()
    return {
        "id": s.id, "title": s.title, "topic": s.topic,
        "article_count": s.article_count, "source_diversity": s.source_diversity,
        "articles": [_article_dict(a) for a in arts],
        "note": "source_diversity counts DISTINCT publishers; syndicated "
                "duplicates do not count as independent corroboration.",
    }


@router.post("/news/ingest")
def ingest_all_sources(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Fetch all enabled RSS sources now. Reports per-source outcomes honestly;
    a failing source records its error and does not fabricate data."""
    sources = db.scalars(
        select(IngestionSource).where(
            IngestionSource.enabled.is_(True),
            IngestionSource.source_type.in_([SourceType.rss, SourceType.newsapi]),
        )
    ).all()
    results = []
    for src in sources:
        if not src.authorized:
            continue
        try:
            summary = news_svc.ingest_source(db, src)
            results.append({"source": src.name, "status": "ok", **summary})
        except Exception as exc:  # noqa: BLE001
            src.last_status = "error"
            src.last_error = str(exc)[:500]
            src.last_ingested_at = utcnow()
            db.commit()
            results.append({"source": src.name, "status": "error", "error": str(exc)[:200]})
    return {"sources_processed": len(results), "results": results}


@router.post("/news/analyze-recent")
def analyze_recent(
    limit: int = Query(20, ge=1, le=100),
    use_factcheck: bool = Query(True),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    count = pipeline.analyze_recent_articles(db, limit=limit, use_factcheck=use_factcheck)
    return {"claims_created": count}


# --------------------------- Claims --------------------------------------- #
def _claim_dict(db: Session, c: Claim, with_evidence: bool = False) -> dict:
    latest = db.scalar(
        select(ClaimAssessment).where(ClaimAssessment.claim_id == c.id)
        .order_by(ClaimAssessment.created_at.desc()).limit(1)
    )
    out = {
        "id": c.id, "article_id": c.article_id, "text": c.text,
        "entities": c.entities, "status": c.status.value,
        "needs_review": c.needs_review, "created_at": c.created_at.isoformat(),
        "assessment": None,
    }
    if latest:
        out["assessment"] = {
            "label": latest.label.value, "explanation": latest.explanation,
            "limitations": latest.limitations,
            "supporting_count": latest.supporting_count,
            "contradicting_count": latest.contradicting_count,
            "model_version": latest.model_version,
            "reviewed_by": latest.reviewed_by,
            "created_at": latest.created_at.isoformat(),
        }
    if with_evidence:
        evs = db.scalars(select(Evidence).where(Evidence.claim_id == c.id)).all()
        out["evidence"] = [
            {
                "url": e.url, "title": e.title, "publisher": e.publisher,
                "snippet": e.snippet, "stance": e.stance, "relevance": e.relevance,
                "provider": e.provider,
                "evidence_timestamp": e.evidence_timestamp.isoformat() if e.evidence_timestamp else None,
                "retrieved_at": e.retrieved_at.isoformat(),
            }
            for e in evs
        ]
    return out


@router.get("/claims")
def list_claims(
    status: str | None = Query(None),
    needs_review: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Claim).order_by(Claim.created_at.desc())
    if status:
        try:
            stmt = stmt.where(Claim.status == ClaimLabel(status))
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid status label")
    if needs_review is not None:
        stmt = stmt.where(Claim.needs_review.is_(needs_review))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.limit(limit).offset(offset)).all()
    return {"total": int(total or 0), "items": [_claim_dict(db, c) for c in rows]}


@router.get("/claims/{claim_id}")
def get_claim(claim_id: int, db: Session = Depends(get_db)):
    c = db.get(Claim, claim_id)
    if not c:
        raise HTTPException(status_code=404, detail="Claim not found")
    return _claim_dict(db, c, with_evidence=True)


@router.post("/claims/analyze", dependencies=[Depends(rate_limit)])
def analyze_text(payload: ClaimAnalyzeIn, db: Session = Depends(get_db)):
    """Ad-hoc claim analysis on arbitrary text (rate-limited, public).

    Creates a transient article record so evidence retrieval + assessment run
    through the same honest pipeline. Content is treated strictly as data.
    """
    from app.services.news import content_hash

    text = payload.text.strip()
    chash = content_hash(text[:120], f"adhoc://{hash(text) & 0xffffffff}")
    existing = db.scalar(select(Article).where(Article.content_hash == chash))
    if existing is None:
        art = Article(
            headline=text[:200], summary=text[:1000], publisher="ad-hoc-submission",
            url=f"adhoc://{chash[:12]}", content=text, content_hash=chash,
            topic=news_svc.classify_topic(text), language="en",
        )
        db.add(art)
        db.flush()
        news_svc.assign_story(db, art)
        db.commit()
    else:
        art = existing
    created = pipeline.analyze_article(db, art, use_factcheck=payload.use_factcheck)
    return {
        "article_id": art.id,
        "claims": [_claim_dict(db, c, with_evidence=True) for c in created],
        "note": "Assessment reflects only configured evidence sources and is "
                "not a determination of absolute truth.",
    }


@router.post("/claims/{claim_id}/review")
def review_claim(
    claim_id: int,
    payload: ClaimReviewIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    c = db.get(Claim, claim_id)
    if not c:
        raise HTTPException(status_code=404, detail="Claim not found")
    label = ClaimLabel(payload.label)
    db.add(ClaimAssessment(
        claim_id=c.id, label=label, explanation=payload.explanation,
        limitations="Human-reviewed assessment.",
        supporting_count=0, contradicting_count=0,
        model_version="human-review", reviewed_by=payload.reviewer or user.username,
    ))
    c.status = label
    c.needs_review = False
    db.commit()
    return _claim_dict(db, c, with_evidence=True)


# --------------------------- Spam ----------------------------------------- #
@router.post("/spam/analyze", response_model=SpamResultOut, dependencies=[Depends(rate_limit)])
def analyze_spam(payload: SpamAnalyzeIn, db: Session = Depends(get_db)):
    result = spam_mod.analyze_message(payload.message, source=payload.source)
    if payload.store:
        db.add(SpamAssessment(
            content_hash=result.content_hash, preview=result.preview,
            category=result.category, score=result.score,
            score_is_calibrated=result.score_is_calibrated,
            indicators=result.indicators, urls=result.urls,
            explanation=result.explanation, recommendation=result.recommendation,
            model_version=result.model_version, source=payload.source,
        ))
        db.commit()
    return SpamResultOut(**{k: getattr(result, k) for k in SpamResultOut.model_fields})


@router.get("/spam")
def list_spam(
    category: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(SpamAssessment).order_by(SpamAssessment.created_at.desc())
    if category:
        stmt = stmt.where(SpamAssessment.category == category)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.limit(limit).offset(offset)).all()
    return {
        "total": int(total or 0),
        "items": [
            {
                "id": s.id, "created_at": s.created_at.isoformat(),
                "category": s.category.value, "score": s.score,
                "score_is_calibrated": s.score_is_calibrated,
                "preview": s.preview, "indicators": s.indicators, "urls": s.urls,
                "explanation": s.explanation, "recommendation": s.recommendation,
                "source": s.source, "model_version": s.model_version,
            }
            for s in rows
        ],
    }
