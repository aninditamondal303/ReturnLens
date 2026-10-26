"""
Data-quality validation and profiling.

Shared by:
  * scripts/generate_data.py  - refuses to write CSVs when an error-level check fails
  * the API (/api/data-quality) - reports issues instead of silently fixing them

Every check returns a record with a severity ("error" or "warning"), the number of
affected rows and a plain-language explanation of how the issue would affect the
analysis. Nothing in this module modifies the data.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

REQUIRED_COLUMNS: dict[str, list[str]] = {
    "orders": [
        "order_id", "order_line_id", "order_date", "customer_id", "product_id", "quantity", "unit_price",
        "discount_amount", "shipping_fee", "shipping_region", "shipping_zone", "sales_channel",
        "promised_delivery_date", "actual_delivery_date", "order_status", "payment_method",
    ],
    "returns": [
        "return_id", "order_id", "order_line_id", "product_id", "return_date", "return_reason",
        "return_quantity", "refund_amount", "reverse_logistics_cost", "restocking_cost",
        "inventory_write_off", "item_condition", "return_status",
    ],
    "products": [
        "product_id", "product_name", "category", "subcategory", "unit_cost", "selling_price",
        "supplier_id", "product_weight", "product_status", "return_window_days",
    ],
    "customers": [
        "customer_id", "customer_segment", "customer_region", "signup_date", "historical_order_count_band",
    ],
}

NUMERIC_COLUMNS = {
    "orders": ["quantity", "unit_price", "discount_amount", "shipping_fee"],
    "returns": ["return_quantity", "refund_amount", "reverse_logistics_cost", "restocking_cost", "inventory_write_off"],
    "products": ["unit_cost", "selling_price", "product_weight", "return_window_days"],
}

PRIMARY_KEYS = {"orders": "order_line_id", "returns": "return_id", "products": "product_id", "customers": "customer_id"}

ORDER_STATUSES = {"Delivered", "Partially Returned", "Returned", "Return in Progress", "Cancelled"}
RETURN_STATUSES = {"Refunded", "Rejected", "Pending"}

# Columns that are legitimately empty in some rows, with the business reason.
EXPECTED_MISSING = {
    ("orders", "actual_delivery_date"): "Empty only for cancelled order lines (never delivered).",
}

TOLERANCE = 0.011  # rupees: allows for 2-decimal rounding


def _check(name: str, passed: bool, severity: str, detail: str, affected: int = 0, impact: str = "") -> dict:
    return {
        "name": name,
        "passed": bool(passed),
        "severity": severity,
        "detail": detail,
        "affected_rows": int(affected),
        "impact": impact,
    }


def _to_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.replace("", np.nan), errors="coerce")


def run_validation(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Run all integrity and business-rule checks. Returns {'passed', 'checks', 'summary'}."""
    checks: list[dict] = []

    # 1. Schema ------------------------------------------------------------------
    schema_ok = True
    for name, cols in REQUIRED_COLUMNS.items():
        df = frames.get(name)
        if df is None:
            checks.append(_check(f"{name}: file present", False, "error", f"{name}.csv is missing",
                                 impact="No analysis is possible without this dataset."))
            schema_ok = False
            continue
        missing = [c for c in cols if c not in df.columns]
        checks.append(_check(
            f"{name}: required columns", not missing, "error",
            "all required columns present" if not missing else f"missing columns: {', '.join(missing)}",
            impact="Metrics depending on these columns cannot be calculated.",
        ))
        schema_ok &= not missing
    if not schema_ok:
        return {"passed": False, "checks": checks, "summary": _summary(checks)}

    orders = frames["orders"].copy()
    returns = frames["returns"].copy()
    products = frames["products"].copy()
    customers = frames["customers"].copy()
    # CSV files are read as text: coerce numeric columns (unparseable values become NaN and fail checks below)
    for df, cols in ((orders, NUMERIC_COLUMNS["orders"]), (returns, NUMERIC_COLUMNS["returns"]),
                     (products, NUMERIC_COLUMNS["products"])):
        for col in cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    frames = {**frames, "orders": orders, "returns": returns, "products": products}

    # 2. Primary keys & duplicates ---------------------------------------------------
    for name, key in PRIMARY_KEYS.items():
        df = frames[name]
        dup = int(df[key].duplicated().sum())
        checks.append(_check(f"{name}: unique {key}", dup == 0, "error",
                             f"{dup} duplicate keys" if dup else f"{len(df):,} unique keys", dup,
                             "Duplicate keys would double-count sales or returns."))
        full_dup = int(df.duplicated().sum())
        checks.append(_check(f"{name}: no duplicate rows", full_dup == 0, "error",
                             f"{full_dup} fully duplicated rows" if full_dup else "no duplicated rows", full_dup,
                             "Duplicated rows inflate every additive metric."))
    dup_op = int(orders.duplicated(["order_id", "product_id"]).sum())
    checks.append(_check("orders: one line per product per order", dup_op == 0, "error",
                         f"{dup_op} repeated order/product pairs" if dup_op else "order_id + product_id is unique",
                         dup_op, "Returns could not be matched unambiguously to the purchased line."))

    # 3. Missing values ----------------------------------------------------------------
    for name, df in frames.items():
        for col in REQUIRED_COLUMNS[name]:
            s = df[col]
            miss = s.isna() | (s.astype(str).str.strip() == "")
            n_miss = int(miss.sum())
            if (name, col) in EXPECTED_MISSING:
                if col == "actual_delivery_date":
                    unexpected = int((miss & (df["order_status"] != "Cancelled")).sum())
                    wrong_filled = int((~miss & (df["order_status"] == "Cancelled")).sum())
                    bad = unexpected + wrong_filled
                    checks.append(_check(
                        "orders: delivery date present iff not cancelled", bad == 0, "error",
                        f"{n_miss:,} empty values, all on cancelled lines (expected)" if bad == 0
                        else f"{unexpected} delivered lines without a delivery date, {wrong_filled} cancelled lines with one",
                        bad, "Shipping-delay and return-window logic depend on the delivery date."))
                continue
            if n_miss:
                checks.append(_check(f"{name}: {col} not missing", False, "error", f"{n_miss} missing values", n_miss,
                                     "Rows with missing required values would be excluded or mis-classified."))
    if not any(c["name"].endswith("not missing") for c in checks):
        checks.append(_check("all datasets: required values present", True, "error", "no unexpected missing values"))

    # 4. Foreign keys ------------------------------------------------------------------
    fk_specs = [
        ("orders.product_id -> products", orders["product_id"], products["product_id"]),
        ("orders.customer_id -> customers", orders["customer_id"], customers["customer_id"]),
        ("returns.order_line_id -> orders", returns["order_line_id"], orders["order_line_id"]),
    ]
    for label, child, parent in fk_specs:
        orphans = int((~child.isin(set(parent))).sum())
        checks.append(_check(f"foreign key {label}", orphans == 0, "error",
                             f"{orphans} orphan rows" if orphans else "all references resolve", orphans,
                             "Orphan rows cannot be attributed to a category, customer or order."))

    # lookups use de-duplicated keys so that duplicate rows are reported, not fatal
    orders_u = orders.drop_duplicates("order_line_id")
    products_u = products.drop_duplicates("product_id").set_index("product_id")
    line_idx = orders_u.set_index("order_line_id")
    merged = returns.merge(
        orders_u[["order_line_id", "order_id", "product_id", "quantity", "unit_price", "discount_amount",
                "order_status", "actual_delivery_date", "order_date"]],
        on="order_line_id", how="left", suffixes=("", "_line"),
    )
    mismatch = int(((merged["order_id"] != merged["order_id_line"]) | (merged["product_id"] != merged["product_id_line"])).sum())
    checks.append(_check("returns: order_id/product_id match the order line", mismatch == 0, "error",
                         f"{mismatch} mismatched returns" if mismatch else "all returns match their order line", mismatch,
                         "A return pointing at the wrong product distorts product return rates."))

    # 5. Numeric validity -----------------------------------------------------------------
    q = pd.to_numeric(orders["quantity"], errors="coerce")
    bad_q = int(((q < 1) | (q.isna()) | (q != q.round())).sum())
    checks.append(_check("orders: quantity is a positive integer", bad_q == 0, "error",
                         f"{bad_q} impossible quantities" if bad_q else "all quantities >= 1", bad_q,
                         "Impossible quantities corrupt units sold and return rates."))
    price = pd.to_numeric(orders["unit_price"], errors="coerce")
    disc = pd.to_numeric(orders["discount_amount"], errors="coerce")
    bad_price = int(((price <= 0) | price.isna()).sum())
    checks.append(_check("orders: unit_price > 0", bad_price == 0, "error",
                         f"{bad_price} non-positive prices" if bad_price else "all prices positive", bad_price,
                         "GMV would be understated."))
    bad_disc = int(((disc < 0) | (disc > q * price + TOLERANCE) | disc.isna()).sum())
    checks.append(_check("orders: 0 <= discount <= gross line value", bad_disc == 0, "error",
                         f"{bad_disc} invalid discounts" if bad_disc else "all discounts within line value", bad_disc,
                         "Discounts above the line value would produce negative net sales."))
    margin_bad = int((pd.to_numeric(products["unit_cost"]) >= pd.to_numeric(products["selling_price"])).sum())
    checks.append(_check("products: unit_cost below selling_price", margin_bad == 0, "warning",
                         f"{margin_bad} products sold at or below cost" if margin_bad else "every product has positive list margin",
                         margin_bad, "Negative list margins are allowed but should be reviewed."))
    for col in ["refund_amount", "reverse_logistics_cost", "restocking_cost", "inventory_write_off"]:
        neg = int((pd.to_numeric(returns[col], errors="coerce") < 0).sum())
        checks.append(_check(f"returns: {col} >= 0", neg == 0, "error",
                             f"{neg} negative values" if neg else "no negative values", neg,
                             "Negative costs would understate return leakage."))

    # 6. Categorical domains ---------------------------------------------------------------
    bad_os = int((~orders["order_status"].isin(ORDER_STATUSES)).sum())
    checks.append(_check("orders: valid order_status values", bad_os == 0, "error",
                         f"{bad_os} unknown statuses" if bad_os else ", ".join(sorted(ORDER_STATUSES)), bad_os,
                         "Unknown statuses cannot be classified as eligible or cancelled."))
    bad_rs = int((~returns["return_status"].isin(RETURN_STATUSES)).sum())
    checks.append(_check("returns: valid return_status values", bad_rs == 0, "error",
                         f"{bad_rs} unknown statuses" if bad_rs else ", ".join(sorted(RETURN_STATUSES)), bad_rs,
                         "Unknown statuses cannot be classified as processed or pending."))

    # 7. Dates -------------------------------------------------------------------------------
    od = _to_date(orders["order_date"])
    pdd = _to_date(orders["promised_delivery_date"])
    add = _to_date(orders["actual_delivery_date"])
    bad_od = int(od.isna().sum())
    checks.append(_check("orders: valid order dates", bad_od == 0, "error",
                         f"{bad_od} unparseable dates" if bad_od else f"{od.min().date()} to {od.max().date()}", bad_od,
                         "Rows with invalid dates drop out of every time filter."))
    bad_seq = int(((pdd < od) | (add.notna() & (add < od))).sum())
    checks.append(_check("orders: delivery dates on/after order date", bad_seq == 0, "error",
                         f"{bad_seq} lines delivered before they were ordered" if bad_seq else "date sequence consistent",
                         bad_seq, "Shipping-delay features would be wrong."))
    rd = _to_date(merged["return_date"])
    md = _to_date(merged["actual_delivery_date"])
    bad_rd = int((rd.isna() | md.isna() | (rd < md)).sum())
    checks.append(_check("returns: return date on/after delivery", bad_rd == 0, "error",
                         f"{bad_rd} returns before delivery or on undelivered lines" if bad_rd else "all returns follow delivery",
                         bad_rd, "Returns on undelivered or cancelled lines are logically impossible."))
    win = merged["product_id"].map(products_u["return_window_days"])
    late = int(((rd - md).dt.days > pd.to_numeric(win, errors="coerce")).sum())
    checks.append(_check("returns: within product return window", late == 0, "warning",
                         f"{late} returns outside the window (documented exceptions)" if late else "all within window",
                         late, "Out-of-window returns may indicate policy exceptions."))

    # 8. Return quantities and refunds ------------------------------------------------------------
    qty_by_line = returns.groupby("order_line_id")["return_quantity"].sum()
    purchased = line_idx["quantity"].reindex(qty_by_line.index)
    over = int((qty_by_line > purchased).sum())
    checks.append(_check("returns: returned qty <= purchased qty", over == 0, "error",
                         f"{over} lines with more units returned than bought" if over else "never exceeds purchased quantity",
                         over, "Return rates above 100 % would be possible."))
    net_unit = (merged["quantity"] * merged["unit_price"] - merged["discount_amount"]) / merged["quantity"]
    max_refund = merged["return_quantity"] * net_unit
    over_ref = int((merged["refund_amount"] > max_refund + TOLERANCE).sum())
    checks.append(_check("returns: refund <= eligible merchandise value", over_ref == 0, "error",
                         f"{over_ref} refunds exceed the net price paid" if over_ref else "refunds follow the net-price policy",
                         over_ref, "Refunds above the amount paid would overstate revenue loss."))
    non_refund_paid = int(((merged["return_status"] != "Refunded") & (merged["refund_amount"] > 0)).sum())
    checks.append(_check("returns: refunds only on Refunded status", non_refund_paid == 0, "error",
                         f"{non_refund_paid} rejected/pending returns carry a refund" if non_refund_paid else "consistent",
                         non_refund_paid, "Refund value would include unprocessed returns."))
    pend = merged["return_status"] == "Pending"
    pend_cost = int((pend & (merged[["reverse_logistics_cost", "restocking_cost", "inventory_write_off"]].sum(axis=1) > 0)).sum())
    checks.append(_check("returns: no costs booked on pending returns", pend_cost == 0, "error",
                         f"{pend_cost} pending returns with booked costs" if pend_cost else "consistent", pend_cost,
                         "Costs would be recognised before the return is processed."))
    cost_basis = merged["product_id"].map(products_u["unit_cost"]) * merged["return_quantity"]
    wo_over = int((merged["inventory_write_off"] > cost_basis + TOLERANCE).sum())
    checks.append(_check("returns: write-off <= cost of returned units", wo_over == 0, "error",
                         f"{wo_over} write-offs exceed inventory cost" if wo_over else "write-offs within cost basis",
                         wo_over, "Write-offs above cost would double count lost inventory."))

    # 9. Status consistency between orders and returns -------------------------------------------
    on_cancelled = int((merged["order_status"] == "Cancelled").sum())
    checks.append(_check("returns: none on cancelled lines", on_cancelled == 0, "error",
                         f"{on_cancelled} returns reference cancelled lines" if on_cancelled else "consistent",
                         on_cancelled, "Cancelled lines never shipped, so they cannot be returned."))
    refunded_qty = returns[returns["return_status"] == "Refunded"].groupby("order_line_id")["return_quantity"].sum()
    pending_lines = set(returns.loc[returns["return_status"] == "Pending", "order_line_id"])
    rq = refunded_qty.reindex(orders["order_line_id"]).fillna(0).to_numpy()
    expected = np.where(
        orders["order_status"] == "Cancelled", "Cancelled",
        np.where(rq >= q.to_numpy(), "Returned",
                 np.where(rq > 0, "Partially Returned",
                          np.where(orders["order_line_id"].isin(pending_lines), "Return in Progress", "Delivered"))),
    )
    inconsistent = int((orders["order_status"].to_numpy() != expected).sum())
    checks.append(_check("orders: status consistent with returns", inconsistent == 0, "error",
                         f"{inconsistent} lines whose status contradicts the returns file" if inconsistent else "consistent",
                         inconsistent, "Status-based counts would disagree with return-based metrics."))

    return {"passed": all(c["passed"] or c["severity"] == "warning" for c in checks),
            "checks": checks, "summary": _summary(checks)}


