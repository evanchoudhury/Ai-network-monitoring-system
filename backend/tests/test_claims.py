"""Claim extraction, stance, and classification tests (pure logic)."""
from __future__ import annotations

from app.services.claims import (
    EvidenceItem,
    classify,
    determine_stance,
    extract_claims,
    extract_entities,
)


def _ev(stance, rel=0.5):
    return EvidenceItem(url="http://x", title="t", publisher="p", snippet="s",
                        stance=stance, relevance=rel, provider="test")


def test_extract_claims_prefers_checkworthy_sentences():
    text = ("I think the weather is nice. The government announced a 4 billion dollar "
            "infrastructure plan on Monday. What do you think?")
    claims = extract_claims(text, min_score=1.0)
    assert any("4 billion dollar" in c.text for c in claims)
    # The opinion/question sentences should rank lower or be excluded.
    assert all("What do you think" not in c.text for c in claims)


def test_extract_entities():
    ents = extract_entities("NASA launched the Artemis rocket in December with 3 astronauts.")
    assert ents["named_entities"]
    assert ents["dates"]
    assert any("3" in n for n in ents["numbers"])


def test_stance_detection_negation():
    claim = "The new battery charges a phone in 10 seconds"
    support = "The new battery charges a phone in 10 seconds, researchers confirmed"
    contra = "The claim that the new battery charges a phone in 10 seconds is false"
    assert determine_stance(claim, support) == "support"
    assert determine_stance(claim, contra) == "contradict"


def test_insufficient_evidence_abstains():
    a = classify("Some unusual claim", [])
    assert a.label == "insufficient_evidence"
    assert a.supporting_count == 0 and a.contradicting_count == 0


def test_single_source_is_unverified():
    a = classify("A claim", [_ev("support")], min_evidence=2)
    assert a.label == "unverified"  # below minimum evidence threshold


def test_supported_when_corroborated():
    a = classify("A claim", [_ev("support"), _ev("support")], min_evidence=2)
    assert a.label == "supported"


def test_contradicted():
    a = classify("A claim", [_ev("contradict"), _ev("contradict")], min_evidence=2)
    assert a.label == "contradicted"


def test_disputed_when_mixed():
    a = classify("A claim", [_ev("support"), _ev("support"), _ev("contradict"), _ev("contradict")],
                 min_evidence=2)
    assert a.label == "disputed"


def test_assessment_always_has_limitations():
    for ev in ([], [_ev("support"), _ev("support")]):
        a = classify("A claim", ev)
        assert a.limitations  # honesty: limitations always recorded
