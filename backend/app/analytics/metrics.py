"""
THE central financial metrics engine. Every KPI, chart, table, insight, scenario
and test in the project derives from `summarize()` / `aggregate()` below.

Formulas (all amounts in INR, eligible = non-cancelled order lines):

    GMV                         = Σ quantity × unit_price
    Discount Value              = Σ discount_amount
    Net Merchandise Sales       = GMV − Discounts
    Refund Value                = Σ refunds on Refunded returns
    Net Merchandise Revenue     = Net Merchandise Sales − Refunds
    Gross COGS                  = Σ units delivered × unit_cost
    Returned Inventory (cost)   = Σ refunded units × unit_cost          (reversed out of COGS)
    Net COGS                    = Gross COGS − Returned Inventory
    Contribution BEFORE return costs = Net Merchandise Revenue − Net COGS
    Incremental Return Costs    = Reverse logistics + Restocking/inspection + Inventory write-off
    Contribution AFTER return costs  = Contribution before − Incremental Return Costs
    Recoverable Inventory Value = Returned Inventory (cost) − Inventory write-off
    Return Profit Leakage       = (Refunds − Returned Inventory) + Incremental Return Costs
                                = contribution if no refunded return had happened − actual contribution

Why nothing is double counted:
  * a refund reduces revenue once; it is never part of incremental costs;
  * the cost of a returned unit is removed from COGS once (Returned Inventory) and the
    unrecoverable part is charged once (Inventory write-off).
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from .data_model import ADDITIVE_COLUMNS


def safe_div(num, den):
    """Scalar or vectorised division returning NaN (scalar: None) when the denominator is 0/missing."""
    if den is None or num is None:
        return None
    if np.isscalar(num) and np.isscalar(den):
        try:
            if den is None or den == 0 or (isinstance(den, float) and math.isnan(den)):
                return None
            return float(num) / float(den)
        except (TypeError, ValueError):
            return None
    num = np.asarray(num, dtype=float)
    den = np.asarray(den, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(den != 0, num / np.where(den == 0, 1, den), np.nan)
    return out


def derive(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived measures to a frame that already holds the additive sums."""
    df = df.copy()
    df["net_revenue"] = df["net_sales"] - df["refund"]
    df["net_cogs"] = df["cogs"] - df["returned_cost"]
    df["contribution_before"] = df["net_revenue"] - df["net_cogs"]
    df["incremental_costs"] = df["reverse_logistics"] + df["restocking"] + df["write_off"]
    df["contribution_after"] = df["contribution_before"] - df["incremental_costs"]
    df["recoverable_inventory"] = df["returned_cost"] - df["write_off"]
    df["return_leakage"] = (df["refund"] - df["returned_cost"]) + df["incremental_costs"]
    df["unit_return_rate"] = safe_div(df["returned_units"], df["units"])
    df["contribution_margin"] = safe_div(df["contribution_after"], df["net_revenue"])
    df["contribution_margin_before"] = safe_div(df["contribution_before"], df["net_revenue"])
    df["refund_rate"] = safe_div(df["refund"], df["net_sales"])
    df["incremental_per_returned_unit"] = safe_div(df["incremental_costs"], df["returned_units"])
    if "eligible_orders" in df.columns:
        df["order_return_rate"] = safe_div(df["returned_orders"], df["eligible_orders"])
        df["avg_order_value"] = safe_div(df["net_sales"], df["eligible_orders"])
        df["incremental_per_returned_order"] = safe_div(df["incremental_costs"], df["returned_orders"])
    return df


def aggregate(lines: pd.DataFrame, by: str | list[str]) -> pd.DataFrame:
    """Group order lines and compute every metric per group (vectorised)."""
    by = [by] if isinstance(by, str) else list(by)
    if lines.empty:
        cols = by + ADDITIVE_COLUMNS + ["eligible_orders", "returned_orders", "eligible_lines"]
        return derive(pd.DataFrame(columns=cols).astype({c: float for c in cols if c not in by}))
    sums = lines.groupby(by, observed=True)[ADDITIVE_COLUMNS].sum()
    elig = lines[lines["is_eligible"]]
    sums["eligible_orders"] = elig.groupby(by, observed=True)["order_id"].nunique()
    sums["returned_orders"] = elig[elig["has_refunded_return"]].groupby(by, observed=True)["order_id"].nunique()
    sums["eligible_lines"] = elig.groupby(by, observed=True)["order_line_id"].count()
    sums = sums.fillna({"eligible_orders": 0, "returned_orders": 0, "eligible_lines": 0})
    return derive(sums.reset_index())


