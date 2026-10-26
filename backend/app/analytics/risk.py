"""
Transparent, rule-based HEURISTIC return-risk score (0-100).

This is NOT a trained model and NOT a probability. It ranks order lines by how
many well-known return drivers are present, using only information that was
available at the prediction point:

  prediction point = the moment the order line is delivered
                     (so the shipping delay is known; the return has not happened)

Leakage controls
  * Product / category return history counts only returns that were initiated
    at least HISTORY_LAG_DAYS before the scored order was placed, and only units
    delivered before that date. The current order and all later orders are excluded.
  * Return reason, return status, item condition, refunds and write-offs are never
    used as inputs.
  * Order value is compared with the *catalogue* median list price of the category
    (a pre-existing reference), not with outcome data.

Exposure (an ESTIMATE, not a loss):
  exposure = band historical return rate × (forgone margin + expected incremental cost)
  where band rate = observed unit return rate of the line's risk band over the full
  history (in-sample, illustrative) and expected incremental cost = category average
  incremental return cost per returned unit × quantity.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def _cum_before(event_dates: np.ndarray, event_values: np.ndarray, query_dates: np.ndarray) -> np.ndarray:
    """Sum of event_values whose event_date is strictly before each query date."""
    if len(event_dates) == 0:
        return np.zeros(len(query_dates))
    order = np.argsort(event_dates, kind="stable")
    ed = event_dates[order]
    cv = np.cumsum(event_values[order])
    idx = np.searchsorted(ed, query_dates, side="left")
    return np.where(idx > 0, cv[np.maximum(idx - 1, 0)], 0.0)


def historical_rates(lines: pd.DataFrame, returns: pd.DataFrame, key: str) -> tuple[np.ndarray, np.ndarray]:
    """
    For every line, (returned units known before order_date, delivered units before order_date)
    for the same `key` (product_id or category). Pure point-in-time computation.
    """
    out_ret = np.zeros(len(lines))
    out_del = np.zeros(len(lines))
    q_dates = lines["order_date"].to_numpy(dtype="datetime64[ns]")
    elig = lines[lines["is_eligible"] & lines["actual_delivery_date"].notna()]
    refunded = returns.loc[returns["return_status"] == config.PROCESSED_REFUND,
                           ["order_line_id", "return_date", "return_quantity"]].merge(
        lines[["order_line_id", key]], on="order_line_id", how="left")
    known = (refunded["return_date"] + pd.Timedelta(days=config.HISTORY_LAG_DAYS)).to_numpy(dtype="datetime64[ns]")
    refunded = refunded.assign(_known=known)

    del_groups = {k: g for k, g in elig.groupby(key, observed=True)}
    ret_groups = {k: g for k, g in refunded.groupby(key, observed=True)}
    pos = {k: np.flatnonzero(lines[key].to_numpy() == k) for k in lines[key].unique()}
    for k, idx in pos.items():
        g = del_groups.get(k)
        if g is not None:
            out_del[idx] = _cum_before(g["actual_delivery_date"].to_numpy(dtype="datetime64[ns]"),
                                       g["quantity"].to_numpy(dtype=float), q_dates[idx])
        gr = ret_groups.get(k)
        if gr is not None:
            out_ret[idx] = _cum_before(gr["_known"].to_numpy(dtype="datetime64[ns]"),
                                       gr["return_quantity"].to_numpy(dtype=float), q_dates[idx])
    return out_ret, out_del


def _scale(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return np.clip((x - lo) / (hi - lo), 0.0, 1.0)


def score_features(features: pd.DataFrame) -> pd.DataFrame:
    """
    Turn raw pre-return features into factor points and a 0-100 score.
    Expected columns: product_hist_rate, category_hist_rate, discount_pct,
    shipping_delay_days, value_ratio, payment_method, quantity.
    """
    w, sc = config.RISK_WEIGHTS, config.RISK_SCALES
    f = pd.DataFrame(index=features.index)
    f["product_history"] = _scale(features["product_hist_rate"].to_numpy(float), *sc["product_history"])
    f["category_history"] = _scale(features["category_hist_rate"].to_numpy(float), *sc["category_history"])
    f["discount"] = _scale(features["discount_pct"].to_numpy(float), *sc["discount"])
    delay = features["shipping_delay_days"].fillna(0).clip(lower=0).to_numpy(float)
    f["shipping_delay"] = _scale(delay, *sc["shipping_delay"])
    f["order_value"] = _scale(features["value_ratio"].fillna(1.0).to_numpy(float), *sc["order_value"])
    f["cash_on_delivery"] = (features["payment_method"] == "Cash on Delivery").astype(float).to_numpy()
    f["multi_unit"] = (features["quantity"] >= 2).astype(float).to_numpy()
    pts = pd.DataFrame({f"pts_{k}": f[k] * w[k] for k in w}, index=features.index)
    pts["risk_score"] = pts.sum(axis=1).round(1).clip(0, 100)
    pts["risk_band"] = band_for(pts["risk_score"])
    return pts


def band_for(score: pd.Series) -> pd.Series:
    return pd.Series(
        np.select([score >= config.HIGH_THRESHOLD, score >= config.MEDIUM_THRESHOLD], ["High", "Medium"], "Low"),
        index=score.index,
    )


def attach_risk_scores(model) -> None:
    """Compute leakage-free features, score, band rates and exposure; add them to model.lines."""
    lines = model.lines
    r_c, d_c = historical_rates(lines, model.returns, "category")
    r_p, d_p = historical_rates(lines, model.returns, "product_id")
    prior = config.GLOBAL_PRIOR_RETURN_RATE
    cat_rate = (r_c + config.CATEGORY_SMOOTHING_UNITS * prior) / (d_c + config.CATEGORY_SMOOTHING_UNITS)
    prod_rate = (r_p + config.PRODUCT_SMOOTHING_UNITS * cat_rate) / (d_p + config.PRODUCT_SMOOTHING_UNITS)

    feats = pd.DataFrame({
        "product_hist_rate": prod_rate,
        "category_hist_rate": cat_rate,
        "discount_pct": lines["discount_pct"].to_numpy(float),
        "shipping_delay_days": lines["shipping_delay_days"],
        "value_ratio": lines["value_ratio"],
        "payment_method": lines["payment_method"],
        "quantity": lines["quantity"],
    }, index=lines.index)
    pts = score_features(feats)
    for col in pts.columns:
        lines[col] = pts[col]
    lines["product_hist_rate"] = prod_rate
    lines["category_hist_rate"] = cat_rate
    lines["product_hist_units"] = d_p
    # Cancelled lines are never scored (no delivery, nothing to return).
    lines.loc[~lines["is_eligible"], ["risk_score"]] = np.nan
    lines.loc[~lines["is_eligible"], "risk_band"] = "Not scored"
    lines["top_factors"] = _top_factors(lines)

    # ----- exposure -----
    elig = lines[lines["is_eligible"]]
    band_units = elig.groupby("risk_band")["units"].sum()
    band_ret = elig.groupby("risk_band")["returned_units"].sum()
    band_rate = (band_ret / band_units.replace(0, np.nan)).fillna(0.0).to_dict()
    cat_units_ret = elig.groupby("category")["returned_units"].sum()
    cat_incr = elig.groupby("category")[["reverse_logistics", "restocking", "write_off"]].sum().sum(axis=1)
    cat_incr_per_unit = (cat_incr / cat_units_ret.replace(0, np.nan)).fillna(0.0).to_dict()
    margin_per_unit = (lines["net_unit_price"] - lines["unit_cost"]).clip(lower=0)
    cost_if_returned = lines["quantity"] * (margin_per_unit + lines["category"].map(cat_incr_per_unit).fillna(0.0))
    lines["band_return_rate"] = lines["risk_band"].map(band_rate).fillna(0.0)
    lines["cost_if_returned"] = np.where(lines["is_eligible"], cost_if_returned, 0.0)
    lines["risk_exposure"] = lines["band_return_rate"] * lines["cost_if_returned"]
    model.band_return_rates = {k: float(v) for k, v in band_rate.items()}
    model.category_incremental_per_unit = {k: float(v) for k, v in cat_incr_per_unit.items()}


def _top_factors(lines: pd.DataFrame, n: int = 3) -> list[str]:
    keys = list(config.RISK_WEIGHTS)
    arr = lines[[f"pts_{k}" for k in keys]].to_numpy()
    out = []
    for row in arr:
        order = np.argsort(-row)[:n]
        parts = [f"{config.RISK_FACTOR_LABELS[keys[i]]} (+{row[i]:.0f})" for i in order if row[i] >= 1]
        out.append("; ".join(parts))
    return out


def describe_model() -> dict:
    """Machine-readable description of the scoring rules for the UI and docs."""
    return {
        "type": "Heuristic rule-based score (not a trained model, not a probability)",
        "prediction_point": "At delivery: shipping delay is known; the return (if any) has not happened.",
        "factors": [
            {
                "key": k,
                "label": config.RISK_FACTOR_LABELS[k],
                "max_points": config.RISK_WEIGHTS[k],
                "scale": (f"linear from {config.RISK_SCALES[k][0]} to {config.RISK_SCALES[k][1]}"
                          if k in config.RISK_SCALES else "binary (yes = full points)"),
            }
            for k in config.RISK_WEIGHTS
        ],
        "bands": [{"label": b, "min": lo, "max": hi} for b, lo, hi in config.RISK_BANDS],
        "leakage_controls": [
            f"Historical return rates use only returns initiated at least {config.HISTORY_LAG_DAYS} days before the order date.",
            "Only units delivered before the order date count in historical denominators; the current order is excluded.",
            "Return reason, status, item condition, refunds and write-offs are never inputs.",
            "Sparse history is smoothed toward the category rate (product) and a 10% prior (category).",
        ],
        "exposure_method": (
            "Exposure = risk band's observed historical unit return rate x (forgone margin + category average "
            "incremental return cost per unit) x quantity. Band rates are in-sample and illustrative."
        ),
    }
