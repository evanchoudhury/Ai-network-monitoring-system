"""Claim extraction and evidence-based assessment.

This is a deterministic, transparent pipeline. It does **not** attempt to
decide absolute truth. It extracts check-worthy factual claims, retrieves
evidence from *configured, authorized* sources, compares supporting and
contradicting evidence, and abstains (``insufficient_evidence`` /
``unverified``) when evidence is thin.

What it explicitly avoids
-------------------------
* Inferring truth from publisher reputation, popularity, or model confidence.
* Treating syndicated duplicates as independent corroboration (dedup +
  distinct-publisher counting happen upstream in ``news.py``).
* Executing any instruction contained in article text (content is data only).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

MODEL_VERSION = "claims-rules-1.1"

# Verbs/structures that signal an assertive, checkable statement.
ASSERTIVE_CUES = re.compile(
    r"\b(is|are|was|were|will|has|have|had|causes?|caused|proves?|proved|found|"
    r"shows?|showed|announces?|announced|reports?|reported|claims?|claimed|"
    r"confirms?|confirmed|reveals?|revealed|increases?|increased|decreases?|"
    r"decreased|kills?|killed|banned?|launch(?:es|ed)?)\b",
    re.IGNORECASE,
)

QUANTITY_RE = re.compile(
    r"\b\d[\d,.]*\s?(?:percent|%|million|billion|thousand|people|deaths?|cases?|"
    r"dollars?|usd|kg|km|years?|days?|times)\b",
    re.IGNORECASE,
)
NUMBER_RE = re.compile(r"\b\d[\d,.]*\b")
DATE_RE = re.compile(
    r"\b(?:\d{4}|\d{1,2}(?:st|nd|rd|th)?\s+)?(?:January|February|March|April|May|"
    r"June|July|August|September|October|November|December|Monday|Tuesday|"
    r"Wednesday|Thursday|Friday|Saturday|Sunday|today|yesterday|tomorrow)\b",
    re.IGNORECASE,
)
# Proper-noun sequences as a cheap named-entity proxy.
ENTITY_RE = re.compile(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b")
NEGATION_RE = re.compile(
    r"\b(no|not|never|denies?|denied|false|hoax|debunk(?:ed|s)?|incorrect|untrue|"
    r"myth|misleading|fabricat(?:ed|ion)|without evidence|no evidence)\b",
    re.IGNORECASE,
)

STOPWORDS = set(
    "the a an and or but of to in on at for with from by as is are was were be "
    "been being this that these those it its he she they them his her their our "
    "your you we i has have had will would could should may might can do does did "
    "not no more most some any all than then so such into over under about".split()
)


@dataclass
class ExtractedClaim:
    text: str
    entities: dict
    score: float


@dataclass
class EvidenceItem:
    url: str
    title: str | None
    publisher: str | None
    snippet: str | None
    stance: str  # support | contradict | context
    relevance: float
    provider: str
    evidence_timestamp: datetime | None = None


@dataclass
class Assessment:
    label: str
    explanation: str
    limitations: str
    supporting_count: int
    contradicting_count: int
    model_version: str = MODEL_VERSION


def _sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    # Simple sentence splitter; good enough for headlines/summaries.
    raw = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", text)
    return [s.strip() for s in raw if len(s.strip()) >= 20]


def _tokenize(text: str) -> set[str]:
    return {
        w for w in re.findall(r"[a-z0-9]+", text.lower())
        if w not in STOPWORDS and len(w) > 2
    }


def extract_entities(text: str) -> dict:
    entities = [e for e in ENTITY_RE.findall(text) if e.lower() not in STOPWORDS]
    # Drop sentence-initial single words that are just capitalized stopwords.
    return {
        "named_entities": sorted(set(entities))[:15],
        "dates": sorted(set(DATE_RE.findall(text)))[:10],
        "quantities": sorted(set(m.group(0) for m in QUANTITY_RE.finditer(text)))[:10],
        "numbers": sorted(set(NUMBER_RE.findall(text)))[:15],
    }


def score_claim(sentence: str) -> float:
    """Heuristic check-worthiness score in [0, ~5]."""
    score = 0.0
    if ASSERTIVE_CUES.search(sentence):
        score += 1.0
    if QUANTITY_RE.search(sentence):
        score += 1.5
    elif NUMBER_RE.search(sentence):
        score += 0.7
    if DATE_RE.search(sentence):
        score += 0.6
    ents = ENTITY_RE.findall(sentence)
    score += min(len(ents), 3) * 0.4
    # Penalize opinion/question framing.
    if sentence.rstrip().endswith("?"):
        score -= 1.0
    if re.search(r"\b(i think|in my opinion|probably|maybe|should|could)\b",
                 sentence, re.IGNORECASE):
        score -= 0.8
    return round(score, 3)


def extract_claims(text: str, *, max_claims: int = 5, min_score: float = 1.2) -> list[ExtractedClaim]:
    """Extract check-worthy factual claims, preserving exact wording."""
    candidates: list[ExtractedClaim] = []
    for sent in _sentences(text):
        s = score_claim(sent)
        if s >= min_score:
            candidates.append(
                ExtractedClaim(text=sent, entities=extract_entities(sent), score=s)
            )
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:max_claims]


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def determine_stance(claim: str, evidence_text: str) -> str:
    """Classify evidence stance relative to the claim via lexical overlap +
    negation. Conservative: defaults to 'context' when unclear."""
    claim_tokens = _tokenize(claim)
    ev_tokens = _tokenize(evidence_text)
    overlap = _jaccard(claim_tokens, ev_tokens)
    if overlap < 0.08:
        return "context"
    claim_neg = bool(NEGATION_RE.search(claim))
    ev_neg = bool(NEGATION_RE.search(evidence_text))
    # If one side negates and the other does not, treat as contradicting.
    if claim_neg != ev_neg and overlap >= 0.12:
        return "contradict"
    if overlap >= 0.12:
        return "support"
    return "context"


def classify(
    claim: str,
    evidence: list[EvidenceItem],
    *,
    min_evidence: int = 2,
) -> Assessment:
    """Produce a structured assessment with explicit abstention."""
    support = [e for e in evidence if e.stance == "support"]
    contradict = [e for e in evidence if e.stance == "contradict"]
    n_support = len(support)
    n_contradict = len(contradict)
    total_relevant = n_support + n_contradict

    limitations = (
        "This assessment reflects only evidence retrievable from the sources "
        "configured in this deployment at assessment time. It is not a "
        "determination of absolute truth, and should be confirmed by a human "
        "reviewer for consequential decisions."
    )

    # Abstain when evidence is thin.
    if total_relevant == 0:
        return Assessment(
            label="insufficient_evidence",
            explanation=(
                "No supporting or contradicting evidence was found in the "
                "configured sources. The claim is recorded but not assessed."
            ),
            limitations=limitations,
            supporting_count=0,
            contradicting_count=0,
        )
    if total_relevant < min_evidence:
        return Assessment(
            label="unverified",
            explanation=(
                f"Only {total_relevant} relevant evidence item(s) were found, "
                f"which is below the minimum of {min_evidence} required for a "
                f"confident assessment. Treated as unverified."
            ),
            limitations=limitations,
            supporting_count=n_support,
            contradicting_count=n_contradict,
        )

    # Both sides present -> disputed/misleading.
    if n_support > 0 and n_contradict > 0:
        if abs(n_support - n_contradict) <= 1:
            label = "disputed"
            expl = (
                f"Evidence is mixed: {n_support} source(s) appear to support and "
                f"{n_contradict} appear to contradict the claim. Marked disputed; "
                f"human review recommended."
            )
        elif n_contradict > n_support:
            label = "misleading"
            expl = (
                f"More evidence contradicts ({n_contradict}) than supports "
                f"({n_support}) the claim, suggesting it may be misleading or "
                f"missing important context."
            )
        else:
            label = "disputed"
            expl = (
                f"Evidence leans supporting ({n_support} vs {n_contradict}) but "
                f"contradicting sources exist; marked disputed pending review."
            )
        return Assessment(label, expl, limitations, n_support, n_contradict)

    if n_contradict > 0:
        return Assessment(
            "contradicted",
            f"{n_contradict} source(s) in the configured evidence set contradict "
            f"the claim and none support it.",
            limitations, n_support, n_contradict,
        )

    return Assessment(
        "supported",
        f"{n_support} source(s) in the configured evidence set support the claim "
        f"and none contradict it. This indicates corroboration within the "
        f"configured sources, not proof of truth.",
        limitations, n_support, n_contradict,
    )
