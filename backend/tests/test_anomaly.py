"""Deterministic anomaly-detection tests on synthetic series."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.anomaly import Point, detect_series, detect_zscore


def _series(values, start=None, step_minutes=15):
    start = start or datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [Point(start + timedelta(minutes=i * step_minutes), v) for i, v in enumerate(values)]


def test_stable_series_has_no_anomaly():
    pts = _series([100 + (i % 3) for i in range(60)])
    assert detect_zscore("request_rate", pts, threshold=3.5, min_baseline=12) is None
    assert detect_series("request_rate", pts, threshold=3.5, min_baseline=12) == []


def test_spike_is_detected_on_latest_point():
    values = [100 + (i % 3) for i in range(40)] + [900]
    det = detect_zscore("request_rate", _series(values), threshold=3.5, min_baseline=12)
    assert det is not None
    assert det.observed_value == 900
    assert det.zscore > 3.5
    assert det.confirmed_attack is False  # never auto-confirm an attack
    assert det.severity in {"medium", "high", "critical"}


def test_series_scan_finds_mid_history_spike():
    values = [100 + (i % 3) for i in range(60)]
    values[30] = 1200  # inject a mid-series spike
    dets = detect_series("request_rate", _series(values), threshold=3.5, min_baseline=12)
    assert len(dets) >= 1
    assert any(abs(d.observed_value - 1200) < 1e-6 for d in dets)


def test_missing_data_is_handled():
    values = [100, None, 102, None, 101] + [100 + (i % 2) for i in range(40)] + [700]
    det = detect_zscore("error_rate", _series(values), threshold=3.0, min_baseline=10)
    assert det is not None  # Nones skipped, spike still found
    assert det.baseline_mean > 0


def test_insufficient_baseline_returns_none():
    det = detect_zscore("request_rate", _series([100, 200, 300]), min_baseline=12)
    assert det is None


def test_sensitivity_is_configurable():
    # Baseline with real variance (~15 std around 100); the point at 160 is
    # roughly 4 std out, so a loose threshold flags it and a strict one does not.
    values = [85 if i % 2 == 0 else 115 for i in range(40)] + [160]
    assert detect_zscore("request_rate", _series(values), threshold=2.0, min_baseline=12) is not None
    assert detect_zscore("request_rate", _series(values), threshold=8.0, min_baseline=12) is None


def test_explanation_records_baseline_and_window():
    values = [50 + (i % 2) for i in range(30)] + [500]
    det = detect_zscore("latency_p95_ms", _series(values), threshold=3.0, min_baseline=12)
    assert det is not None
    assert det.baseline_mean is not None and det.baseline_std is not None
    assert det.window_start < det.window_end
    assert "standard deviation" in det.explanation
