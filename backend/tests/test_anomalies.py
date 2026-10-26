"""Anomaly detection edge cases: spikes, zero baselines, gaps and small samples."""
import pandas as pd

from app.analytics.anomalies import detect


def synthetic_lines(months_rates: dict[str, tuple[int, int]], category="Shoes") -> pd.DataFrame:
    """Build minimal line rows: per month (units, returned_units)."""
    rows = []
    i = 0
    for month, (units, returned) in months_rates.items():
        for j in range(units):
            i += 1
            r = 1.0 if j < returned else 0.0
            rows.append(dict(order_line_id=f"L{i}", order_id=f"O{i}", month=month, category=category,
                             supplier_id="S1", shipping_region="R1", is_eligible=True, has_refunded_return=r > 0,
                             gmv=100.0, discount=0.0, net_sales=100.0, units=1.0, cogs=50.0, returned_units=r,
                             refund=100.0 * r, returned_cost=50.0 * r, reverse_logistics=80.0 * r,
                             restocking=30.0 * r, write_off=0.0, rejected_units=0.0, pending_units=0.0))
    return pd.DataFrame(rows)


def flags_for(lines, metric="Unit return rate", **kw):
    return [f for f in detect(lines, **kw)["flags"] if f["metric"] == metric and f["dimension"] == "Category"]


def test_detects_clear_spike():
    lines = synthetic_lines({"2026-01": (400, 40), "2026-02": (400, 40), "2026-03": (400, 40), "2026-04": (400, 100)})
    f = flags_for(lines)
    assert len(f) == 1 and f[0]["month"] == "2026-04"
    assert f[0]["baseline"] == 0.1 and f[0]["observed"] == 0.25
    assert "baseline" in f[0]["reason"]


def test_small_sample_is_not_flagged():
    lines = synthetic_lines({"2026-01": (40, 4), "2026-02": (40, 4), "2026-03": (40, 4), "2026-04": (40, 20)})
    assert flags_for(lines) == []
    assert detect(lines)["skipped_insufficient_volume"] > 0


def test_zero_baseline_does_not_divide_by_zero():
    lines = synthetic_lines({"2026-01": (300, 0), "2026-02": (300, 0), "2026-03": (300, 30)})
    assert flags_for(lines) == []  # zero baseline -> no rate test, no crash


def test_missing_month_breaks_baseline():
    # gap in March: April has no consecutive baseline months, so it is skipped
    lines = synthetic_lines({"2026-01": (400, 40), "2026-02": (400, 40), "2026-04": (400, 120)})
    assert flags_for(lines) == []


def test_needs_two_baseline_months():
    lines = synthetic_lines({"2026-01": (400, 40), "2026-02": (400, 140)})
    assert flags_for(lines) == []


def test_real_data_detects_injected_footwear_anomaly(real_model):
    flags = detect(real_model.lines)["flags"]
    footwear = [f for f in flags if f["member"] == "Footwear" and f["metric"] == "Unit return rate"]
    assert any(f["month"] in ("2026-06", "2026-07") for f in footwear)
