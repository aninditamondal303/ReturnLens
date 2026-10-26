"""Hand-calculated tests for the central metrics engine (see the table in conftest.py)."""
from datetime import date

import pandas as pd
import pytest

from app.analytics.filters import Filters, apply
from app.analytics.metrics import aggregate, anatomy_steps, bridge_steps, safe_div, summarize

# ---------------------------------------------------------------------------
# Expected values, calculated by hand:
#   eligible lines L1, L2, L4, L5 (L3 cancelled)
#   GMV        = 2*100 + 500 + 500 + 100        = 1300
#   Discounts  = 20 + 0 + 50 + 10               = 80
#   Net sales  = 1300 - 80                      = 1220
#   Refunds    = 90 + 500 (R3 rejected, R4 pending excluded) = 590
#   Net revenue= 1220 - 590                     = 630
#   Units      = 2 + 1 + 1 + 1                  = 5     Returned units = 1 + 1 = 2
#   Gross COGS = 2*60 + 300 + 300 + 60          = 780   Returned cost  = 60 + 300 = 360
#   Contribution before = 630 - (780 - 360)     = 210
#   Reverse logistics   = 70 + 90 + 180 (rejected) = 340
#   Restocking          = 50 + 160 + 160        = 370
#   Write-off           = 6 + 300               = 306   Incremental = 1016
#   Contribution after  = 210 - 1016            = -806
#   Return leakage      = (590 - 360) + 1016    = 1246
#   Orders: eligible O1, O3, O4 = 3; returned O1 = 1
# ---------------------------------------------------------------------------
EXPECTED = {
    "gmv": 1300, "discount": 80, "net_sales": 1220, "refund": 590, "net_revenue": 630, "units": 5,
    "returned_units": 2, "cogs": 780, "returned_cost": 360, "net_cogs": 420, "contribution_before": 210,
    "reverse_logistics": 340, "restocking": 370, "write_off": 306, "incremental_costs": 1016,
    "contribution_after": -806, "return_leakage": 1246, "recoverable_inventory": 54,
    "eligible_orders": 3, "returned_orders": 1, "cancelled_lines": 1, "total_lines": 5,
}


def test_summary_matches_hand_calculation(tiny_model):
    s = summarize(tiny_model.lines)
    for key, value in EXPECTED.items():
        assert s[key] == pytest.approx(value), key


def test_rates(tiny_model):
    s = summarize(tiny_model.lines)
    assert s["unit_return_rate"] == pytest.approx(2 / 5)
    assert s["order_return_rate"] == pytest.approx(1 / 3)
    assert s["contribution_margin"] == pytest.approx(-806 / 630)


def test_cancelled_lines_have_no_financial_effect(tiny_model):
    l3 = tiny_model.lines.set_index("order_line_id").loc["L3"]
    for col in ["gmv", "discount", "net_sales", "units", "cogs", "refund"]:
        assert l3[col] == 0


def test_partial_return_refund_uses_net_price(tiny_model):
    l1 = tiny_model.lines.set_index("order_line_id").loc["L1"]
    assert l1["returned_units"] == 1 and l1["quantity"] == 2
    assert l1["refund"] == pytest.approx(90)  # (200 - 20) / 2
    assert l1["order_status"] == "Partially Returned"


def test_refund_is_not_an_incremental_cost(tiny_model):
    s = summarize(tiny_model.lines)
    assert s["incremental_costs"] == pytest.approx(s["reverse_logistics"] + s["restocking"] + s["write_off"])
    assert s["incremental_costs"] != pytest.approx(s["incremental_costs"] + s["refund"])


def test_rejected_and_pending_returns(tiny_model):
    lines = tiny_model.lines.set_index("order_line_id")
    assert lines.loc["L4", "returned_units"] == 0 and lines.loc["L4", "refund"] == 0
    assert lines.loc["L4", "reverse_logistics"] == 180  # cost still incurred
    assert lines.loc["L5", "pending_units"] == 1 and lines.loc["L5", "incremental_costs" if False else "restocking"] == 0
    assert lines.loc["L4", "actual_return_status"] == "Return rejected"
    assert lines.loc["L5", "actual_return_status"] == "Return in progress"