def summarize(lines: pd.DataFrame) -> dict[str, Any]:
    """Portfolio-level totals for the (already filtered) order lines."""
    totals = {c: float(lines[c].sum()) if len(lines) else 0.0 for c in ADDITIVE_COLUMNS}
    elig = lines[lines["is_eligible"]] if len(lines) else lines
    totals["eligible_orders"] = int(elig["order_id"].nunique()) if len(lines) else 0
    totals["returned_orders"] = int(elig.loc[elig["has_refunded_return"], "order_id"].nunique()) if len(lines) else 0
    totals["eligible_lines"] = int(len(elig))
    totals["total_lines"] = int(len(lines))
    totals["total_orders"] = int(lines["order_id"].nunique()) if len(lines) else 0
    totals["cancelled_lines"] = int((~lines["is_eligible"]).sum()) if len(lines) else 0
    row = derive(pd.DataFrame([totals])).iloc[0].to_dict()
    return {k: clean(v) for k, v in row.items()}


def clean(v):
    """Convert numpy / NaN values into JSON-safe Python values."""
    if v is None:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else round(f, 6)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, pd.Timestamp):
        return v.date().isoformat()
    return v


def records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> list of JSON-safe dicts."""
    return [{k: clean(v) for k, v in row.items()} for row in df.to_dict(orient="records")]


def bridge_steps(s: dict[str, Any]) -> list[dict]:
    """
    Detailed financial bridge (Profit Leakage page). Each step has a signed value;
    running totals reconcile exactly to Estimated Contribution After Return Costs.
    kind: total | revenue_reduction | cost | recovery | subtotal
    """
    steps = [
        ("gmv", "Gross merchandise value", s["gmv"], "total"),
        ("discount", "Discounts", -s["discount"], "revenue_reduction"),
        ("refund", "Refunds", -s["refund"], "revenue_reduction"),
        ("net_revenue", "Net merchandise revenue", s["net_revenue"], "subtotal"),
        ("cogs", "Cost of goods delivered", -s["cogs"], "cost"),
        ("returned_cost", "Returned inventory (at cost)", s["returned_cost"], "recovery"),
        ("contribution_before", "Contribution before return costs", s["contribution_before"], "subtotal"),
        ("reverse_logistics", "Reverse logistics", -s["reverse_logistics"], "cost"),
        ("restocking", "Restocking & inspection", -s["restocking"], "cost"),
        ("write_off", "Inventory write-offs", -s["write_off"], "cost"),
        ("contribution_after", "Est. contribution after return costs", s["contribution_after"], "total"),
    ]
    return _waterfall(steps)


def anatomy_steps(s: dict[str, Any]) -> list[dict]:
    """Compact 'Return Cost Anatomy' (Overview): COGS shown net of returned inventory."""
    steps = [
        ("gmv", "Merchandise sales (GMV)", s["gmv"], "total"),
        ("discount", "Discounts", -s["discount"], "revenue_reduction"),
        ("refund", "Refunds", -s["refund"], "revenue_reduction"),
        ("net_cogs", "Cost of goods kept (net of returned stock)", -s["net_cogs"], "cost"),
        ("reverse_logistics", "Reverse logistics", -s["reverse_logistics"], "cost"),
        ("restocking", "Restocking & inspection", -s["restocking"], "cost"),
        ("write_off", "Inventory write-offs", -s["write_off"], "cost"),
        ("contribution_after", "Estimated contribution", s["contribution_after"], "total"),
    ]
    return _waterfall(steps)


def _waterfall(steps) -> list[dict]:
    out = []
    running = 0.0
    for key, label, value, kind in steps:
        value = float(value or 0.0)
        if kind in ("total", "subtotal"):
            start, end = 0.0, value
            running = value
        else:
            start = running
            running = running + value
            end = running
        out.append({"key": key, "label": label, "value": round(value, 2), "kind": kind,
                    "start": round(start, 2), "end": round(end, 2)})
    return out
