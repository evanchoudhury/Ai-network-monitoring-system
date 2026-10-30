"""News ingestion, deduplication, and story-grouping tests (fixture RSS)."""
from __future__ import annotations

from app.models import IngestionSource, SourceType
from app.services import news as news_svc

RSS_FIXTURE = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Fixture Feed</title><language>en</language>
  <item>
    <title>City approves new transit budget of 20 million dollars</title>
    <link>https://example.com/transit-budget?utm_source=rss</link>
    <description>The city council approved a 20 million dollar transit budget.</description>
    <pubDate>Tue, 28 Oct 2026 10:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Local team wins championship final</title>
    <link>https://example.com/championship</link>
    <description>The local team won the championship final on Sunday.</description>
    <pubDate>Tue, 28 Oct 2026 11:00:00 GMT</pubDate>
  </item>
</channel></rss>"""


def _source(db):
    s = IngestionSource(name="Fixture Feed", source_type=SourceType.rss,
                        url="https://example.com/rss", enabled=True, authorized=True)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def test_parse_feed_extracts_fields():
    arts = news_svc.parse_feed(RSS_FIXTURE)
    assert len(arts) == 2
    first = arts[0]
    assert "transit budget" in first["headline"]
    assert first["url"].startswith("https://example.com")
    assert first["published_at"] is not None


def test_ingest_and_dedup(db):
    src = _source(db)
    arts = news_svc.parse_feed(RSS_FIXTURE)
    r1 = news_svc.ingest_articles(db, src, arts)
    assert r1["new"] == 2 and r1["duplicates"] == 0
    # Re-ingesting the same feed yields only duplicates (content-hash dedup).
    r2 = news_svc.ingest_articles(db, src, news_svc.parse_feed(RSS_FIXTURE))
    assert r2["new"] == 0 and r2["duplicates"] == 2


def test_tracking_params_normalized_for_dedup(db):
    src = _source(db)
    a = {"headline": "Same headline here", "url": "https://x.com/a?utm_source=t&id=1",
         "summary": "s", "publisher": "P1"}
    b = {"headline": "Same headline here", "url": "https://x.com/a?id=1&fbclid=z",
         "summary": "s", "publisher": "P2"}
    news_svc.ingest_articles(db, src, [a])
    r = news_svc.ingest_articles(db, src, [b])
    assert r["duplicates"] == 1  # treated as the same article


def test_story_grouping_and_source_diversity(db):
    src = _source(db)
    # Three near-identical stories from DISTINCT publishers should group, and
    # source_diversity should count distinct publishers.
    arts = [
        {"headline": "Renewable energy output rose 12 percent this year",
         "url": "https://a.com/1", "summary": "Renewable energy output rose 12 percent.",
         "publisher": "PubA"},
        {"headline": "Renewable energy output increased 12 percent this year",
         "url": "https://b.com/2", "summary": "Renewable energy output increased 12 percent.",
         "publisher": "PubB"},
        {"headline": "An unrelated article about a sports championship final",
         "url": "https://c.com/3", "summary": "The team won the championship final.",
         "publisher": "PubC"},
    ]
    news_svc.ingest_articles(db, src, arts)
    from app.models import Article, Story
    from sqlalchemy import select
    stories = db.scalars(select(Story)).all()
    # The two renewable articles group; the sports one is separate.
    assert len(stories) == 2
    grouped = max(stories, key=lambda s: s.article_count)
    assert grouped.article_count == 2
    assert grouped.source_diversity == 2  # distinct publishers


def test_syndication_does_not_inflate_diversity(db):
    src = _source(db)
    arts = [
        {"headline": "Breaking major policy announcement today",
         "url": "https://a.com/x", "summary": "A major policy announcement was made.",
         "publisher": "WireService"},
        {"headline": "Breaking major policy announcement today republished",
         "url": "https://b.com/x", "summary": "A major policy announcement was made.",
         "publisher": "WireService"},  # same publisher (syndication)
    ]
    news_svc.ingest_articles(db, src, arts)
    from app.models import Story
    from sqlalchemy import select
    story = db.scalars(select(Story)).first()
    assert story.source_diversity == 1  # one distinct publisher despite 2 copies
