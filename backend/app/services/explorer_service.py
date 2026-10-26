"""Data Explorer: dataset previews, profiles, validation results and the data dictionary."""
from __future__ import annotations

import pandas as pd

from ..analytics.quality import profile_dataset
from .common import BadRequestError, NotFoundError, paginate, text_search
from .datastore import DATASETS, DataStore

DATA_DICTIONARY: dict[str, dict[str, str]] = {
    "orders": {
        "order_id": "Order identifier; an order can contain several lines.",
        "order_line_id": "Unique identifier of one product line within an order (grain of this file).",
        "order_date": "Date the order was placed (ISO yyyy-mm-dd).",
        "customer_id": "Synthetic customer key (FK to customers.csv).",
        "product_id": "Product key (FK to products.csv).",
        "quantity": "Units ordered on the line.",
        "unit_price": "List selling price per unit at order time, INR.",
        "discount_amount": "Total discount on the line, INR.",
        "shipping_fee": "Fee charged to the customer for the order (first line only). Excluded from merchandise metrics.",
        "shipping_region": "Destination state / region.",
        "shipping_zone": "Logistics zone from the fulfilment centre: Local, Metro, National, Remote.",
        "sales_channel": "Mobile App, Mobile Web, Desktop Web or Social Commerce.",
        "promised_delivery_date": "Delivery date promised at checkout.",
        "actual_delivery_date": "Actual delivery date; empty for cancelled lines.",
        "order_status": "Delivered, Partially Returned, Returned, Return in Progress or Cancelled.",
        "payment_method": "UPI, Cash on Delivery, Credit/Debit Card, Wallet or Net Banking.",
    },
    "returns": {
        "return_id": "Unique return identifier.",
        "order_id": "Order of the returned line.",
        "order_line_id": "Returned order line (FK to orders.csv).",
        "product_id": "Returned product.",
        "return_date": "Date the return was initiated.",
        "return_reason": "Customer-stated reason.",
        "return_quantity": "Units returned (never more than purchased).",
        "refund_amount": "Merchandise refund = units × net price paid per unit; 0 unless status is Refunded.",
        "reverse_logistics_cost": "Pickup/return transport, INR (doubled for rejected returns: item is re-shipped).",
        "restocking_cost": "Inspection, repackaging and disposal handling, INR.",
        "inventory_write_off": "Unrecoverable inventory cost, INR (returned units × unit cost × condition share).",
        "item_condition": "Inspection outcome; 'Awaiting inspection' for pending returns.",
        "return_status": "Refunded (processed), Rejected (failed inspection, no refund) or Pending (not processed).",
    },
    "products": {
        "product_id": "Product key.",
        "product_name": "Fictional product name.",
        "category": "Product category (10 categories).",
        "subcategory": "Product subcategory.",
        "unit_cost": "Landed inventory cost per unit, INR.",
        "selling_price": "List selling price, INR.",
        "supplier_id": "Fictional supplier code.",
        "product_weight": "Shipping weight in kg (drives reverse-logistics cost).",
        "product_status": "Active or Discontinued.",
        "return_window_days": "Days after delivery during which a return is accepted.",
    },
    "customers": {
        "customer_id": "Synthetic customer key. No names, contact details or other personal data exist.",
        "customer_segment": "Plus Member, Regular, Value Seeker or Business Buyer.",
        "customer_region": "Home region.",
        "signup_date": "Account creation date.",
        "historical_order_count_band": "Orders placed before the analysis period: 0, 1-3, 4-10, 11+.",
    },
}


def _frame(store: DataStore, name: str) -> pd.DataFrame:
    if name not in DATASETS:
        raise NotFoundError(f"Unknown dataset '{name}'. Use one of: {', '.join(DATASETS)}")
    return store.raw[name]


def quality(store: DataStore) -> dict:
    model = store.model
    return {
        "status": store.status(),
        "dataset_info": store.dataset_info,
        "validation": store.validation,
        "profiles": [profile_dataset(n, store.raw[n]) for n in DATASETS],
        "dictionary": DATA_DICTIONARY,
        "snapshot_date": model.snapshot_date.isoformat(),
    }


def preview(store: DataStore, name: str, search: str | None, sort_by: str | None, sort_dir: str,
            page: int, page_size: int) -> dict:
    df = _frame(store, name)
    if search:
        df = text_search(df, search, list(df.columns))
    if sort_by:
        if sort_by not in df.columns:
            raise BadRequestError(f"Unknown column '{sort_by}' for {name}")
        if sort_dir not in ("asc", "desc"):
            raise BadRequestError("sort_dir must be 'asc' or 'desc'")
        numeric = pd.to_numeric(df[sort_by], errors="coerce")
        key = numeric if numeric.notna().mean() > 0.95 else df[sort_by]
        df = df.assign(_k=key).sort_values("_k", ascending=sort_dir == "asc", kind="mergesort").drop(columns="_k")
    return {"dataset": name, "columns": list(store.raw[name].columns), **paginate(df, page, page_size)}
