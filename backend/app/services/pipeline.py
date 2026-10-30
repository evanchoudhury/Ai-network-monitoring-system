"""Orchestration that ties extraction + evidence retrieval + classification
together and persists results. Kept separate from the pure logic in
``claims.py`` so that module stays easily unit-testable without a database.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import (
    Article,
    Claim,
    ClaimAssessment,
    ClaimLabel,
    Evidence,
    Severity,
    AlertCategory,
)
from app.services import alerts, claims as claims_mod, news

logger = get_logger("sentinel.pipeline")


def analyze_article(db: Session, article: Article, *, use_factcheck: bool = True) -> list[Claim]:
    """Extract and assess claims for one article. Returns created Claim rows."""
    text = f"{article.headline}. {article.summary or ''} {article.content or ''}"
    extracted = claims_mod.extract_claims(text)
    created: list[Claim] = []

    for ex in extracted:
        # Avoid duplicate claim rows for the same article + text.
        existing = db.scalar(
            select(Claim).where(Claim.article_id == article.id, Claim.text == ex.text)
        )
        if existing is not None:
            continue
        claim = Claim(article_id=article.id, text=ex.text, entities=ex.entities)
        db.add(claim)
        db.flush()

        evidence_items = news.retrieve_local_evidence(
            db, ex.text, exclude_article_id=article.id
        )
        if use_factcheck:
            evidence_items += news.retrieve_factcheck_evidence(ex.text)

        for ev in evidence_items:
            db.add(Evidence(
                claim_id=claim.id,
                url=ev.url,
                title=ev.title,
                publisher=ev.publisher,
                snippet=ev.snippet,
                stance=ev.stance,
                relevance=ev.relevance,
                provider=ev.provider,
                evidence_timestamp=ev.evidence_timestamp,
            ))

        assessment = claims_mod.classify(ex.text, evidence_items)
        label = ClaimLabel(assessment.label)
        db.add(ClaimAssessment(
            claim_id=claim.id,
            label=label,
            explanation=assessment.explanation,
            limitations=assessment.limitations,
            supporting_count=assessment.supporting_count,
            contradicting_count=assessment.contradicting_count,
            model_version=assessment.model_version,
        ))
        claim.status = label
        claim.needs_review = label in {
            ClaimLabel.disputed, ClaimLabel.misleading, ClaimLabel.contradicted
        }
        db.flush()

        # Raise an alert when a notable claim is disputed/contradicted.
        if label in {ClaimLabel.disputed, ClaimLabel.contradicted, ClaimLabel.misleading}:
            alerts.create_alert(
                db,
                category=AlertCategory.claim_conflict,
                severity=Severity.medium,
                title=f"Conflicting evidence on a claim ({label.value})",
                explanation=assessment.explanation,
                source=article.publisher,
                related={"claim_id": claim.id, "article_id": article.id},
                discriminator=f"claim:{claim.id}",
                commit=False,
            )
        created.append(claim)

    db.commit()
    return created


def analyze_recent_articles(db: Session, limit: int = 20, use_factcheck: bool = True) -> int:
    """Assess the most recent articles that have no claims yet."""
    arts = db.scalars(
        select(Article).order_by(Article.ingested_at.desc()).limit(limit)
    ).all()
    total = 0
    for art in arts:
        has_claims = db.scalar(select(Claim.id).where(Claim.article_id == art.id))
        if has_claims is not None:
            continue
        created = analyze_article(db, art, use_factcheck=use_factcheck)
        total += len(created)
    return total
