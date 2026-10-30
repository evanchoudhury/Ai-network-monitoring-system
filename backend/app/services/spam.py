"""Spam and phishing detection.

A deterministic, explainable rule engine. Every contribution to the score is
recorded as a named indicator with its weight, so the result is fully
auditable. The numeric score is a *heuristic risk score*, NOT a calibrated
probability — callers must treat it as such until a calibration study is run.

Safety properties
-----------------
* URLs are parsed and inspected but **never fetched** automatically.
* Message content is not sent to any external AI provider.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

MODEL_VERSION = "rules-1.1"

# URL shorteners commonly abused to hide destinations.
SHORTENER_DOMAINS = {
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "is.gd", "buff.ly",
    "rebrand.ly", "cutt.ly", "shorturl.at", "rb.gy",
}

# Brands frequently impersonated in phishing.
IMPERSONATED_BRANDS = {
    "paypal", "apple", "microsoft", "amazon", "netflix", "google", "facebook",
    "instagram", "bank", "chase", "wellsfargo", "irs", "usps", "fedex", "dhl",
    "coinbase", "binance", "whatsapp", "linkedin",
}

CREDENTIAL_PATTERNS = [
    r"\bverify your (?:account|identity|password)\b",
    r"\bconfirm your (?:account|identity|password|details)\b",
    r"\bupdate your (?:payment|billing|account) (?:info|information|details)\b",
    r"\blog ?in to (?:verify|confirm|secure)\b",
    r"\byour account (?:has been|will be) (?:suspended|locked|disabled|closed)\b",
    r"\bunusual (?:sign[- ]?in|activity|login)\b",
    r"\bre[- ]?activate your account\b",
]

URGENCY_PATTERNS = [
    r"\b(?:urgent|immediately|right away|within \d+ hours?|act now|final notice)\b",
    r"\b(?:expires? (?:today|soon)|last chance|limited time)\b",
]

SCAM_PATTERNS = [
    r"\byou(?:'ve| have) won\b",
    r"\b(?:lottery|prize|jackpot|inheritance|beneficiary)\b",
    r"\bwire transfer\b",
    r"\b(?:gift ?cards?|bitcoin|btc|crypto)\b.*\b(?:pay|send|purchase)\b",
    r"\bnigerian? prince\b",
    r"\bprocessing fee\b",
    r"\b100% (?:free|guaranteed)\b",
    r"\bclaim your (?:reward|prize|refund)\b",
]

SUSPICIOUS_TLDS = {".zip", ".xyz", ".top", ".click", ".link", ".work", ".gq", ".tk", ".ml"}

URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.IGNORECASE)
IP_HOST_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


@dataclass
class Indicator:
    name: str
    weight: float
    detail: str


@dataclass
class SpamResult:
    category: str  # matches models.SpamCategory values
    score: float
    score_is_calibrated: bool
    indicators: list[dict]
    urls: list[dict]
    explanation: str
    recommendation: str
    model_version: str = MODEL_VERSION
    content_hash: str = ""
    preview: str = ""


def _extract_urls(text: str) -> list[str]:
    return URL_RE.findall(text or "")


def _analyze_url(raw: str) -> tuple[list[Indicator], dict]:
    inds: list[Indicator] = []
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    info = {"url": raw, "host": host, "flags": []}

    if host in SHORTENER_DOMAINS:
        inds.append(Indicator("shortened_url", 1.5, f"Uses URL shortener: {host}"))
        info["flags"].append("shortener")
    if IP_HOST_RE.match(host):
        inds.append(Indicator("ip_address_url", 2.0, f"Links to a raw IP address: {host}"))
        info["flags"].append("ip_host")
    for tld in SUSPICIOUS_TLDS:
        if host.endswith(tld):
            inds.append(Indicator("suspicious_tld", 1.5, f"Uncommon TLD in link: {host}"))
            info["flags"].append("suspicious_tld")
            break
    # Brand name appears in path/subdomain but not as the registrable domain.
    for brand in IMPERSONATED_BRANDS:
        if brand in raw.lower() and brand not in host:
            inds.append(
                Indicator(
                    "brand_in_non_domain",
                    2.0,
                    f"Brand '{brand}' appears in the link but not its domain ({host}).",
                )
            )
            info["flags"].append("possible_impersonation")
            break
    if host.count("-") >= 3 or host.count(".") >= 4:
        inds.append(Indicator("complex_hostname", 1.0, f"Unusually complex hostname: {host}"))
        info["flags"].append("complex_host")
    if parsed.username or "@" in parsed.netloc:
        inds.append(Indicator("url_userinfo", 2.0, "Link contains user-info/@ obfuscation."))
        info["flags"].append("userinfo")
    return inds, info


def _count_matches(text: str, patterns: list[str]) -> list[str]:
    hits: list[str] = []
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            hits.append(m.group(0))
    return hits


def analyze_message(text: str, source: str = "user_submission") -> SpamResult:
    text = (text or "").strip()
    lower = text.lower()
    indicators: list[Indicator] = []

    # Credential-harvesting language.
    cred_hits = _count_matches(lower, CREDENTIAL_PATTERNS)
    for h in cred_hits:
        indicators.append(Indicator("credential_harvesting", 2.5, f"Credential request: '{h}'"))

    # Urgency / pressure.
    urgency_hits = _count_matches(lower, URGENCY_PATTERNS)
    for h in urgency_hits[:2]:
        indicators.append(Indicator("urgency_pressure", 1.2, f"Urgency language: '{h}'"))

    # Scam patterns.
    scam_hits = _count_matches(lower, SCAM_PATTERNS)
    for h in scam_hits:
        indicators.append(Indicator("scam_pattern", 2.0, f"Common scam phrasing: '{h}'"))

    # Impersonation keywords in body.
    for brand in IMPERSONATED_BRANDS:
        if re.search(rf"\b{re.escape(brand)}\b", lower):
            # Only a weak signal on its own.
            indicators.append(Indicator("brand_mention", 0.4, f"Mentions brand '{brand}'."))
            break

    # Excessive repetition (same token repeated a lot).
    words = re.findall(r"[a-zA-Z']+", lower)
    if words:
        most = max(set(words), key=words.count)
        freq = words.count(most) / len(words)
        if len(words) >= 8 and freq > 0.25:
            indicators.append(
                Indicator("excessive_repetition", 1.0, f"Token '{most}' repeated heavily.")
            )

    # Excessive capitalization / shouting.
    letters = [c for c in text if c.isalpha()]
    if len(letters) >= 15:
        caps_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if caps_ratio > 0.55:
            indicators.append(Indicator("excessive_caps", 0.8, "Excessive capitalization."))

    # Too many exclamation marks.
    if text.count("!") >= 4:
        indicators.append(Indicator("excessive_exclamation", 0.6, "Many exclamation marks."))

    # URL analysis.
    urls = _extract_urls(text)
    url_infos: list[dict] = []
    for u in urls[:20]:
        u_inds, info = _analyze_url(u)
        indicators.extend(u_inds)
        url_infos.append(info)
    if len(urls) >= 4:
        indicators.append(Indicator("many_links", 0.8, f"Message contains {len(urls)} links."))

    # Request for money / payment combined with urgency is a strong signal.
    if ("gift card" in lower or "bitcoin" in lower or "wire" in lower) and urgency_hits:
        indicators.append(Indicator("payment_under_pressure", 1.5, "Payment request with urgency."))

    score = round(sum(i.weight for i in indicators), 3)
    phishing_signals = {
        "credential_harvesting", "brand_in_non_domain", "ip_address_url", "payment_under_pressure",
    }
    has_phishing = any(i.name in phishing_signals for i in indicators)

    # Map score -> category. Thresholds are heuristic, documented as such.
    if score >= 5.0 and has_phishing:
        category = "phishing"
    elif score >= 5.0:
        category = "high_risk"
    elif score >= 2.5:
        category = "suspicious"
    elif score >= 1.0:
        category = "low_risk"
    else:
        category = "clean"

    explanation = _build_explanation(indicators, category)
    recommendation = _build_recommendation(category)

    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    preview = (text[:200] + "…") if len(text) > 200 else text

    return SpamResult(
        category=category,
        score=score,
        score_is_calibrated=False,
        indicators=[i.__dict__ for i in indicators],
        urls=url_infos,
        explanation=explanation,
        recommendation=recommendation,
        content_hash=content_hash,
        preview=preview,
    )


def _build_explanation(indicators: list[Indicator], category: str) -> str:
    if not indicators:
        return (
            "No spam or phishing indicators were triggered. This is a heuristic "
            "result, not a guarantee the message is safe."
        )
    names = sorted({i.name.replace("_", " ") for i in indicators})
    return (
        f"Classified as '{category}' based on {len(indicators)} triggered indicator(s): "
        f"{', '.join(names)}. The score is a heuristic sum of indicator weights and is "
        f"not a calibrated probability."
    )


def _build_recommendation(category: str) -> str:
    return {
        "phishing": (
            "Do not click links or enter credentials. Report as phishing and verify the "
            "sender through an independent, trusted channel."
        ),
        "high_risk": "Treat as unsafe. Do not act on requests for money, data, or logins.",
        "suspicious": "Be cautious. Verify the sender independently before taking any action.",
        "low_risk": "Minor indicators present. Review before trusting embedded links.",
        "clean": "No action needed, but remain alert to unexpected requests.",
    }.get(category, "Review the message carefully.")
