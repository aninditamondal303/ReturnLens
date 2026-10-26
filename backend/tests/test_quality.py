"""Data validation: generated data passes; deliberately corrupted data is caught."""
import pandas as pd

from app.analytics.quality import profile_dataset, run_validation


def failed(report):
    return {c["name"] for c in report["checks"] if not c["passed"]}


def test_tiny_dataset_is_valid(tiny_frames):
    report = run_validation(tiny_frames)
    assert report["passed"], failed(report)


def test_generated_dataset_is_valid(real_frames):
    report = run_validation(real_frames)
    assert report["passed"], failed(report)
    assert report["summary"]["errors"] == 0


def test_return_quantity_above_purchase_is_caught(tiny_frames):
    tiny_frames["returns"].loc[0, "return_quantity"] = "5"
    assert "returns: returned qty <= purchased qty" in failed(run_validation(tiny_frames))


def test_orphan_foreign_key_is_caught(tiny_frames):
    tiny_frames["orders"].loc[0, "product_id"] = "P999"
    assert "foreign key orders.product_id -> products" in failed(run_validation(tiny_frames))


def test_excess_refund_is_caught(tiny_frames):
    tiny_frames["returns"].loc[0, "refund_amount"] = "150"  # net price paid was 90
    assert "returns: refund <= eligible merchandise value" in failed(run_validation(tiny_frames))


def test_duplicate_keys_and_rows_are_caught(tiny_frames):
    o = tiny_frames["orders"]
    tiny_frames["orders"] = pd.concat([o, o.iloc[[0]]], ignore_index=True)
    names = failed(run_validation(tiny_frames))
    assert "orders: unique order_line_id" in names and "orders: no duplicate rows" in names


def test_status_inconsistency_is_caught(tiny_frames):
    tiny_frames["orders"].loc[1, "order_status"] = "Delivered"  # L2 was fully refunded
    assert "orders: status consistent with returns" in failed(run_validation(tiny_frames))


def test_missing_required_column(tiny_frames):
    tiny_frames["orders"] = tiny_frames["orders"].drop(columns=["quantity"])
    report = run_validation(tiny_frames)
    assert not report["passed"]


def test_invalid_quantity_and_date(tiny_frames):
    tiny_frames["orders"].loc[0, "quantity"] = "0"
    tiny_frames["orders"].loc[1, "order_date"] = "not-a-date"
    names = failed(run_validation(tiny_frames))
    assert "orders: quantity is a positive integer" in names and "orders: valid order dates" in names


def test_profile_reports_expected_missing(tiny_frames):
    prof = profile_dataset("orders", tiny_frames["orders"])
    col = next(c for c in prof["columns"] if c["name"] == "actual_delivery_date")
    assert col["missing"] == 1 and "cancelled" in col["missing_note"].lower()