def test_returned_inventory_recovery_not_double_counted(tiny_model):
    s = summarize(tiny_model.lines)
    # identity: leakage = contribution with no returns at all - actual contribution
    no_return_contribution = s["net_sales"] - s["cogs"]
    assert no_return_contribution - s["contribution_after"] == pytest.approx(s["return_leakage"])
    assert s["recoverable_inventory"] == pytest.approx(s["returned_cost"] - s["write_off"])


def test_bridge_reconciles(tiny_model):
    s = summarize(tiny_model.lines)
    steps = bridge_steps(s)
    assert steps[-1]["end"] == pytest.approx(s["contribution_after"])
    net_rev = next(x for x in steps if x["key"] == "net_revenue")
    assert net_rev["end"] == pytest.approx(630)
    before = next(x for x in steps if x["key"] == "contribution_before")
    assert before["end"] == pytest.approx(210)
    flow = s["gmv"] + sum(x["value"] for x in steps if x["kind"] not in ("total", "subtotal"))
    assert flow == pytest.approx(s["contribution_after"])
    anatomy = anatomy_steps(s)
    assert sum(x["value"] for x in anatomy[1:-1]) + s["gmv"] == pytest.approx(anatomy[-1]["value"])


def test_category_aggregation_sums_to_total(tiny_model):
    cats = aggregate(tiny_model.lines, "category").set_index("category")
    s = summarize(tiny_model.lines)
    assert cats["gmv"].sum() == pytest.approx(s["gmv"])
    assert cats["contribution_after"].sum() == pytest.approx(s["contribution_after"])
    assert cats.loc["Apparel", "gmv"] == pytest.approx(300)  # L1 200 + L5 100 (L3 cancelled)
    assert cats.loc["Apparel", "unit_return_rate"] == pytest.approx(1 / 3)
    assert cats.loc["Decor", "unit_return_rate"] == pytest.approx(1 / 2)


def test_filters_category_region_dates(tiny_model):
    lines = tiny_model.lines
    s = summarize(apply(lines, Filters(categories=("Decor",))))
    assert s["gmv"] == pytest.approx(1000) and s["refund"] == pytest.approx(500)
    s = summarize(apply(lines, Filters(regions=("Kerala",))))
    assert s["gmv"] == pytest.approx(500) and s["cancelled_lines"] == 1
    s = summarize(apply(lines, Filters(start_date=date(2026, 2, 1), end_date=date(2026, 2, 28))))
    assert s["gmv"] == pytest.approx(600) and s["units"] == 2


def test_empty_filter_is_safe(tiny_model):
    s = summarize(apply(tiny_model.lines, Filters(regions=("Nowhere",))))
    assert s["gmv"] == 0 and s["unit_return_rate"] is None and s["order_return_rate"] is None
    assert aggregate(apply(tiny_model.lines, Filters(regions=("Nowhere",))), "category").empty


def test_safe_div():
    assert safe_div(1, 0) is None
    assert safe_div(1, None) is None
    assert safe_div(3, 4) == 0.75
    out = safe_div(pd.Series([1.0, 2.0]), pd.Series([0.0, 4.0]))
    assert pd.isna(out[0]) and out[1] == 0.5


def test_previous_period():
    f = Filters(start_date=date(2026, 7, 1), end_date=date(2026, 9, 30))
    prev = f.previous_period(date(2025, 10, 1))
    assert prev.start_date == date(2026, 3, 31) and prev.end_date == date(2026, 6, 30)
    assert Filters(start_date=date(2025, 10, 1), end_date=date(2026, 9, 30)).previous_period(date(2025, 10, 1)) is None


def test_missing_numeric_values_are_treated_as_zero(tiny_frames):
    from app.analytics.data_model import build_model

    f = tiny_frames
    f["orders"].loc[f["orders"]["order_line_id"] == "L4", "discount_amount"] = ""
    m = build_model(f["orders"], f["returns"], f["products"], f["customers"], snapshot_date=date(2026, 2, 20))
    assert summarize(m.lines)["discount"] == pytest.approx(30)
