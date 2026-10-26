"""
What-if simulator. HYPOTHETICAL ESTIMATES — not forecasts and not guaranteed savings.

Levers (all fractions):
  r  return_reduction        share of refunded returns avoided (0-30 %), overridable per category
  l  logistics_reduction     cost-per-return efficiency on the REMAINING returns (0-30 %)
  w  write_off_reduction     better grading/refurbishment of REMAINING returned stock (0-50 %)
  k  retained_sale_share     share of avoided returns that become kept sales; the rest
                             are assumed to become no-sale (e.g. customer does not buy)
  S  prevention_spend        INR spent on interventions during the selected period

Cost model, applied per category and summed (volume effect first, efficiency second,
so no saving is counted twice):

  scenario reverse logistics = RL × (1 − r) × (1 − l)
  scenario restocking        = RS × (1 − r)                (no efficiency lever modelled)
  scenario write-off         = WO × (1 − r) × (1 − w)
  gross cost savings         = baseline incremental − scenario incremental
      volume component       = r × (RL + RS + WO)
      efficiency component   = RL(1−r)l + WO(1−r)w
  retained margin            = r × k × (Refunds − Returned inventory at cost)
      (a kept sale retains the refund but the unit is no longer recovered to stock;
       refunds are revenue effects and are NOT counted as cost savings)
  net improvement            = gross cost savings + retained margin − S
  scenario contribution      = baseline contribution after return costs + net improvement
  ROI                        = net improvement / S                 (only when S > 0)
  payback (months)           = S / (monthly gross benefit)         (only when benefit > 0 and S > 0)

Rejected-return costs scale with return volume like other return costs (assumption).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import config
from .metrics import clean, safe_div


@dataclass(frozen=True)
class ScenarioParams:
    return_reduction: float = 0.0
    logistics_reduction: float = 0.0
    write_off_reduction: float = 0.0
    retained_sale_share: float = 0.65
    prevention_spend: float = 0.0
    category_overrides: dict[str, float] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors = []
        for name, (lo, hi) in config.SCENARIO_LIMITS.items():
            v = getattr(self, name)
            if not (lo <= v <= hi):
                errors.append(f"{name} must be between {lo:.0%} and {hi:.0%} (got {v:.2%})")
        lo, hi = config.SCENARIO_LIMITS["return_reduction"]
        for cat, v in self.category_overrides.items():
            if not (lo <= v <= hi):
                errors.append(f"category override for '{cat}' must be between {lo:.0%} and {hi:.0%}")
        if self.prevention_spend < 0:
            errors.append("prevention_spend cannot be negative")
        return errors


def parse_overrides(text: str | None) -> dict[str, float]:
    """'Footwear:20,Women\\'s Fashion:15' -> {'Footwear': 0.20, ...} (percent inputs)."""
    out: dict[str, float] = {}
    if not text:
        return out
    for part in text.split(","):
        if ":" not in part:
            raise ValueError(f"Invalid category override '{part}'. Use Category:percent")
        name, pct = part.rsplit(":", 1)
        out[name.strip()] = float(pct) / 100.0
    return out


COMPONENTS = ("reverse_logistics", "restocking", "write_off")


