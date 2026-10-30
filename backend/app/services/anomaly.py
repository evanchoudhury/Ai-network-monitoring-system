"""Time-series anomaly detection.

Two complementary, interpretable methods:

1. **Rolling z-score** (default): compares the latest observation against the
   mean/std of a trailing baseline window. Interpretable and deterministic.
2. **IsolationForest** (optional, scikit-learn): a multivariate detector used
   as a secondary opinion across several features.

Design principles
------------------
* Missing data points are skipped, not treated as zero.
* A minimum number of baseline points is required before any alert fires,
  avoiding noise on cold starts.
* Every detection records the baseline statistics and the observation window,
  and explains exactly which measurement triggered it.
* An anomaly is explicitly **not** a confirmed attack.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

# Metrics where a *higher* value is the concern (spikes). For latency/errors we
# care about upward deviations; for request_rate both directions matter but a
# spike is the primary alerting case here.
UPWARD_METRICS = {
    "error_rate", "error_count", "latency_p95_ms", "latency_p99_ms",
    "latency_p50_ms", "request_rate", "request_count", "bytes_in", "bytes_out",
}

DETECTOR_VERSION = "zscore-1.0"


@dataclass
class Point:
    timestamp: datetime
    value: float | None


@dataclass
class Detection:
    metric_name: str
    observed_value: float
    baseline_mean: float
    baseline_std: float
    zscore: float
    method: str
    window_start: datetime
    window_end: datetime
    severity: str
    explanation: str
    confirmed_attack: bool = False


def _clean(points: list[Point]) -> list[Point]:
    return [p for p in points if p.value is not None and np.isfinite(p.value)]


def _severity_from_z(z: float, threshold: float) -> str:
    az = abs(z)
    if az >= threshold * 2.0:
        return "critical"
    if az >= threshold * 1.4:
        return "high"
    if az >= threshold:
        return "medium"
    return "low"


def _evaluate(
    metric_name: str,
    baseline: list[Point],
    latest: Point,
    *,
    threshold: float,
    direction: str,
) -> Detection | None:
    """Evaluate a single observation against a baseline window."""
    if len(baseline) < 2 or latest.value is None:
        return None
    values = np.array([p.value for p in baseline], dtype=float)
    mean = float(values.mean())
    std = float(values.std(ddof=1))

    # Guard against a degenerate (near-constant) baseline producing huge z.
    if std < 1e-9:
        if abs(latest.value - mean) < 1e-9:
            return None
        std = max(abs(mean) * 0.05, 1e-6)

    z = (latest.value - mean) / std

    if direction == "auto":
        direction = "up" if metric_name in UPWARD_METRICS else "both"

    triggered = (
        (direction == "up" and z >= threshold)
        or (direction == "down" and z <= -threshold)
        or (direction == "both" and abs(z) >= threshold)
    )
    if not triggered:
        return None

    severity = _severity_from_z(z, threshold)
    pct = ((latest.value - mean) / mean * 100.0) if mean else float("inf")
    arrow = "above" if z > 0 else "below"
    explanation = (
        f"{metric_name} observed at {latest.value:.3g} is {abs(z):.1f} standard "
        f"deviations {arrow} the trailing baseline (mean {mean:.3g}, std {std:.3g} "
        f"over {len(baseline)} points). That is roughly {abs(pct):.0f}% "
        f"{'higher' if z > 0 else 'lower'} than baseline. This indicates an "
        f"unusual pattern, not a confirmed attack."
    )
    return Detection(
        metric_name=metric_name,
        observed_value=float(latest.value),
        baseline_mean=round(mean, 6),
        baseline_std=round(std, 6),
        zscore=round(float(z), 4),
        method="zscore",
        window_start=baseline[0].timestamp,
        window_end=latest.timestamp,
        severity=severity,
        explanation=explanation,
        confirmed_attack=False,
    )


def detect_zscore(
    metric_name: str,
    points: list[Point],
    *,
    threshold: float = 3.5,
    min_baseline: int = 12,
    baseline_window: int = 48,
    direction: str = "auto",
) -> Detection | None:
    """Detect an anomaly in the *latest* point using a rolling z-score.

    ``points`` must be ordered oldest -> newest. Suited to live scanning where
    only the newest observation is of interest. Returns ``None`` when there is
    insufficient data or no anomaly.
    """
    clean = _clean(points)
    if len(clean) < min_baseline + 1:
        return None
    baseline = clean[-(baseline_window + 1):-1] if baseline_window else clean[:-1]
    if len(baseline) < min_baseline:
        return None
    return _evaluate(metric_name, baseline, clean[-1],
                     threshold=threshold, direction=direction)


def detect_series(
    metric_name: str,
    points: list[Point],
    *,
    threshold: float = 3.5,
    min_baseline: int = 12,
    baseline_window: int = 48,
    direction: str = "auto",
) -> list[Detection]:
    """Scan an entire series, flagging every anomalous point.

    Used for historical analysis and the anomaly timeline. Each flagged point
    is evaluated against the baseline window that immediately precedes it.
    """
    clean = _clean(points)
    detections: list[Detection] = []
    for i in range(min_baseline, len(clean)):
        start = max(0, i - baseline_window) if baseline_window else 0
        baseline = clean[start:i]
        if len(baseline) < min_baseline:
            continue
        det = _evaluate(metric_name, baseline, clean[i],
                        threshold=threshold, direction=direction)
        if det is not None:
            detections.append(det)
    return detections


def detect_isolation_forest(
    feature_rows: list[dict[str, float]],
    feature_names: list[str],
    *,
    contamination: float = 0.05,
) -> list[int]:
    """Return indices flagged as anomalous by IsolationForest.

    Multivariate secondary detector. Requires enough rows to be meaningful;
    returns an empty list otherwise. Imported lazily to keep startup light.
    """
    if len(feature_rows) < 20:
        return []
    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:  # pragma: no cover
        return []

    matrix = np.array(
        [[row.get(name, 0.0) or 0.0 for name in feature_names] for row in feature_rows],
        dtype=float,
    )
    model = IsolationForest(
        contamination=contamination, random_state=42, n_estimators=100
    )
    preds = model.fit_predict(matrix)
    return [i for i, p in enumerate(preds) if p == -1]
