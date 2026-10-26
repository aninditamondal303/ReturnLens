"""Product Intelligence page: product table, spotlights, scatter and product detail."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..analytics import config
from ..analytics.data_model import AnalyticsModel
from ..analytics.filters import Filters, apply
from ..analytics.metrics import aggregate, clean, records, summarize
from .common import NotFoundError, meta, paginate, sort_frame, text_search

PRODUCT_COLUMNS = ["product_id", "product_name", "category", "subcategory", "supplier_id", "product_status",
                   "units", "returned_units", "gmv", "net_sales", "unit_return_rate", "refund", "incremental_costs",
                   "contribution_after", "contribution_margin", "return_leakage", "avg_risk_score", "risk_indicator"]
SORTABLE = {"product_id", "product_name", "category", "units", "returned_units", "gmv", "unit_return_rate", "refund",
            "incremental_costs", "contribution_after", "contribution_margin", "return_leakage", "avg_risk_score"}
MIN_UNITS_FOR_RATE = 30


def product_frame(model: AnalyticsModel, lines: pd.DataFrame) -> pd.DataFrame:
    """Per-product metrics + documented risk indicator."""
    if lines.empty:
        return pd.DataFrame(columns=PRODUCT_COLUMNS)
    p = aggregate(lines, "product_id")
    p = p[p["units"] > 0]
    info = model.products.set_index("product_id")[["product_name", "category", "subcategory", "supplier_id",
                                                   "product_status"]]
    p = p.join(info, on="product_id")
    elig = lines[lines["is_eligible"]]
    p["avg_risk_score"] = p["product_id"].map(elig.groupby("product_id")["risk_score"].mean())
    portfolio = summarize(lines)
    p["risk_indicator"] = risk_indicator(p, portfolio.get("unit_return_rate") or 0,
                                         portfolio.get("contribution_margin") or 0)
    return p


def risk_indicator(p: pd.DataFrame, portfolio_rate: float, portfolio_margin: float) -> np.ndarray:
    """
    High     : contribution after return costs < 0, or return rate >= 2x portfolio rate (min 30 units)
    Elevated : return rate >= 1.3x portfolio rate (min 30 units), or margin < half of portfolio margin
    Normal   : otherwise
    """
    enough = p["units"] >= MIN_UNITS_FOR_RATE
    rate = p["unit_return_rate"].fillna(0)
    margin = p["contribution_margin"].fillna(0)
    high = (p["contribution_after"] < 0) | (enough & (rate >= 2 * portfolio_rate))
    elevated = (enough & (rate >= 1.3 * portfolio_rate)) | (margin < 0.5 * portfolio_margin)
    return np.select([high, elevated], ["High", "Elevated"], "Normal")


def build(model: AnalyticsModel, f: Filters) -> dict:
    lines = apply(model.lines, f)
    p = product_frame(model, lines)
    rx = apply(model.returns_x, f)
    processed = rx[rx["return_status"] != config.PENDING]

    def top(df, col, n=6, asc=False):
        return records(df.sort_values(col, ascending=asc).head(n)[
            ["product_id", "product_name", "category", "gmv", "units", "unit_return_rate", "incremental_costs",
             "contribution_after", "contribution_margin"]])

    damage = processed[processed["return_reason"].isin(config.DAMAGE_REASONS)]
    dmg = (damage.groupby(["product_id", "product_name", "category"])
           .agg(damage_units=("return_quantity", "sum"), write_off=("inventory_write_off", "sum"))
           .reset_index().sort_values("damage_units", ascending=False).head(6)) if len(damage) else pd.DataFrame()

    reason_focus = []
    for reason in config.SIZE_QUALITY_MISMATCH_REASONS:
        sub = processed[processed["return_reason"] == reason]
        if sub.empty:
            continue
        g = sub.groupby(["product_id", "product_name", "category"])["return_quantity"].sum().reset_index()
        totals = processed.groupby("product_id")["return_quantity"].sum()
        g["share_of_product_returns"] = g["return_quantity"] / g["product_id"].map(totals)
        g = g[g["return_quantity"] >= 3].sort_values("return_quantity", ascending=False).head(4)
        reason_focus.append({"reason": reason, "products": records(g.rename(columns={"return_quantity": "units"}))})

    enough = p[p["units"] >= MIN_UNITS_FOR_RATE] if len(p) else p
    return {
        "meta": meta(model, f, len(p)),
        "counts": {
            "products": int(len(p)),
            "negative_contribution": int((p["contribution_after"] < 0).sum()) if len(p) else 0,
            "high_risk_indicator": int((p["risk_indicator"] == "High").sum()) if len(p) else 0,
        },
        "spotlights": {
            "top_sales": top(p, "gmv") if len(p) else [],
            "highest_return_rate": top(enough, "unit_return_rate") if len(enough) else [],
            "highest_incremental_costs": top(p, "incremental_costs") if len(p) else [],
            "negative_contribution": top(p[p["contribution_after"] < 0], "contribution_after", n=10, asc=True) if len(p) else [],
            "damage_returns": records(dmg),
            "reason_focus": reason_focus,
        },
        "scatter": records(p[["product_id", "product_name", "category", "gmv", "unit_return_rate", "contribution_after",
                              "contribution_margin", "units", "risk_indicator"]]) if len(p) else [],
        "min_units_for_rate": MIN_UNITS_FOR_RATE,
    }


def table(model, f, category: str | None, search, sort_by, sort_dir, risk: str | None = None) -> pd.DataFrame:
    lines = apply(model.lines, f)
    p = product_frame(model, lines)
    if category:
        p = p[p["category"] == category]
    if risk:
        p = p[p["risk_indicator"] == risk]
    p = text_search(p, search, ["product_id", "product_name", "subcategory", "supplier_id"])
    p = sort_frame(p, sort_by, sort_dir, SORTABLE, "gmv")
    return p[PRODUCT_COLUMNS]


def table_page(model, f, category, search, sort_by, sort_dir, page, page_size, risk=None) -> dict:
    df = table(model, f, category, search, sort_by, sort_dir, risk)
    return {"meta": meta(model, f, len(df)), **paginate(df, page, page_size)}


def detail(model: AnalyticsModel, f: Filters, product_id: str) -> dict:
    prod = model.products[model.products["product_id"] == product_id]
    if prod.empty:
        raise NotFoundError(f"Unknown product '{product_id}'")
    info = prod.iloc[0]
    lines = apply(model.lines, f)
    pl = lines[lines["product_id"] == product_id]
    cl = lines[lines["category"] == info["category"]]
    ps, cs = summarize(pl), summarize(cl)
    cat_products = int(cl.loc[cl["units"] > 0, "product_id"].nunique()) or 1

    monthly = aggregate(pl, "month").sort_values("month") if len(pl) else aggregate(pl, "month")
    rx = apply(model.returns_x, f)
    pr = rx[(rx["product_id"] == product_id) & (rx["return_status"] != config.PENDING)]
    reasons = (pr.groupby("return_reason").agg(units=("return_quantity", "sum"), returns=("return_id", "count"))
               .reset_index().sort_values("units", ascending=False)) if len(pr) else pd.DataFrame()
    conditions = (pr.groupby("item_condition").agg(units=("return_quantity", "sum"), write_off=("inventory_write_off", "sum"))
                  .reset_index().sort_values("units", ascending=False)) if len(pr) else pd.DataFrame()

    def pick(s):
        keys = ["gmv", "units", "returned_units", "unit_return_rate", "refund", "reverse_logistics", "restocking",
                "write_off", "incremental_costs", "contribution_before", "contribution_after", "contribution_margin",
                "return_leakage", "recoverable_inventory", "net_revenue", "discount", "order_return_rate"]
        return {k: s.get(k) for k in keys}

    cat_avg = pick(cs)
    for k in ["gmv", "units", "returned_units", "refund", "reverse_logistics", "restocking", "write_off",
              "incremental_costs", "contribution_before", "contribution_after", "return_leakage",
              "recoverable_inventory", "net_revenue", "discount"]:
        cat_avg[k] = clean((cs.get(k) or 0) / cat_products)

    return {
        "meta": meta(model, f, len(pl)),
        "product": {
            "product_id": product_id, "product_name": info["product_name"], "category": info["category"],
            "subcategory": info["subcategory"], "supplier_id": info["supplier_id"],
            "product_status": info["product_status"], "selling_price": clean(info["selling_price"]),
            "unit_cost": clean(info["unit_cost"]), "return_window_days": int(info["return_window_days"]),
        },
        "metrics": pick(ps),
        "category_average": cat_avg,
        "category_products": cat_products,
        "monthly": records(monthly[["month", "units", "returned_units", "unit_return_rate", "gmv", "refund",
                                    "incremental_costs", "contribution_after"]]) if len(monthly) else [],
        "reasons": records(reasons),
        "conditions": records(conditions),
        "avg_risk_score": clean(pl.loc[pl["is_eligible"], "risk_score"].mean()) if len(pl) else None,
    }
