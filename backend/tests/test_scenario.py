"""What-if simulator: arithmetic, no double counting, validation."""
import pandas as pd
import pytest

from app.analytics.metrics import aggregate
from app.analytics.scenario import ScenarioParams, parse_overrides, preset_params, simulate


def base(tiny_model):
    return aggregate(tiny_model.lines, "category")


def test_zero_levers_change_nothing(tiny_model):
    res = simulate(base(tiny_model), ScenarioParams(), months=2)
    assert res["gross_cost_savings"] == 0
    assert res["net_improvement"] == 0
    assert res["scenario_contribution"] == pytest.approx(res["baseline_contribution"])


def test_hand_calculated_scenario(tiny_model):
    # Baseline: RL 340, RS 370, WO 306 (incremental 1016); refunds 590; returned cost 360
    p = ScenarioParams(return_reduction=0.10, logistics_reduction=0.20, write_off_reduction=0.50,
                       retained_sale_share=0.5, prevention_spend=50)
    res = simulate(base(tiny_model), p, months=2)
    rl = 340 * 0.9 * 0.8      # 244.8
    rs = 370 * 0.9            # 333.0
    wo = 306 * 0.9 * 0.5      # 137.7
    assert res["scenario_incremental_costs"] == pytest.approx(rl + rs + wo)
    gross = 1016 - (rl + rs + wo)
    assert res["gross_cost_savings"] == pytest.approx(gross)
    # volume + efficiency decomposition equals gross savings (no double counting)
    assert res["volume_savings"] + res["efficiency_savings"] == pytest.approx(gross)
    retained = 0.10 * 0.5 * (590 - 360)
    assert res["retained_margin"] == pytest.approx(retained)
    assert res["net_improvement"] == pytest.approx(gross + retained - 50)
    assert res["roi"] == pytest.approx((gross + retained - 50) / 50, rel=1e-4)
    assert res["payback_months"] == pytest.approx(50 / ((gross + retained) / 2), rel=1e-4)
    comps = {c["key"]: c for c in res["components"]}
    assert sum(c["savings"] for c in comps.values()) == pytest.approx(gross, abs=0.05)


def test_category_override(tiny_model):
    p = ScenarioParams(return_reduction=0.0, category_overrides={"Decor": 0.30})
    res = simulate(base(tiny_model), p, months=2)
    rows = {r["category"]: r for r in res["by_category"]}
    assert rows["Apparel"]["gross_savings"] == 0
    assert rows["Decor"]["gross_savings"] > 0


def test_validation_limits():
    assert ScenarioParams(return_reduction=0.31).validate()
    assert ScenarioParams(write_off_reduction=0.6).validate()
    assert ScenarioParams(prevention_spend=-1).validate()
    assert ScenarioParams(category_overrides={"X": 0.5}).validate()
    assert not ScenarioParams(0.3, 0.3, 0.5, 1.0, 0).validate()


def test_parse_overrides():
    assert parse_overrides("Footwear:20,Women's Fashion:15") == {"Footwear": 0.20, "Women's Fashion": 0.15}
    assert parse_overrides(None) == {}
    with pytest.raises(ValueError):
        parse_overrides("Footwear20")


def test_no_roi_without_spend(tiny_model):
    res = simulate(base(tiny_model), ScenarioParams(return_reduction=0.1), months=2)
    assert res["roi"] is None and res["payback_months"] is None


def test_empty_baseline_is_safe():
    empty = pd.DataFrame(columns=["category"])
    res = simulate(empty, ScenarioParams(prevention_spend=100), months=0)
    assert res["net_improvement"] == -100 and res["by_category"] == []


def test_presets_scale_with_baseline():
    assert preset_params("moderate", 1_000_000).prevention_spend == 100_000
    assert preset_params("aggressive", 1_000_000).return_reduction > preset_params("conservative", 1_000_000).return_reduction
