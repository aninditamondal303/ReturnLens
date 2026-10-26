"""Profit Leakage page: KPIs, financial bridge, category table and drill-down."""
from __future__ import annotations

import pandas as pd

from ..analytics.data_model import AnalyticsModel
from ..analytics.filters import Filters, apply
from ..analytics.metrics import aggregate, bridge_steps, records, summarize
from .common import NotFoundError, meta, paginate, sort_frame, text_search

TABLE_COLUMNS = ["gmv", "discount", "net_sales", "refund", "cogs", "returned_cost", "reverse_logistics", "restocking", "write_off",
                 "incremental_costs", "contribution_before", "contribution_after", "contribution_margin",
                 "unit_return_rate", "order_return_rate", "return_leakage", "units", "returned_units", "net_revenue",
                 "recoverable_inventory"]


def flag_rows(df: pd.DataFrame, portfolio_margin: float | None, share_col: str = "gmv") -> pd.DataFrame:
    """Add 'negative_contribution' and 'weak_contribution' (high sales, margin < half of portfolio) flags."""
    df = df.copy()
    total = float(df[share_col].sum()) or 1.0
    df["gmv_share"] = df[share_col] / total
    median_share = float(df["gmv_share"].median()) if len(df) else 0.0
    pm = portfolio_margin or 0.0
    df["negative_contribution"] = df["contribution_after"] < 0
    df["weak_contribution"] = (~df["negative_contribution"]) & (df["gmv_share"] >= median_share) & (
        df["contribution_margin"].fillna(0) < pm * 0.5)
    return df


def build(model: AnalyticsModel, f: Filters) -> dict:
    lines = apply(model.lines, f)
    s = summarize(lines)
    cats = aggregate(lines, "category")
    cats = cats[cats["units"] > 0]
    cats = flag_rows(cats, s.get("contribution_margin")).sort_values("return_leakage", ascending=False)
    prods = aggregate(lines, ["product_id", "product_name", "category"])
    prods = prods[prods["units"] > 0]
    negative = prods[prods["contribution_after"] < 0].sort_values("contribution_after")
    return {
        "meta": meta(model, f, len(lines)),
        "summary": s,
        "bridge": bridge_steps(s),
        "categories": records(cats[["category", "gmv_share", "negative_contribution", "weak_contribution"] + TABLE_COLUMNS]),
        "negative_products": records(negative[["product_id", "product_name", "category", "gmv", "unit_return_rate",
                                               "contribution_after", "incremental_costs"]].head(15)),
        "negative_product_count": int(len(negative)),
        "reconciliation": {
            # "+ 0.0" normalises -0.0 so a passing check never displays as "-0.00"
            "net_revenue_check": round(s["gmv"] - s["discount"] - s["refund"] - s["net_revenue"], 2) + 0.0,
            "contribution_check": round(
                s["net_revenue"] - s["cogs"] + s["returned_cost"] - s["incremental_costs"] - s["contribution_after"], 2) + 0.0,
            "category_sum_check": round(float(cats["contribution_after"].sum()) - s["contribution_after"], 2) + 0.0,
            "note": "All checks should be 0.00: the bridge, totals and category table come from the same engine.",
        },
    }


def category_products(model: AnalyticsModel, f: Filters, category: str) -> dict:
    if category not in set(model.products["category"]):
        raise NotFoundError(f"Unknown category '{category}'")
    lines = apply(model.lines, f)
    lines = lines[lines["category"] == category]
    s = summarize(lines)
    prods = aggregate(lines, ["product_id", "product_name", "subcategory"])
    prods = prods[prods["units"] > 0]
    prods = flag_rows(prods, s.get("contribution_margin")).sort_values("return_leakage", ascending=False)
    return {
        "meta": meta(model, f, len(lines)),
        "category": category,
        "summary": s,
        "products": records(prods[["product_id", "product_name", "subcategory", "gmv_share", "negative_contribution",
                                   "weak_contribution"] + TABLE_COLUMNS]),
    }


LINE_COLUMNS = ["order_id", "order_line_id", "order_date", "customer_id", "product_id", "product_name", "category",
                "shipping_region", "sales_channel", "payment_method", "quantity", "unit_price", "discount",
                "net_sales", "refund", "returned_units", "reverse_logistics", "restocking", "write_off",
                "order_status", "actual_return_status", "risk_score", "risk_band", "primary_reason"]
LINE_SORTABLE = {"order_date", "net_sales", "refund", "risk_score", "order_id", "quantity", "discount"}


def order_lines_frame(model: AnalyticsModel, f: Filters, product_id: str | None, search: str | None,
                      sort_by: str | None, sort_dir: str, returned_only: bool = False) -> pd.DataFrame:
    lines = apply(model.lines, f)
    if product_id:
        if product_id not in set(model.products["product_id"]):
            raise NotFoundError(f"Unknown product '{product_id}'")
        lines = lines[lines["product_id"] == product_id]
    if returned_only:
        lines = lines[(lines["returned_units"] > 0) | (lines["rejected_units"] > 0) | (lines["pending_units"] > 0)]
    lines = text_search(lines, search, ["order_id", "order_line_id", "product_name", "customer_id"])
    lines = sort_frame(lines, sort_by, sort_dir, LINE_SORTABLE, "order_date")
    out = lines[LINE_COLUMNS].copy()
    out["order_date"] = out["order_date"].dt.strftime("%Y-%m-%d")
    out["primary_reason"] = out["primary_reason"].fillna("")
    return out


def order_lines_page(model, f, product_id, search, sort_by, sort_dir, page, page_size, returned_only=False) -> dict:
    df = order_lines_frame(model, f, product_id, search, sort_by, sort_dir, returned_only)
    return {"meta": meta(model, f, len(df)), **paginate(df, page, page_size)}
