"""What-If Simulator and anomaly services."""
from __future__ import annotations

from ..analytics import anomalies, config
from ..analytics.data_model import AnalyticsModel
from ..analytics.filters import Filters, apply
from ..analytics.metrics import aggregate
from ..analytics.scenario import ScenarioParams, preset_params, simulate
from .common import BadRequestError, meta, months_in

SUMMARY_KEYS = ["baseline_incremental_costs", "scenario_incremental_costs", "gross_cost_savings", "retained_margin",
                "prevention_spend", "net_improvement", "cost_reduction_pct", "scenario_contribution", "roi",
                "payback_months", "scenario_unit_return_rate"]


def build(model: AnalyticsModel, f: Filters, params: ScenarioParams) -> dict:
    errors = params.validate()
    known = set(model.products["category"])
    unknown = [c for c in params.category_overrides if c not in known]
    if unknown:
        errors.append(f"Unknown category in overrides: {', '.join(unknown)}")
    if errors:
        raise BadRequestError("; ".join(errors))

    lines = apply(model.lines, f)
    cats = aggregate(lines, "category")
    cats = cats[cats["units"] > 0]
    months = months_in(lines)
    result = simulate(cats, params, months)

    baseline_incr = result["baseline_incremental_costs"]
    presets = []
    for key, p in config.SCENARIO_PRESETS.items():
        pp = preset_params(key, baseline_incr)
        res = simulate(cats, pp, months)
        presets.append({
            "key": key, "label": p["label"],
            "params": res["params"],
            **{k: res[k] for k in SUMMARY_KEYS},
        })
    return {
        "meta": meta(model, f, len(lines)),
        "result": result,
        "presets": presets,
        "limits": {k: {"min": lo, "max": hi} for k, (lo, hi) in config.SCENARIO_LIMITS.items()},
        "categories": sorted(cats["category"].tolist()),
        "formulas": [
            "Scenario reverse logistics = baseline × (1 − return reduction) × (1 − logistics efficiency)",
            "Scenario restocking = baseline × (1 − return reduction)",
            "Scenario write-off = baseline × (1 − return reduction) × (1 − write-off reduction)",
            "Retained margin = return reduction × retained-sale share × (refunds − returned inventory at cost)",
            "Net improvement = gross cost savings + retained margin − prevention spend",
            "ROI = net improvement ÷ prevention spend; payback = spend ÷ average monthly gross benefit",
        ],
        "disclaimer": ("Hypothetical estimates calculated from historical synthetic data. They are not forecasts "
                       "and do not guarantee savings."),
    }


def detect_anomalies(model: AnalyticsModel, f: Filters, min_units: int, min_returns: int,
                     rate_lift: float, z_threshold: float) -> dict:
    lines = apply(model.lines, f)
    res = anomalies.detect(lines, min_units=min_units, min_returns=min_returns, rate_lift=rate_lift,
                           z_threshold=z_threshold)
    return {"meta": meta(model, f, len(res["flags"])), **res,
            "disclaimer": "Statistical signals for investigation. They do not establish cause, fraud or wrongdoing."}
