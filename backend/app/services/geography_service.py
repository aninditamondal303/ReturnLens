"""Customer & Geography page: regions, shipping zones, customer segments (aggregated only)."""
from __future__ import annotations

from ..analytics.data_model import AnalyticsModel
from ..analytics.filters import Filters, apply
from ..analytics.metrics import aggregate, records, safe_div, summarize
from .common import meta

GROUP_COLUMNS = ["gmv", "net_sales", "units", "returned_units", "unit_return_rate", "order_return_rate",
                 "eligible_orders", "returned_orders", "refund", "reverse_logistics", "restocking", "write_off",
                 "incremental_costs", "incremental_per_returned_order", "incremental_per_returned_unit",
                 "avg_order_value", "contribution_after", "contribution_margin", "return_leakage"]

HISTORY_ORDER = ["0", "1-3", "4-10", "11+"]


def _group(lines, key, order=None):
    g = aggregate(lines, key)
    g = g[g["units"] > 0]
    if order:
        g = g.set_index(key).reindex([o for o in order if o in set(g[key])]).reset_index()
    else:
        g = g.sort_values("gmv", ascending=False)
    total_rl = float(g["reverse_logistics"].sum()) or 1.0
    total_gmv = float(g["gmv"].sum()) or 1.0
    g["gmv_share"] = g["gmv"] / total_gmv
    g["reverse_logistics_share"] = g["reverse_logistics"] / total_rl
    return g


def build(model: AnalyticsModel, f: Filters) -> dict:
    lines = apply(model.lines, f)
    s = summarize(lines)
    regions = _group(lines, "shipping_region")
    zone_of = lines.drop_duplicates("shipping_region").set_index("shipping_region")["shipping_zone"]
    regions["shipping_zone"] = regions["shipping_region"].map(zone_of)
    zones = _group(lines, "shipping_zone", ["Local", "Metro", "National", "Remote"])
    segments = _group(lines, "customer_segment")
    ctype = _group(lines, "customer_type", ["New", "Repeat"])
    history = _group(lines, "historical_order_count_band", HISTORY_ORDER)
    channels = _group(lines, "sales_channel")
    payments = _group(lines, "payment_method")

    # 12-month value proxy per segment (NOT lifetime value: only one year of history exists)
    elig = lines[lines["is_eligible"]]
    active = elig.groupby("customer_segment")["customer_id"].nunique()
    segments["active_customers"] = segments["customer_segment"].map(active).fillna(0)
    segments["net_revenue_per_customer"] = safe_div(segments["net_revenue"], segments["active_customers"])
    segments["contribution_per_customer"] = safe_div(segments["contribution_after"], segments["active_customers"])
    segments["orders_per_customer"] = safe_div(segments["eligible_orders"], segments["active_customers"])

    cols = ["shipping_region", "shipping_zone", "gmv_share", "reverse_logistics_share"] + GROUP_COLUMNS
    return {
        "meta": meta(model, f, len(lines)),
        "summary": {k: s.get(k) for k in ["gmv", "unit_return_rate", "incremental_costs", "reverse_logistics",
                                          "incremental_per_returned_order", "eligible_orders", "returned_orders"]},
        "regions": records(regions[cols]),
        "zones": records(zones[["shipping_zone", "gmv_share", "reverse_logistics_share"] + GROUP_COLUMNS]),
        "segments": records(segments[["customer_segment", "gmv_share", "active_customers", "net_revenue_per_customer",
                                      "contribution_per_customer", "orders_per_customer"] + GROUP_COLUMNS]),
        "customer_type": records(ctype[["customer_type", "gmv_share"] + GROUP_COLUMNS]),
        "history_bands": records(history[["historical_order_count_band", "gmv_share"] + GROUP_COLUMNS]),
        "channels": records(channels[["sales_channel", "gmv_share"] + GROUP_COLUMNS]),
        "payments": records(payments[["payment_method", "gmv_share"] + GROUP_COLUMNS]),
        "notes": [
            "Customer analysis is aggregated by segment; no personal information is stored or shown.",
            "'New' = the customer's first order in the dataset with no pre-period order history; all others are 'Repeat'.",
            "Value per customer is a 12-month proxy, not lifetime value: only one year of history is available.",
            "Higher return rates in a segment are a pattern to investigate, not evidence of fraud.",
        ],
    }
