"""Executive Overview page service."""
from __future__ import annotations

import pandas as pd

from ..analytics import config, insights
from ..analytics.data_model import AnalyticsModel
from ..analytics.definitions import METRICS_BY_KEY
from ..analytics.filters import Filters, apply
from ..analytics.metrics import aggregate, anatomy_steps, clean, records, summarize
from .common import meta, months_in

KPI_SPECS = [
    # key, label, direction where "good" is up/down, secondary key
    ("gmv", "Gross Merchandise Value", "up", None),
    ("unit_return_rate", "Unit Return Rate", "down", "order_return_rate"),
    ("refund", "Refund Value", "down", None),
    ("incremental_costs", "Est. Incremental Return Costs", "down", None),
    ("contribution_after", "Est. Contribution After Return Costs", "up", "contribution_margin"),
]

STATUS_ORDER = ["Delivered", "Partially Returned", "Returned", "Return in Progress", "Cancelled"]


def kpi_block(summary: dict, previous: dict | None, monthly: pd.DataFrame, specs=KPI_SPECS) -> list[dict]:
    out = []
    for key, label, good, secondary in specs:
        d = METRICS_BY_KEY[key]
        value = summary.get(key)
        prev = previous.get(key) if previous else None
        change = None
        if value is not None and prev is not None:
            if d["unit"] == "percent":
                change = value - prev  # percentage points (as a fraction)
            elif prev:
                change = (value - prev) / abs(prev)
        out.append({
            "key": key, "label": label, "value": clean(value), "unit": d["unit"], "kind": d["kind"],
            "previous": clean(prev), "change": clean(change),
            "change_type": "points" if d["unit"] == "percent" else "relative",
            "good_direction": good, "definition": d["definition"], "formula": d["formula"],
            "secondary_key": secondary,
            "secondary_label": METRICS_BY_KEY[secondary]["name"] if secondary else None,
            "secondary_value": clean(summary.get(secondary)) if secondary else None,
            "sparkline": [clean(v) for v in monthly[key].tolist()] if key in monthly.columns else [],
        })
    return out


def build(model: AnalyticsModel, f: Filters) -> dict:
    lines = apply(model.lines, f)
    s = summarize(lines)
    prev_f = f.previous_period(model.period_start)
    previous = summarize(apply(model.lines, prev_f)) if prev_f else None
    if previous and not previous.get("units"):
        previous = None

    monthly = aggregate(lines, "month").sort_values("month") if len(lines) else aggregate(lines, "month")
    cats = aggregate(lines, "category")
    cats = cats[cats["units"] > 0].sort_values("gmv", ascending=False)

    status = (lines.groupby("order_status").agg(lines=("order_line_id", "count"), units=("quantity", "sum"))
              .reindex(STATUS_ORDER).fillna(0).reset_index()) if len(lines) else pd.DataFrame(
        {"order_status": STATUS_ORDER, "lines": 0, "units": 0})
    total_lines = float(status["lines"].sum())
    status["share"] = status["lines"] / total_lines if total_lines else 0.0

    return {
        "meta": meta(model, f, len(lines)),
        "summary": s,
        "comparison": {
            "available": previous is not None,
            "previous_start": prev_f.start_date.isoformat() if prev_f and previous else None,
            "previous_end": prev_f.end_date.isoformat() if prev_f and previous else None,
            "note": None if previous is not None else (
                "Select a reporting period shorter than the full history to compare with the preceding period."),
        },
        "kpis": kpi_block(s, previous, monthly),
        "monthly": records(monthly[["month", "gmv", "net_sales", "net_revenue", "refund", "units", "returned_units",
                                     "unit_return_rate", "order_return_rate", "incremental_costs",
                                     "contribution_after"]]),
        "return_rate_target": config.RETURN_RATE_TARGET,
        "leakage_map": records(cats[["category", "gmv", "units", "returned_units", "unit_return_rate", "refund",
                                     "incremental_costs", "return_leakage", "contribution_after",
                                     "contribution_margin", "net_revenue"]]),
        "anatomy": anatomy_steps(s),
        "status_distribution": {
            "denominator": "All order lines placed in the selected period, including cancelled lines.",
            "rows": records(status.rename(columns={"order_status": "status"})),
        },
        "insights": insights.generate(lines, s, months_in(lines)),
    }
