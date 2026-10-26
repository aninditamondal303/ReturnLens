"""
Builds the analytical model from the four raw tables.

The central object is `lines`: one row per order line (the grain of orders.csv),
enriched with product and customer attributes and with *line-level aggregates of
its returns*. Every additive financial measure is pre-computed per line here,
so every page, chart and test aggregates the very same columns.

Accounting conventions:
  * Cancelled lines are not sales: all their financial columns are zero.
  * Merchandise metrics exclude customer shipping fees.
  * Only `Refunded` returns move units, refunds and inventory recovery.
  * `Rejected` returns still incur reverse-logistics and inspection costs.
  * `Pending` returns have no financial effect yet.
  * Returns are attributed to the month of the ORIGINAL ORDER (cohort view), so a
    filtered period always pairs returns with the sales that caused them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from . import config

ADDITIVE_COLUMNS = [
    "gmv", "discount", "net_sales", "units", "cogs",
    "returned_units", "refund", "returned_cost",
    "reverse_logistics", "restocking", "write_off",
    "rejected_units", "pending_units",
]


@dataclass
class AnalyticsModel:
    orders: pd.DataFrame
    returns: pd.DataFrame
    products: pd.DataFrame
    customers: pd.DataFrame
    lines: pd.DataFrame
    returns_x: pd.DataFrame
    snapshot_date: date
    period_start: date
    period_end: date
    category_median_price: dict = field(default_factory=dict)
    band_return_rates: dict = field(default_factory=dict)
    category_incremental_per_unit: dict = field(default_factory=dict)


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0.0).astype(float)


def _dates(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.astype("object").where(s.notna() & (s.astype(str).str.strip() != ""), None), errors="coerce")


def build_model(orders: pd.DataFrame, returns: pd.DataFrame, products: pd.DataFrame,
                customers: pd.DataFrame, snapshot_date: date | None = None,
                with_risk: bool = True) -> AnalyticsModel:
    o = orders.copy()
    r = returns.copy()
    p = products.copy()
    c = customers.copy()

    for col in ["quantity"]:
        o[col] = pd.to_numeric(o[col], errors="coerce").fillna(0).astype(int)
    for col in ["unit_price", "discount_amount", "shipping_fee"]:
        o[col] = _num(o[col])
    for col in ["unit_cost", "selling_price", "product_weight"]:
        p[col] = _num(p[col])
    p["return_window_days"] = pd.to_numeric(p["return_window_days"], errors="coerce").fillna(7).astype(int)
    r["return_quantity"] = pd.to_numeric(r["return_quantity"], errors="coerce").fillna(0).astype(int)
    for col in ["refund_amount", "reverse_logistics_cost", "restocking_cost", "inventory_write_off"]:
        r[col] = _num(r[col])

    o["order_date"] = _dates(o["order_date"])
    o["promised_delivery_date"] = _dates(o["promised_delivery_date"])
    o["actual_delivery_date"] = _dates(o["actual_delivery_date"])
    r["return_date"] = _dates(r["return_date"])

    lines = o.merge(
        p[["product_id", "product_name", "category", "subcategory", "unit_cost", "selling_price",
           "supplier_id", "product_weight", "return_window_days"]],
        on="product_id", how="left",
    ).merge(
        c[["customer_id", "customer_segment", "historical_order_count_band", "signup_date"]],
        on="customer_id", how="left",
    )
    lines["month"] = lines["order_date"].dt.strftime("%Y-%m")
    lines["is_eligible"] = lines["order_status"] != config.CANCELLED_STATUS
    elig = lines["is_eligible"].astype(float)

    gross = lines["quantity"] * lines["unit_price"]
    lines["gross_value"] = gross
    lines["gmv"] = gross * elig
    lines["discount"] = lines["discount_amount"] * elig
    lines["net_sales"] = lines["gmv"] - lines["discount"]
    lines["units"] = lines["quantity"] * elig
    lines["cogs"] = lines["units"] * lines["unit_cost"]
    lines["line_net_value"] = gross - lines["discount_amount"]
    lines["discount_pct"] = np.where(gross > 0, lines["discount_amount"] / gross, 0.0)
    lines["net_unit_price"] = np.where(lines["quantity"] > 0, lines["line_net_value"] / lines["quantity"], 0.0)
    lines["shipping_delay_days"] = (lines["actual_delivery_date"] - lines["promised_delivery_date"]).dt.days

    # ---- line-level return aggregates (no double counting: one row per line) ----
    refunded = r[r["return_status"] == config.PROCESSED_REFUND]
    rejected = r[r["return_status"] == config.REJECTED]
    pending = r[r["return_status"] == config.PENDING]
    agg_ref = refunded.groupby("order_line_id").agg(
        returned_units=("return_quantity", "sum"), refund=("refund_amount", "sum"))
    agg_cost = r.groupby("order_line_id").agg(
        reverse_logistics=("reverse_logistics_cost", "sum"), restocking=("restocking_cost", "sum"),
        write_off=("inventory_write_off", "sum"))
    agg_rej = rejected.groupby("order_line_id").agg(rejected_units=("return_quantity", "sum"))
    agg_pen = pending.groupby("order_line_id").agg(pending_units=("return_quantity", "sum"))
    first_return = r.sort_values("return_date").groupby("order_line_id").agg(
        first_return_date=("return_date", "first"), primary_reason=("return_reason", "first"))
    for agg in (agg_ref, agg_cost, agg_rej, agg_pen, first_return):
        lines = lines.merge(agg, left_on="order_line_id", right_index=True, how="left")
    for col in ["returned_units", "refund", "reverse_logistics", "restocking", "write_off", "rejected_units", "pending_units"]:
        lines[col] = lines[col].fillna(0.0).astype(float)
    lines["returned_cost"] = lines["returned_units"] * lines["unit_cost"]
    lines["has_refunded_return"] = lines["returned_units"] > 0

    snap = snapshot_date or _infer_snapshot(lines, r)
    snap_ts = pd.Timestamp(snap)
    days_since_delivery = (snap_ts - lines["actual_delivery_date"]).dt.days
    window_open = lines["is_eligible"] & (days_since_delivery < lines["return_window_days"])
    lines["return_window_open"] = window_open.fillna(False)
    lines["actual_return_status"] = np.select(
        [~lines["is_eligible"], lines["has_refunded_return"], lines["pending_units"] > 0,
         lines["rejected_units"] > 0, lines["return_window_open"]],
        ["Cancelled", "Returned", "Return in progress", "Return rejected", "Window open"],
        default="Not returned",
    )

    # ---- customer type: first order in the dataset by a customer with no prior history ----
    first_order = lines.groupby("customer_id")["order_date"].transform("min")
    lines["customer_type"] = np.where(
        (lines["order_date"] == first_order) & (lines["historical_order_count_band"].astype(str) == "0"),
        "New", "Repeat",
    )

    category_median_price = p.groupby("category")["selling_price"].median().to_dict()
    lines["value_ratio"] = lines["line_net_value"] / lines["category"].map(category_median_price)

    returns_x = r.merge(
        lines[["order_line_id", "order_date", "month", "category", "subcategory", "product_name",
               "supplier_id", "shipping_region", "shipping_zone", "sales_channel", "payment_method",
               "customer_id", "customer_segment", "unit_cost", "quantity", "shipping_delay_days"]],
        on="order_line_id", how="left",
    )

    model = AnalyticsModel(
        orders=o, returns=r, products=p, customers=c, lines=lines, returns_x=returns_x,
        snapshot_date=snap,
        period_start=lines["order_date"].min().date(),
        period_end=lines["order_date"].max().date(),
        category_median_price=category_median_price,
    )
    if with_risk:
        from .risk import attach_risk_scores  # local import avoids a cycle

        attach_risk_scores(model)
    return model


def _infer_snapshot(lines: pd.DataFrame, returns: pd.DataFrame) -> date:
    """Latest known event (delivery or return) — used when no snapshot is supplied."""
    candidates = [lines["actual_delivery_date"].max(), returns["return_date"].max() if len(returns) else pd.NaT]
    valid = [d for d in candidates if pd.notna(d)]
    return (max(valid) if valid else lines["order_date"].max()).date()