def _summary(checks: list[dict]) -> dict:
    errors = sum(1 for c in checks if not c["passed"] and c["severity"] == "error")
    warnings = sum(1 for c in checks if not c["passed"] and c["severity"] == "warning")
    return {"total_checks": len(checks), "passed": sum(c["passed"] for c in checks), "errors": errors, "warnings": warnings}


def profile_dataset(name: str, df: pd.DataFrame) -> dict[str, Any]:
    """Column-level profile: dtype, missing values, distinct values, example."""
    columns = []
    for col in df.columns:
        s = df[col]
        miss = int((s.isna() | (s.astype(str).str.strip() == "")).sum())
        note = EXPECTED_MISSING.get((name, col), "")
        example = s.dropna()
        example = example[example.astype(str).str.strip() != ""]
        columns.append({
            "name": col,
            "dtype": _friendly_dtype(s),
            "missing": miss,
            "missing_note": note if miss else "",
            "distinct": int(s.nunique(dropna=True)),
            "example": str(example.iloc[0]) if len(example) else "",
        })
    date_cols = [c for c in df.columns if c.endswith("_date")]
    coverage = {}
    for c in date_cols:
        d = _to_date(df[c].astype(str))
        if d.notna().any():
            coverage[c] = {"min": d.min().date().isoformat(), "max": d.max().date().isoformat()}
    return {
        "name": name,
        "rows": int(len(df)),
        "columns": columns,
        "duplicate_rows": int(df.duplicated().sum()),
        "duplicate_keys": int(df[PRIMARY_KEYS[name]].duplicated().sum()) if PRIMARY_KEYS.get(name) in df.columns else 0,
        "date_coverage": coverage,
    }


def _friendly_dtype(s: pd.Series) -> str:
    if pd.api.types.is_integer_dtype(s):
        return "integer"
    if pd.api.types.is_float_dtype(s):
        return "decimal"
    if pd.api.types.is_bool_dtype(s):
        return "boolean"
    if s.name and str(s.name).endswith("_date"):
        return "date (ISO text)"
    return "text"