def simulate(category_base: pd.DataFrame, params: ScenarioParams, months: int) -> dict:
    """
    category_base: output of metrics.aggregate(lines, 'category') for the filtered data.
    months: number of months in the selected period (for payback).
    """
    df = category_base.copy()
    if df.empty:
        return _empty_result(params)
    r = df["category"].map(params.category_overrides).fillna(params.return_reduction).astype(float)
    l, w, k = params.logistics_reduction, params.write_off_reduction, params.retained_sale_share

    df["r"] = r
    df["sc_reverse_logistics"] = df["reverse_logistics"] * (1 - r) * (1 - l)
    df["sc_restocking"] = df["restocking"] * (1 - r)
    df["sc_write_off"] = df["write_off"] * (1 - r) * (1 - w)
    df["sc_incremental"] = df[["sc_reverse_logistics", "sc_restocking", "sc_write_off"]].sum(axis=1)
    df["volume_savings"] = r * df["incremental_costs"]
    df["efficiency_savings"] = df["reverse_logistics"] * (1 - r) * l + df["write_off"] * (1 - r) * w
    df["gross_savings"] = df["incremental_costs"] - df["sc_incremental"]
    df["retained_margin"] = r * k * (df["refund"] - df["returned_cost"])
    df["avoided_returned_units"] = r * df["returned_units"]
    df["sc_returned_units"] = df["returned_units"] - df["avoided_returned_units"]
    df["sc_unit_return_rate"] = safe_div(df["sc_returned_units"], df["units"])

    base_incr = float(df["incremental_costs"].sum())
    sc_incr = float(df["sc_incremental"].sum())
    gross = base_incr - sc_incr
    retained = float(df["retained_margin"].sum())
    spend = float(params.prevention_spend)
    net = gross + retained - spend
    base_contrib = float(df["contribution_after"].sum())
    monthly_benefit = (gross + retained) / months if months > 0 else 0.0

    components = []
    for comp in COMPONENTS:
        b = float(df[comp].sum())
        s = float(df[f"sc_{comp}"].sum())
        components.append({"key": comp, "baseline": round(b, 2), "scenario": round(s, 2), "savings": round(b - s, 2)})

    base_units = float(df["units"].sum())
    return {
        "params": {
            "return_reduction": params.return_reduction,
            "logistics_reduction": l,
            "write_off_reduction": w,
            "retained_sale_share": k,
            "prevention_spend": spend,
            "category_overrides": params.category_overrides,
        },
        "baseline_incremental_costs": round(base_incr, 2),
        "scenario_incremental_costs": round(sc_incr, 2),
        "gross_cost_savings": round(gross, 2),
        "volume_savings": round(float(df["volume_savings"].sum()), 2),
        "efficiency_savings": round(float(df["efficiency_savings"].sum()), 2),
        "retained_margin": round(retained, 2),
        "prevention_spend": round(spend, 2),
        "net_improvement": round(net, 2),
        "cost_reduction_pct": clean(safe_div(gross, base_incr)),
        "baseline_contribution": round(base_contrib, 2),
        "scenario_contribution": round(base_contrib + net, 2),
        "roi": clean(safe_div(net, spend)) if spend > 0 else None,
        "payback_months": clean(spend / monthly_benefit) if spend > 0 and monthly_benefit > 0 else None,
        "months_in_period": months,
        "baseline_unit_return_rate": clean(safe_div(float(df["returned_units"].sum()), base_units)),
        "scenario_unit_return_rate": clean(safe_div(float(df["sc_returned_units"].sum()), base_units)),
        "avoided_returned_units": round(float(df["avoided_returned_units"].sum()), 1),
        "components": components,
        "by_category": [
            {
                "category": row["category"],
                "return_reduction": clean(row["r"]),
                "baseline_incremental": round(row["incremental_costs"], 2),
                "scenario_incremental": round(row["sc_incremental"], 2),
                "gross_savings": round(row["gross_savings"], 2),
                "retained_margin": round(row["retained_margin"], 2),
                "baseline_unit_return_rate": clean(row["unit_return_rate"]),
                "scenario_unit_return_rate": clean(row["sc_unit_return_rate"]),
            }
            for _, row in df.sort_values("gross_savings", ascending=False).iterrows()
        ],
    }


def preset_params(key: str, baseline_incremental: float) -> ScenarioParams:
    p = config.SCENARIO_PRESETS[key]
    spend = round(baseline_incremental * p["spend_share_of_baseline"], -3)
    return ScenarioParams(
        return_reduction=p["return_reduction"], logistics_reduction=p["logistics_reduction"],
        write_off_reduction=p["write_off_reduction"], retained_sale_share=p["retained_sale_share"],
        prevention_spend=spend,
    )


def _empty_result(params: ScenarioParams) -> dict:
    zero = {k: 0.0 for k in [
        "baseline_incremental_costs", "scenario_incremental_costs", "gross_cost_savings", "volume_savings",
        "efficiency_savings", "retained_margin", "baseline_contribution", "scenario_contribution"]}
    spend = float(params.prevention_spend)
    return {
        "params": {**params.__dict__},
        **zero,
        "prevention_spend": spend,
        "net_improvement": -spend,
        "cost_reduction_pct": None, "roi": None, "payback_months": None, "months_in_period": 0,
        "baseline_unit_return_rate": None, "scenario_unit_return_rate": None, "avoided_returned_units": 0.0,
        "components": [{"key": c, "baseline": 0.0, "scenario": 0.0, "savings": 0.0} for c in COMPONENTS],
        "by_category": [],
    }
