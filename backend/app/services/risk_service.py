"""Return Risk Analysis page + high-risk order table service."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..analytics import config
from ..analytics.data_model import AnalyticsModel
from ..analytics.filters import Filters, apply
from ..analytics.metrics import clean, records, summarize
from ..analytics.risk import describe_model
from .common import (DELAY_BANDS, DISCOUNT_BANDS, VALUE_BANDS, BadRequestError, band, meta, paginate,
                     rate_table, sort_frame, text_search)

BAND_ORDER = ["Low", "Medium", "High"]
RETURN_STATUS_VALUES = ["Returned", "Return in progress", "Return rejected", "Window open", "Not returned"]

ORDER_TABLE_COLUMNS = [
    "order_id", "order_line_id", "order_date", "product_id", "product_name", "category", "shipping_region",
    "sales_channel", "payment_method", "quantity", "line_net_value", "discount_pct", "shipping_delay_days",
    "risk_score", "risk_band", "top_factors", "risk_exposure", "actual_return_status",
    "product_hist_rate", "category_hist_rate",
] + [f"pts_{k}" for k in config.RISK_WEIGHTS]

SORTABLE = {"order_date", "line_net_value", "discount_pct", "shipping_delay_days", "risk_score", "risk_exposure",
            "order_id", "category", "shipping_region", "product_name"}


def build(model: AnalyticsModel, f: Filters) -> dict:
    lines = apply(model.lines, f)
    elig = lines[lines["is_eligible"]]
    s = summarize(lines)
    high = elig[elig["risk_band"] == "High"]

    hist = []
    if len(elig):
        bins = np.arange(0, 105, 5)
        idx = np.clip((elig["risk_score"].to_numpy() // 5).astype(int), 0, 19)
        counts = np.bincount(idx, minlength=20)
        ret = np.bincount(idx, weights=elig["has_refunded_return"].to_numpy(float), minlength=20)
        for i in range(20):
            lo = int(bins[i])
            hist.append({
                "bin_start": lo, "bin_end": lo + 5, "lines": int(counts[i]), "returned_lines": int(ret[i]),
                "band": "High" if lo >= config.HIGH_THRESHOLD else "Medium" if lo >= config.MEDIUM_THRESHOLD else "Low",
            })

    by_band = []
    for b in BAND_ORDER:
        g = elig[elig["risk_band"] == b]
        units = float(g["units"].sum())
        by_band.append({
            "band": b, "lines": int(len(g)), "orders": int(g["order_id"].nunique()), "units": units,
            "returned_units": float(g["returned_units"].sum()),
            "unit_return_rate": clean(g["returned_units"].sum() / units) if units else None,
            "avg_score": clean(g["risk_score"].mean()) if len(g) else None,
            "exposure": clean(g["risk_exposure"].sum()),
        })

    # scatter: all high-risk lines (capped) + a deterministic random sample of the rest
    scatter = pd.DataFrame()
    if len(elig):
        hi = elig[elig["risk_band"] == "High"].nlargest(250, "risk_exposure")
        rest = elig[elig["risk_band"] != "High"]
        rest = rest.sample(n=min(len(rest), 450), random_state=7) if len(rest) else rest
        scatter = pd.concat([hi, rest])[["order_line_id", "order_id", "product_name", "category", "risk_score",
                                         "risk_exposure", "risk_band", "actual_return_status"]]

    rx = apply(model.returns_x, f)
    processed = rx[rx["return_status"] != config.PENDING]
    reasons = []
    if len(processed):
        rg = processed.groupby("return_reason").agg(returns=("return_id", "count"), units=("return_quantity", "sum"),
                                                     refund=("refund_amount", "sum")).sort_values("units", ascending=False)
        rg["share"] = rg["units"] / rg["units"].sum()
        reasons = records(rg.reset_index().rename(columns={"return_reason": "reason"}))
    reason_matrix = []
    if len(processed):
        m = processed.pivot_table(index="category", columns="return_reason", values="return_quantity",
                                  aggfunc="sum", fill_value=0)
        for cat, row in m.iterrows():
            tot = float(row.sum())
            reason_matrix.append({"category": cat, "total": tot,
                                  "reasons": {k: clean(v / tot) if tot else 0 for k, v in row.items()}})

    return {
        "meta": meta(model, f, len(elig)),
        "kpis": {
            "eligible_orders": s["eligible_orders"],
            "returned_orders": s["returned_orders"],
            "order_return_rate": s.get("order_return_rate"),
            "unit_return_rate": s.get("unit_return_rate"),
            "eligible_lines": s["eligible_lines"],
            "high_risk_orders": int(high["order_id"].nunique()),
            "high_risk_lines": int(len(high)),
            "high_risk_exposure": clean(high["risk_exposure"].sum()),
            "high_risk_value": clean(high["line_net_value"].sum()),
            "high_band_observed_rate": next((b["unit_return_rate"] for b in by_band if b["band"] == "High"), None),
        },
        "score_distribution": hist,
        "by_band": by_band,
        "by_category": rate_table(lines, "category"),
        "by_discount": rate_table(lines, band(lines["discount_pct"], DISCOUNT_BANDS), DISCOUNT_BANDS[1]),
        "by_delay": rate_table(lines, band(lines["shipping_delay_days"], DELAY_BANDS), DELAY_BANDS[1]),
        "by_value": rate_table(lines, band(lines["line_net_value"], VALUE_BANDS), VALUE_BANDS[1]),
        "by_payment": rate_table(lines, "payment_method"),
        "scatter": records(scatter),
        "reasons": reasons,
        "reason_matrix": reason_matrix,
        "model": describe_model(),
        "band_return_rates": {k: clean(v) for k, v in model.band_return_rates.items()},
        "notes": [
            "Historical assessment: scores are recomputed for past orders using only information available "
            "at the time; they are not prospective predictions.",
            "Observed return rates by band are measured on this synthetic dataset and are not validated accuracy.",
        ],
    }


def order_table(model: AnalyticsModel, f: Filters, bands: tuple[str, ...], statuses: tuple[str, ...],
                search: str | None, sort_by: str | None, sort_dir: str) -> pd.DataFrame:
    for b in bands:
        if b not in BAND_ORDER:
            raise BadRequestError(f"Unknown risk band '{b}'. Use Low, Medium or High.")
    for st in statuses:
        if st not in RETURN_STATUS_VALUES:
            raise BadRequestError(f"Unknown return status '{st}'. Use one of: {', '.join(RETURN_STATUS_VALUES)}")
    lines = apply(model.lines, f)
    df = lines[lines["is_eligible"]]
    if bands:
        df = df[df["risk_band"].isin(bands)]
    if statuses:
        df = df[df["actual_return_status"].isin(statuses)]
    df = text_search(df, search, ["order_id", "order_line_id", "product_name", "product_id"])
    df = sort_frame(df, sort_by, sort_dir, SORTABLE, "risk_score")
    out = df[ORDER_TABLE_COLUMNS].copy()
    out["order_date"] = out["order_date"].dt.strftime("%Y-%m-%d")
    return out


def order_page(model, f, bands, statuses, search, sort_by, sort_dir, page, page_size) -> dict:
    df = order_table(model, f, bands, statuses, search, sort_by, sort_dir)
    return {"meta": meta(model, f, len(df)), **paginate(df, page, page_size)}
