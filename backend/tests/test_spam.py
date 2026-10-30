"""Spam/phishing detection tests (deterministic rule engine)."""
from __future__ import annotations

from app.services.spam import analyze_message


def test_clean_message_is_clean():
    r = analyze_message("Hi, are we still on for lunch tomorrow at noon?")
    assert r.category == "clean"
    assert r.score == 0.0
    assert r.score_is_calibrated is False  # never claim calibration


def test_phishing_message_flagged():
    msg = ("URGENT: Your PayPal account has been suspended. Verify your identity "
           "immediately at http://paypal-secure-login.xyz or it will be closed.")
    r = analyze_message(msg)
    assert r.category in {"phishing", "high_risk"}
    names = {i["name"] for i in r.indicators}
    assert "credential_harvesting" in names
    assert r.urls  # the link was extracted
    assert any(u["flags"] for u in r.urls)


def test_shortener_and_prize_scam():
    r = analyze_message("Congratulations! You've won a $1000 gift card. Claim at http://bit.ly/x")
    names = {i["name"] for i in r.indicators}
    assert "shortened_url" in names
    assert "scam_pattern" in names
    assert r.category in {"suspicious", "high_risk", "phishing"}


def test_ip_address_url_flagged():
    r = analyze_message("Update your billing information now: http://192.168.10.5/login")
    names = {i["name"] for i in r.indicators}
    assert "ip_address_url" in names


def test_indicators_are_explained_and_urls_not_fetched():
    r = analyze_message("Verify your account at http://evil.example/login immediately!")
    assert r.explanation
    assert r.recommendation
    # The analyzer only parses URLs; it never fetches them. We assert the
    # structure is metadata-only (host present, no response/content field).
    for u in r.urls:
        assert "host" in u and "status_code" not in u
