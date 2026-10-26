"""
Explainable anomaly detection on monthly metrics.

Method (per dimension member, e.g. a category, supplier or region):
  baseline   = pooled value over the previous N months (default 3) that have data
  rate tests = unit return rate:  flag when observed >= baseline x LIFT
               AND z = (p - p0) / sqrt(p0 (1 - p0) / n) >= Z   AND n >= MIN_UNITS
  cost test  = reverse-logistics cost per returned unit:
               flag when observed >= baseline x COST_LIFT AND returned units >= MIN_RETURNS
  refund test= refund rate (refunds / net sales): observed >= baseline x REFUND_LIFT
               AND returned units >= 2 x MIN_RETURNS (value-weighted, so needs more volume)

Small groups are reported as "insufficient volume" rather than flagged, months with
no baseline (start of the series or gaps) are skipped, and a zero baseline is never
divided by. An anomaly is a statistical signal for investigation; it does not
establish cause, fraud or wrongdoing.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import config
from .metrics import aggregate, clean

DIMENSIONS = {"category": "Category", "supplier_id": "Supplier", "shipping_region": "Region"}


def detect(lines: pd.DataFrame, baseline_months: int = config.ANOMALY_BASELINE_MONTHS,
           min_units: int = config.ANOMALY_MIN_UNITS, min_returns: int = config.ANOMALY_MIN_RETURNS,
           rate_lift: float = config.ANOMALY_RATE_LIFT, z_threshold: float = config.ANOMALY_Z,
           cost_lift: float = config.ANOMALY_COST_LIFT,
           refund_lift: float = config.ANOMALY_REFUND_LIFT) -> dict:
    flags: list[dict] = []
    skipped_small = 0
    tests_run = 0
    for dim, dim_label in DIMENSIONS.items():
        monthly = aggregate(lines, [dim, "month"]) if len(lines) else pd.DataFrame()
        if monthly.empty:
            continue
        for member, g in monthly.groupby(dim):
            g = g.sort_values("month").reset_index(drop=True)
            months = list(g["month"])
            for i in range(len(g)):
                prior = g.iloc[max(0, i - baseline_months):i]
                if len(prior) < 2 or not _consecutive(months, i, len(prior)):
                    continue
                cur = g.iloc[i]
                # --- unit return rate ---
                n = float(cur["units"])
                if n < min_units:
                    skipped_small += 1
                else:
                    tests_run += 1
                    p0 = _safe(prior["returned_units"].sum(), prior["units"].sum())
                    p = _safe(cur["returned_units"], n)
                    if p0 and p is not None and 0 < p0 < 1:
                        z = (p - p0) / math.sqrt(p0 * (1 - p0) / n)
                        if p >= p0 * rate_lift and z >= z_threshold:
                            flags.append(_flag(dim_label, member, cur["month"], "Unit return rate", p, p0, "percent",
                                               f"z = {z:.1f}; {int(cur['returned_units'])} of {int(n)} units returned",
                                               baseline_months, z))
                # --- cost per returned unit & refund rate ---
                if float(cur["returned_units"]) < min_returns:
                    skipped_small += 1
                    continue
                tests_run += 1
                handled = float(cur["returned_units"] + cur["rejected_units"])
                c0 = _safe(prior["reverse_logistics"].sum(), (prior["returned_units"] + prior["rejected_units"]).sum())
                c = _safe(cur["reverse_logistics"], handled)
                if c0 and c is not None and c >= c0 * cost_lift:
                    flags.append(_flag(dim_label, member, cur["month"], "Reverse logistics cost per returned unit", c, c0,
                                       "currency", f"{int(handled)} returned units handled", baseline_months))
                f0 = _safe(prior["refund"].sum(), prior["net_sales"].sum())
                f = _safe(cur["refund"], cur["net_sales"])
                if (f0 and f is not None and f >= f0 * refund_lift
                        and float(cur["returned_units"]) >= 2 * min_returns):
                    flags.append(_flag(dim_label, member, cur["month"], "Refund rate (refunds / net sales)", f, f0,
                                       "percent", f"refunds INR {cur['refund']:,.0f}", baseline_months))
    flags.sort(key=lambda x: (-x["lift"], x["month"]))
    return {
        "method": {
            "baseline_months": baseline_months, "min_units": min_units, "min_returns": min_returns,
            "rate_lift": rate_lift, "z_threshold": z_threshold, "cost_lift": cost_lift, "refund_lift": refund_lift,
            "description": ("Each month is compared with the pooled previous months for the same category, "
                            "supplier or region. Rate flags need both a relative lift and statistical "
                            "significance; cost flags need a relative lift and a minimum number of returns."),
        },
        "tests_run": tests_run,
        "skipped_insufficient_volume": skipped_small,
        "flags": flags,
    }


def _consecutive(months: list[str], i: int, k: int) -> bool:
    """True when the k months before index i are consecutive calendar months ending the month before i."""
    cur = pd.Period(months[i], freq="M")
    expected = [str(cur - j) for j in range(k, 0, -1)]
    return months[i - k:i] == expected


def _safe(num, den):
    num, den = float(num), float(den)
    return None if den == 0 or np.isnan(den) else num / den


def _flag(dim_label, member, month, metric, observed, baseline, unit, evidence, baseline_months, z=None) -> dict:
    lift = observed / baseline if baseline else None
    if unit == "percent":
        reason = (f"{metric} of {observed:.1%} vs {baseline:.1%} baseline "
                  f"({(lift - 1):+.0%}); {evidence}")
    else:
        reason = (f"{metric} of INR {observed:,.0f} vs INR {baseline:,.0f} baseline "
                  f"({(lift - 1):+.0%}); {evidence}")
    return {
        "dimension": dim_label,
        "member": str(member),
        "month": month,
        "metric": metric,
        "unit": unit,
        "observed": clean(observed),
        "baseline": clean(baseline),
        "lift": clean(lift),
        "z_score": clean(z),
        "baseline_period": f"previous {baseline_months} months",
        "reason": reason,
        "severity": "high" if lift and lift >= 1.6 else "medium",
    }
