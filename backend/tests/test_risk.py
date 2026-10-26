"""Risk score: bounds, configuration and — most importantly — absence of look-ahead leakage."""
import numpy as np
import pandas as pd
import pytest

from app.analytics import config
from app.analytics.risk import historical_rates, score_features


def _history_frames():
    # One product. Order A is returned; the return is "known" 7 days after initiation.
    lines = pd.DataFrame({
        "order_line_id": ["A", "B", "C"],
        "product_id": ["X", "X", "X"],
        "category": ["K", "K", "K"],
        "order_date": pd.to_datetime(["2026-01-01", "2026-01-10", "2026-01-20"]),
        "actual_delivery_date": pd.to_datetime(["2026-01-03", "2026-01-12", "2026-01-22"]),
        "quantity": [1, 1, 1],
        "is_eligible": [True, True, True],
    })
    returns = pd.DataFrame({
        "order_line_id": ["A"], "return_date": pd.to_datetime(["2026-01-05"]), "return_quantity": [1],
        "return_status": ["Refunded"],
    })
    return lines, returns


def test_history_excludes_current_and_future_information():
    lines, returns = _history_frames()
    ret, dlv = historical_rates(lines, returns, "product_id")
    # A: nothing known before its own order -> its own return is never used
    assert ret[0] == 0 and dlv[0] == 0
    # B (ordered 01-10): A delivered 01-03 counts; A's return known only on 01-12 -> not yet visible
    assert ret[1] == 0 and dlv[1] == 1
    # C (ordered 01-20): A and B delivered before; A's return known since 01-12
    assert ret[2] == 1 and dlv[2] == 2


def test_future_return_does_not_change_earlier_scores():
    lines, returns = _history_frames()
    before = historical_rates(lines, returns, "product_id")
    later_return = pd.DataFrame({"order_line_id": ["C"], "return_date": pd.to_datetime(["2026-01-25"]),
                                 "return_quantity": [1], "return_status": ["Refunded"]})
    after = historical_rates(lines, pd.concat([returns, later_return]), "product_id")
    np.testing.assert_array_equal(before[0], after[0])
    np.testing.assert_array_equal(before[1], after[1])


def test_weights_sum_to_100_and_scores_bounded():
    assert sum(config.RISK_WEIGHTS.values()) == pytest.approx(100)
    extreme = pd.DataFrame({
        "product_hist_rate": [0.0, 0.9], "category_hist_rate": [0.0, 0.9], "discount_pct": [0.0, 0.9],
        "shipping_delay_days": [-2, 30], "value_ratio": [0.1, 50.0],
        "payment_method": ["UPI", "Cash on Delivery"], "quantity": [1, 4],
    })
    pts = score_features(extreme)
    assert pts["risk_score"].iloc[0] == 0
    assert pts["risk_score"].iloc[1] == 100
    assert list(pts["risk_band"]) == ["Low", "High"]


def test_band_thresholds():
    feats = pd.DataFrame({
        "product_hist_rate": [0.04] * 3, "category_hist_rate": [0.03] * 3, "discount_pct": [0.0, 0.0, 0.45],
        "shipping_delay_days": [0, 0, 5], "value_ratio": [0.8] * 3,
        "payment_method": ["UPI", "Cash on Delivery", "Cash on Delivery"], "quantity": [1, 2, 2],
    })
    pts = score_features(feats)
    # 0 ; COD 12 + multi 8 = 20 ; 20 + discount 16 + delay 14 = 50
    assert list(pts["risk_score"]) == [0, 20, 50]
    assert list(pts["risk_band"]) == ["Low", "Low", "Medium"]


def test_cancelled_lines_not_scored(tiny_model):
    l3 = tiny_model.lines.set_index("order_line_id").loc["L3"]
    assert pd.isna(l3["risk_score"]) and l3["risk_band"] == "Not scored" and l3["risk_exposure"] == 0


def test_post_return_fields_are_not_inputs():
    """The scoring function only accepts pre-return features; adding outcome columns changes nothing."""
    feats = pd.DataFrame({
        "product_hist_rate": [0.1], "category_hist_rate": [0.1], "discount_pct": [0.2], "shipping_delay_days": [1],
        "value_ratio": [1.5], "payment_method": ["UPI"], "quantity": [1],
    })
    base = score_features(feats)["risk_score"].iloc[0]
    leaked = feats.assign(return_reason="Damaged in transit", refund=999, return_status="Refunded")
    assert score_features(leaked)["risk_score"].iloc[0] == base


def test_real_data_high_band_has_higher_observed_rate(real_model):
    """Historical sanity check on synthetic data (not a validation of predictive accuracy)."""
    elig = real_model.lines[real_model.lines["is_eligible"]]
    rates = elig.groupby("risk_band").apply(lambda g: g["returned_units"].sum() / g["units"].sum())
    assert rates["High"] > rates["Medium"] > rates["Low"]
