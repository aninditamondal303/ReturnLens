"""
Reconciliation on the full generated dataset: every page, table and source file must
agree on the same totals.
"""
from datetime import date

import pandas as pd
import pytest

from app.analytics.filters import Filters, apply
from app.analytics.metrics import aggregate, summarize
from app.analytics.scenario import ScenarioParams
from app.services import geography_service, leakage_service, overview, product_service, risk_service, simulator_service

ALL = Filters()


def test_lines_reconcile_to_source_files(real_model, real_frames):
    s = summarize(real_model.lines)
    o = real_frames["orders"].copy()
    r = real_frames["returns"].copy()
    o = o[o["order_status"] != "Cancelled"]
    gmv = (pd.to_numeric(o["quantity"]) * pd.to_numeric(o["unit_price"])).sum()
    assert s["gmv"] == pytest.approx(gmv)
    assert s["discount"] == pytest.approx(pd.to_numeric(o["discount_amount"]).sum())
    ref = r[r["return_status"] == "Refunded"]
    assert s["refund"] == pytest.approx(pd.to_numeric(ref["refund_amount"]).sum())
    assert s["returned_units"] == pytest.approx(pd.to_numeric(ref["return_quantity"]).sum())
    assert s["reverse_logistics"] == pytest.approx(pd.to_numeric(r["reverse_logistics_cost"]).sum())
    assert s["restocking"] == pytest.approx(pd.to_numeric(r["restocking_cost"]).sum())
    assert s["write_off"] == pytest.approx(pd.to_numeric(r["inventory_write_off"]).sum())


def test_pages_report_identical_totals(real_model):
    ov = overview.build(real_model, ALL)["summary"]
    lk = leakage_service.build(real_model, ALL)
    geo = geography_service.build(real_model, ALL)
    sim = simulator_service.build(real_model, ALL, ScenarioParams())["result"]
    for key in ("gmv", "refund", "incremental_costs", "contribution_after", "unit_return_rate"):
        assert ov[key] == pytest.approx(lk["summary"][key]), key
    assert sum(r["gmv"] for r in geo["regions"]) == pytest.approx(ov["gmv"])
    assert sum(r["incremental_costs"] for r in geo["segments"]) == pytest.approx(ov["incremental_costs"])
    assert sum(r["contribution_after"] for r in lk["categories"]) == pytest.approx(ov["contribution_after"])
    assert sim["baseline_incremental_costs"] == pytest.approx(ov["incremental_costs"], abs=0.01)
    assert sim["baseline_contribution"] == pytest.approx(ov["contribution_after"], abs=0.01)
    assert all(abs(v) < 0.01 for k, v in lk["reconciliation"].items() if k != "note")


def test_product_table_reconciles(real_model):
    prods = product_service.table(real_model, ALL, None, None, "gmv", "desc")
    s = summarize(real_model.lines)
    assert prods["gmv"].sum() == pytest.approx(s["gmv"])
    assert prods["refund"].sum() == pytest.approx(s["refund"])
    assert prods["contribution_after"].sum() == pytest.approx(s["contribution_after"])


def test_drilldown_category_to_product_to_lines(real_model):
    f = Filters(start_date=date(2026, 4, 1), end_date=date(2026, 6, 30))
    cat = leakage_service.build(real_model, f)["categories"][0]
    drill = leakage_service.category_products(real_model, f, cat["category"])
    assert sum(p["gmv"] for p in drill["products"]) == pytest.approx(cat["gmv"])
    prod = drill["products"][0]
    lines = leakage_service.order_lines_frame(real_model, f, prod["product_id"], None, "order_date", "desc")
    assert lines["net_sales"].sum() == pytest.approx(prod["net_sales"])
    assert lines["refund"].sum() == pytest.approx(prod["refund"])


def test_filters_partition_totals(real_model):
    """Summing each region's filtered total equals the unfiltered total."""
    total = summarize(real_model.lines)["gmv"]
    regions = real_model.lines["shipping_region"].unique()
    parts = sum(summarize(apply(real_model.lines, Filters(regions=(r,))))["gmv"] for r in regions)
    assert parts == pytest.approx(total)


def test_combined_filters(real_model):
    f = Filters(start_date=date(2026, 1, 1), end_date=date(2026, 3, 31), categories=("Footwear",),
                regions=("Maharashtra",), channels=("Mobile App",))
    lines = apply(real_model.lines, f)
    assert len(lines) > 0
    assert set(lines["category"]) == {"Footwear"} and set(lines["shipping_region"]) == {"Maharashtra"}
    assert lines["order_date"].min() >= pd.Timestamp("2026-01-01")
    assert overview.build(real_model, f)["summary"]["gmv"] == pytest.approx(summarize(lines)["gmv"])


def test_risk_table_csv_export_respects_filters(real_model):
    f = Filters(categories=("Women's Fashion",))
    df = risk_service.order_table(real_model, f, ("High",), (), None, "risk_score", "desc")
    assert len(df) > 0 and set(df["category"]) == {"Women's Fashion"} and set(df["risk_band"]) == {"High"}
    assert df["risk_score"].is_monotonic_decreasing


def test_overview_comparison_for_partial_period(real_model):
    res = overview.build(real_model, Filters(start_date=date(2026, 7, 1), end_date=date(2026, 9, 30)))
    assert res["comparison"]["available"]
    gmv = next(k for k in res["kpis"] if k["key"] == "gmv")
    assert gmv["previous"] is not None and gmv["change"] is not None
    full = overview.build(real_model, ALL)
    assert not full["comparison"]["available"]


def test_insights_are_consistent_with_data(real_model):
    res = overview.build(real_model, ALL)
    assert 3 <= len(res["insights"]) <= 5
    cats = aggregate(real_model.lines, "category")
    above = int((cats["unit_return_rate"] > 0.08).sum())
    first = next((i for i in res["insights"] if i["id"] == "category_above_target"), None)
    if first:
        assert first["title"].startswith(f"{above} of")
