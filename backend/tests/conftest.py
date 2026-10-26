"""
Shared fixtures.

`tiny_frames` is a hand-built dataset small enough to calculate every metric with a
pencil. The expected values are written out in tests/test_metrics.py.

    line  order  date        product  qty  price  disc  status               return
    L1    O1     2026-01-05  P1 (A)   2    100    20    Partially Returned   R1: 1 unit refunded 90
    L2    O1     2026-01-05  P2 (B)   1    500    0     Returned             R2: 1 unit refunded 500 (damaged)
    L3    O2     2026-01-10  P1 (A)   1    100    0     Cancelled            -
    L4    O3     2026-02-01  P2 (B)   1    500    50    Delivered            R3: rejected (costs only)
    L5    O4     2026-02-10  P1 (A)   1    100    10    Return in Progress   R4: pending (nothing booked)
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.analytics.data_model import build_model  # noqa: E402


def _df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows).astype(str)


@pytest.fixture()
def tiny_frames() -> dict[str, pd.DataFrame]:
    products = _df([
        dict(product_id="P1", product_name="Alpha Tee", category="Apparel", subcategory="Tees", unit_cost=60,
             selling_price=100, supplier_id="S1", product_weight=0.3, product_status="Active", return_window_days=10),
        dict(product_id="P2", product_name="Beta Lamp", category="Decor", subcategory="Lamps", unit_cost=300,
             selling_price=500, supplier_id="S2", product_weight=2.0, product_status="Active", return_window_days=7),
    ])
    customers = _df([
        dict(customer_id="C1", customer_segment="Regular", customer_region="Karnataka", signup_date="2025-12-01",
             historical_order_count_band="0"),
        dict(customer_id="C2", customer_segment="Plus Member", customer_region="Kerala", signup_date="2021-03-01",
             historical_order_count_band="4-10"),
    ])
    base = dict(shipping_fee=0, shipping_zone="Local", sales_channel="Mobile App", payment_method="UPI")
    orders = _df([
        dict(order_id="O1", order_line_id="L1", order_date="2026-01-05", customer_id="C1", product_id="P1", quantity=2,
             unit_price=100, discount_amount=20, shipping_region="Karnataka", promised_delivery_date="2026-01-08",
             actual_delivery_date="2026-01-08", order_status="Partially Returned", **base),
        dict(order_id="O1", order_line_id="L2", order_date="2026-01-05", customer_id="C1", product_id="P2", quantity=1,
             unit_price=500, discount_amount=0, shipping_region="Karnataka", promised_delivery_date="2026-01-08",
             actual_delivery_date="2026-01-08", order_status="Returned", **base),
        dict(order_id="O2", order_line_id="L3", order_date="2026-01-10", customer_id="C2", product_id="P1", quantity=1,
             unit_price=100, discount_amount=0, shipping_region="Kerala", promised_delivery_date="2026-01-14",
             actual_delivery_date="", order_status="Cancelled", **base),
        dict(order_id="O3", order_line_id="L4", order_date="2026-02-01", customer_id="C2", product_id="P2", quantity=1,
             unit_price=500, discount_amount=50, shipping_region="Kerala", promised_delivery_date="2026-02-03",
             actual_delivery_date="2026-02-05", order_status="Delivered", **base),
        dict(order_id="O4", order_line_id="L5", order_date="2026-02-10", customer_id="C1", product_id="P1", quantity=1,
             unit_price=100, discount_amount=10, shipping_region="Karnataka", promised_delivery_date="2026-02-12",
             actual_delivery_date="2026-02-12", order_status="Return in Progress", **base),
    ])
    returns = _df([
        dict(return_id="R1", order_id="O1", order_line_id="L1", product_id="P1", return_date="2026-01-10",
             return_reason="Size or fit issue", return_quantity=1, refund_amount=90, reverse_logistics_cost=70,
             restocking_cost=50, inventory_write_off=6, item_condition="Resellable - Opened", return_status="Refunded"),
        dict(return_id="R2", order_id="O1", order_line_id="L2", product_id="P2", return_date="2026-01-12",
             return_reason="Damaged in transit", return_quantity=1, refund_amount=500, reverse_logistics_cost=90,
             restocking_cost=160, inventory_write_off=300, item_condition="Damaged", return_status="Refunded"),
        dict(return_id="R3", order_id="O3", order_line_id="L4", product_id="P2", return_date="2026-02-08",
             return_reason="Changed mind / no longer needed", return_quantity=1, refund_amount=0,
             reverse_logistics_cost=180, restocking_cost=160, inventory_write_off=0,
             item_condition="Resellable - Opened", return_status="Rejected"),
        dict(return_id="R4", order_id="O4", order_line_id="L5", product_id="P1", return_date="2026-02-14",
             return_reason="Size or fit issue", return_quantity=1, refund_amount=0, reverse_logistics_cost=0,
             restocking_cost=0, inventory_write_off=0, item_condition="Awaiting inspection", return_status="Pending"),
    ])
    return {"orders": orders, "returns": returns, "products": products, "customers": customers}


@pytest.fixture()
def tiny_model(tiny_frames):
    f = tiny_frames
    return build_model(f["orders"], f["returns"], f["products"], f["customers"], snapshot_date=date(2026, 2, 20))


def _real_frames() -> dict[str, pd.DataFrame]:
    data = REPO / "data"
    if not (data / "orders.csv").exists():
        pytest.skip("Generated data not found. Run: python scripts/generate_data.py")
    return {n: pd.read_csv(data / f"{n}.csv", dtype=str, keep_default_na=False)
            for n in ("orders", "returns", "products", "customers")}


@pytest.fixture(scope="session")
def real_frames():
    return _real_frames()


@pytest.fixture(scope="session")
def real_model(real_frames):
    import json

    info = json.loads((REPO / "data" / "dataset_info.json").read_text()) if (REPO / "data" / "dataset_info.json").exists() else {}
    snap = date.fromisoformat(info["snapshot_date"]) if info.get("snapshot_date") else None
    f = real_frames
    return build_model(f["orders"], f["returns"], f["products"], f["customers"], snapshot_date=snap)


@pytest.fixture(scope="session")
def client():
    """FastAPI TestClient bound to the real generated dataset."""
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app.main import create_app

    _real_frames()  # skip cleanly when data is missing
    app = create_app(REPO / "data")
    with TestClient(app) as c:
        yield c
