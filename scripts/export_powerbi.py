"""
Export a Power BI-ready star schema from the SAME analytics engine the website uses.

Writes to data/powerbi/:
    fact_order_lines.csv   one row per order line (grain of orders.csv) + engine measures + risk score
    fact_returns.csv       one row per return record, carrying the keys of its order line
    dim_product.csv  dim_customer.csv  dim_geography.csv  dim_channel.csv
    expected_totals.json   full-period totals to reconcile Power BI against the API

Usage (repository root, backend virtual environment active):
    python scripts/export_powerbi.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.analytics.data_model import build_model  # noqa: E402
from app.analytics.metrics import summarize  # noqa: E402

DATA = ROOT / "data"
OUT = DATA / "powerbi"


def main() -> int:
    frames = {n: pd.read_csv(DATA / f"{n}.csv", dtype=str, keep_default_na=False)
              for n in ("orders", "returns", "products", "customers")}
    info = json.loads((DATA / "dataset_info.json").read_text()) if (DATA / "dataset_info.json").exists() else {}
    snap = date.fromisoformat(info["snapshot_date"]) if info.get("snapshot_date") else None
    m = build_model(frames["orders"], frames["returns"], frames["products"], frames["customers"], snapshot_date=snap)
    OUT.mkdir(parents=True, exist_ok=True)

    lines = m.lines.copy()
    lines["order_date"] = lines["order_date"].dt.strftime("%Y-%m-%d")
    lines["is_eligible"] = lines["is_eligible"].astype(int)
    lines["has_refunded_return"] = lines["has_refunded_return"].astype(int)
    fact_lines = lines[[
        "order_line_id", "order_id", "order_date", "customer_id", "product_id", "shipping_region", "sales_channel",
        "payment_method", "order_status", "customer_type", "is_eligible", "quantity", "unit_price", "discount_amount",
        "gmv", "discount", "net_sales", "units", "unit_cost", "cogs", "returned_units", "refund", "returned_cost",
        "reverse_logistics", "restocking", "write_off", "has_refunded_return", "shipping_delay_days", "risk_score",
        "risk_band", "risk_exposure", "actual_return_status",
    ]].round(4)
    fact_lines.to_csv(OUT / "fact_order_lines.csv", index=False)

    rx = m.returns_x.copy()
    rx["order_date"] = rx["order_date"].dt.strftime("%Y-%m-%d")
    rx["return_date"] = rx["return_date"].dt.strftime("%Y-%m-%d")
    rx["is_refunded"] = (rx["return_status"] == "Refunded").astype(int)
    rx[["return_id", "order_line_id", "order_id", "product_id", "customer_id", "shipping_region", "sales_channel",
        "order_date", "return_date", "return_reason", "return_quantity", "refund_amount", "reverse_logistics_cost",
        "restocking_cost", "inventory_write_off", "item_condition", "return_status", "is_refunded"]].to_csv(
        OUT / "fact_returns.csv", index=False)

    m.products.to_csv(OUT / "dim_product.csv", index=False)
    m.customers.to_csv(OUT / "dim_customer.csv", index=False)
    geo = (m.lines[["shipping_region", "shipping_zone"]].drop_duplicates().sort_values("shipping_region"))
    geo.to_csv(OUT / "dim_geography.csv", index=False)
    pd.DataFrame({"sales_channel": sorted(m.lines["sales_channel"].unique())}).to_csv(OUT / "dim_channel.csv", index=False)

    s = summarize(m.lines)
    keys = ["gmv", "discount", "net_sales", "refund", "net_revenue", "units", "returned_units", "unit_return_rate",
            "eligible_orders", "returned_orders", "order_return_rate", "cogs", "returned_cost", "reverse_logistics",
            "restocking", "write_off", "incremental_costs", "contribution_before", "contribution_after",
            "return_leakage"]
    elig = m.lines[m.lines["is_eligible"]]
    expected = {k: (int(s[k]) if k in ("units", "returned_units", "eligible_orders", "returned_orders") else s[k]) for k in keys}
    expected["high_risk_orders"] = int(elig.loc[elig["risk_band"] == "High", "order_id"].nunique())
    expected["high_risk_exposure"] = round(float(elig.loc[elig["risk_band"] == "High", "risk_exposure"].sum()), 2)
    (OUT / "expected_totals.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")

    for f in sorted(OUT.iterdir()):
        print(f"  wrote {f.relative_to(ROOT)}")
    print("\nExpected full-period totals (compare with Power BI cards):")
    for k, v in expected.items():
        print(f"  {k:22s} {v:>18,.4f}" if isinstance(v, float) else f"  {k:22s} {v:>18,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
