"""
ShopSphere | Return Intelligence Lab — synthetic data generator.

Generates four internally consistent CSV files for a FICTIONAL Indian
e-commerce company and validates them before reporting success:

    data/products.csv   data/customers.csv   data/orders.csv   data/returns.csv

Everything is driven by a fixed random seed, so running the script twice
produces byte-identical files.

Usage (from the repository root, with the backend virtual environment active):

    python scripts/generate_data.py            # default seed 20251001
    python scripts/generate_data.py --seed 7   # alternative reproducible dataset

ALL DATA IS SYNTHETIC. Company, customers, products and transactions are
invented for portfolio/demonstration purposes only.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.analytics.quality import run_validation  # noqa: E402  (shared validator)

DEFAULT_SEED = 20251001
PERIOD_START = date(2025, 10, 1)
PERIOD_END = date(2026, 9, 30)
SNAPSHOT_DATE = date(2026, 10, 20)  # data extract date: returns after this are unknown
PROCESSING_DAYS = 6  # returns initiated within the last N days before the snapshot are still pending
BASE_ORDERS_PER_DAY = 40
RETURN_CALIBRATION = 0.78  # global scaler so overall unit return rate lands near 11-12 %

# --------------------------------------------------------------------------- #
# Reference data
# --------------------------------------------------------------------------- #
REGIONS = {
    # state: (order share, shipping zone)
    "Maharashtra": (0.16, "Local"),
    "Karnataka": (0.12, "Local"),
    "Delhi NCR": (0.13, "Metro"),
    "Tamil Nadu": (0.10, "Metro"),
    "Telangana": (0.08, "Metro"),
    "West Bengal": (0.07, "Metro"),
    "Uttar Pradesh": (0.10, "National"),
    "Gujarat": (0.08, "National"),
    "Rajasthan": (0.06, "National"),
    "Kerala": (0.06, "National"),
    "Assam": (0.04, "Remote"),
}
ZONE_PROMISE_DAYS = {"Local": (2, 3), "Metro": (3, 4), "National": (4, 6), "Remote": (6, 8)}
ZONE_REVERSE_BASE = {"Local": 70.0, "Metro": 90.0, "National": 115.0, "Remote": 165.0}

CHANNELS = ["Mobile App", "Mobile Web", "Desktop Web", "Social Commerce"]
PAYMENTS = ["UPI", "Cash on Delivery", "Credit/Debit Card", "Wallet", "Net Banking"]

SEGMENTS = {
    # segment: (customer share, order-frequency weight, channel probs, payment probs, return multiplier)
    "Plus Member": (0.18, 2.4, [0.70, 0.08, 0.20, 0.02], [0.52, 0.06, 0.30, 0.08, 0.04], 0.88),
    "Regular": (0.52, 1.0, [0.58, 0.15, 0.20, 0.07], [0.46, 0.24, 0.17, 0.07, 0.06], 1.00),
    "Value Seeker": (0.22, 0.9, [0.55, 0.20, 0.10, 0.15], [0.36, 0.42, 0.10, 0.08, 0.04], 1.12),
    "Business Buyer": (0.08, 1.3, [0.25, 0.05, 0.68, 0.02], [0.30, 0.00, 0.40, 0.00, 0.30], 0.70),
}

RETURN_REASONS = [
    "Size or fit issue",
    "Quality not as expected",
    "Description or image mismatch",
    "Damaged in transit",
    "Defective / not working",
    "Wrong item delivered",
    "Changed mind / no longer needed",
    "Late delivery",
]

CONDITION_WRITE_OFF = {
    # condition: share of unit cost that cannot be recovered (inventory write-off basis)
    "Resellable - Unopened": 0.00,
    "Resellable - Opened": 0.10,   # repackaging / mark-down loss
    "Open Box - B Grade": 0.45,    # sold through liquidation channel
    "Damaged": 1.00,
    "Defective": 0.65,             # 35 % recovered through return-to-vendor credit
}


@dataclass(frozen=True)
class CategorySpec:
    base_return_rate: float
    cost_ratio: tuple[float, float]
    price: tuple[int, int]
    weight_kg: tuple[float, float]
    return_window_days: int
    popularity: float
    max_discount: float
    multi_qty_prob: float
    inspection_cost: float
    reason_weights: tuple[float, ...]  # aligned with RETURN_REASONS
    subcategories: dict[str, list[str]]
    brands: tuple[str, ...]


CATEGORIES: dict[str, CategorySpec] = {
    "Women's Fashion": CategorySpec(
        0.20, (0.38, 0.50), (449, 3999), (0.2, 0.9), 10, 0.17, 0.70, 0.14, 30,
        (0.42, 0.14, 0.17, 0.03, 0.01, 0.04, 0.15, 0.04),
        {"Kurtas & Kurtis": ["Cotton Kurta", "Anarkali Kurta", "Straight Kurti", "Printed Kurti Set"],
         "Dresses": ["A-Line Dress", "Maxi Dress", "Wrap Dress"],
         "Sarees": ["Silk Blend Saree", "Georgette Saree", "Cotton Saree"],
         "Tops & Tees": ["Crop Top", "Relaxed Tee", "Peplum Top"]},
        ("Aaranya", "Saanjh", "Meher", "Ivory Loom"),
    ),
    "Men's Fashion": CategorySpec(
        0.15, (0.40, 0.52), (399, 3499), (0.2, 0.9), 10, 0.13, 0.65, 0.12, 30,
        (0.40, 0.15, 0.15, 0.03, 0.01, 0.05, 0.16, 0.05),
        {"Shirts": ["Oxford Shirt", "Linen Shirt", "Checked Shirt"],
         "T-Shirts": ["Crew Neck Tee", "Polo T-Shirt", "Graphic Tee"],
         "Jeans & Trousers": ["Slim Fit Jeans", "Chino Trousers", "Cargo Pants"],
         "Ethnic Wear": ["Kurta Pyjama Set", "Nehru Jacket"]},
        ("Rangrez", "Northline", "Kaveri Mills", "Urban Tant"),
    ),
    "Footwear": CategorySpec(
        0.16, (0.42, 0.55), (599, 4999), (0.6, 1.4), 10, 0.10, 0.60, 0.04, 35,
        (0.45, 0.17, 0.10, 0.04, 0.04, 0.04, 0.12, 0.04),
        {"Sneakers": ["Canvas Sneakers", "Chunky Sneakers", "Slip-On Sneakers"],
         "Sandals & Floaters": ["Leather Sandals", "Sports Floaters", "Kolhapuri Chappal"],
         "Formal Shoes": ["Derby Shoes", "Oxford Shoes", "Loafers"],
         "Sports Shoes": ["Running Shoes", "Training Shoes"]},
        ("Stridewell", "Paduka & Co", "Trekko", "Solemate"),
    ),
    "Electronics Accessories": CategorySpec(
        0.09, (0.62, 0.75), (399, 7999), (0.1, 0.6), 7, 0.12, 0.55, 0.06, 140,
        (0.00, 0.20, 0.12, 0.08, 0.36, 0.06, 0.12, 0.06),
        {"Earbuds & Headphones": ["ANC Earbuds", "Wireless Neckband", "Over-Ear Headphones"],
         "Smartwatches": ["Fitness Smartwatch", "AMOLED Smartwatch"],
         "Power Banks": ["20000mAh Power Bank", "10000mAh Slim Power Bank"],
         "Chargers & Cables": ["65W GaN Charger", "Braided USB-C Cable", "Car Charger"]},
        ("Voltix", "Sonora", "Pulsewave", "Kinetic Labs"),
    ),
    "Mobiles & Tablets": CategorySpec(
        0.05, (0.82, 0.90), (7999, 34999), (0.25, 0.6), 7, 0.035, 0.15, 0.00, 160,
        (0.00, 0.14, 0.14, 0.10, 0.40, 0.08, 0.10, 0.04),
        {"Smartphones": ["5G Smartphone 8GB/128GB", "5G Smartphone 12GB/256GB", "4G Smartphone 6GB/128GB"],
         "Tablets": ["10.6-inch Tablet", "8-inch Kids Tablet"]},
        ("Nexora", "Aurum Mobile", "Zephyr"),
    ),
    "Home & Kitchen": CategorySpec(
        0.07, (0.50, 0.62), (299, 5999), (0.5, 4.5), 7, 0.12, 0.60, 0.10, 45,
        (0.00, 0.22, 0.16, 0.26, 0.16, 0.06, 0.10, 0.04),
        {"Cookware": ["Non-Stick Kadai", "Pressure Cooker 5L", "Tawa"],
         "Small Appliances": ["Mixer Grinder 750W", "Electric Kettle", "Hand Blender"],
         "Storage": ["Glass Jar Set", "Steel Lunch Box"],
         "Bed & Bath": ["Cotton Bedsheet Set", "Bath Towel Pack"]},
        ("Rasoi Craft", "Ghar Essentials", "Tulsi Home", "Kitchenova"),
    ),
    "Beauty & Personal Care": CategorySpec(
        0.04, (0.35, 0.46), (199, 2499), (0.1, 0.5), 7, 0.11, 0.50, 0.15, 25,
        (0.00, 0.24, 0.18, 0.18, 0.06, 0.10, 0.20, 0.04),
        {"Skincare": ["Vitamin C Serum", "SPF 50 Sunscreen", "Niacinamide Moisturiser"],
         "Haircare": ["Onion Hair Oil", "Keratin Shampoo"],
         "Fragrances": ["Eau de Parfum 100ml", "Attar Roll-On"],
         "Grooming Devices": ["Beard Trimmer", "Hair Dryer"]},
        ("Kesari Botanics", "Glowveda", "Nila Naturals"),
    ),
    "Sports & Fitness": CategorySpec(
        0.09, (0.50, 0.60), (299, 6999), (0.3, 6.0), 10, 0.07, 0.55, 0.08, 40,
        (0.22, 0.20, 0.14, 0.12, 0.08, 0.06, 0.14, 0.04),
        {"Yoga & Mats": ["TPE Yoga Mat", "Yoga Block Set"],
         "Gym Equipment": ["Adjustable Dumbbells", "Resistance Band Set", "Kettlebell 8kg"],
         "Cycling": ["Cycling Helmet", "Bike Light Set"],
         "Activewear": ["Dry-Fit Track Pants", "Training Shorts"]},
        ("Kridaa", "Peakform", "Sahyadri Sports"),
    ),
    "Books & Stationery": CategorySpec(
        0.03, (0.55, 0.68), (149, 1299), (0.2, 1.0), 7, 0.08, 0.40, 0.15, 20,
        (0.00, 0.12, 0.10, 0.34, 0.04, 0.22, 0.14, 0.04),
        {"Books": ["Exam Prep Guide", "Fiction Paperback", "Business Bestseller"],
         "Notebooks & Planners": ["A5 Hardbound Notebook", "2026 Daily Planner"],
         "Art Supplies": ["Watercolour Set", "Sketch Pen Pack"]},
        ("Pustak Press", "Kalam & Co", "Inkwell"),
    ),
    "Home Décor & Furnishing": CategorySpec(
        0.10, (0.45, 0.58), (399, 8999), (0.5, 12.0), 7, 0.05, 0.65, 0.05, 50,
        (0.00, 0.22, 0.22, 0.30, 0.04, 0.06, 0.12, 0.04),
        {"Lighting": ["Ceramic Table Lamp", "Rattan Floor Lamp"],
         "Wall Décor": ["Framed Canvas Print", "Brass Wall Mirror"],
         "Cushions & Curtains": ["Blackout Curtain Pair", "Block-Print Cushion Covers"],
         "Small Furniture": ["Sheesham Side Table", "Folding Study Desk"]},
        ("Haveli Living", "Jharokha", "Neem Tree Decor"),
    ),
}

# Injected, documented anomalies so the anomaly detector has genuine signals.
ANOMALY_SUPPLIER = "SUP-07"              # Footwear supplier with a faulty batch
ANOMALY_SUPPLIER_WINDOW = (date(2026, 6, 1), date(2026, 7, 31))
ANOMALY_COURIER_REGION = "Uttar Pradesh"     # courier contract change raises reverse costs
ANOMALY_COURIER_WINDOW = (date(2026, 6, 1), date(2026, 9, 30))


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def season_factor(d: date) -> tuple[float, bool]:
    """Return (demand multiplier, is_sale_event) for a calendar day."""
    m, day = d.month, d.day
    if m == 10 and day <= 10:
        return 2.0, True       # festive "Big Billion"-style sale (fictional)
    if m == 10 and day <= 25:
        return 1.55, True      # Diwali run-up
    if m == 10:
        return 1.15, False
    if m == 11:
        return 1.15, False
    if m == 12:
        return (1.35, True) if day >= 20 else (1.0, False)
    if m == 1:
        return (1.6, True) if 15 <= day <= 20 else (0.95, False)
    if m == 2:
        return 0.85, False
    if m == 3:
        return 0.9, False
    if m == 7 and 10 <= day <= 15:
        return 1.6, True
    if m == 8 and 6 <= day <= 10:
        return 1.6, True
    if m == 9:
        return (1.45, True) if day >= 25 else (1.05, False)
    return 1.0, False


def build_products(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    pid = 1
    supplier_no = 1
    for cat_idx, (cat, spec) in enumerate(CATEGORIES.items()):
        # each category gets 2-3 suppliers; Footwear's second supplier is SUP-07
        suppliers = [f"SUP-{supplier_no + i:02d}" for i in range(3 if cat_idx % 2 == 0 else 2)]
        supplier_no += len(suppliers)
        n_products = int(rng.integers(16, 21))
        used_names: set[str] = set()
        for _ in range(n_products):
            sub = rng.choice(list(spec.subcategories.keys()))
            for _attempt in range(20):
                item = rng.choice(spec.subcategories[sub])
                brand = rng.choice(spec.brands)
                variant = rng.choice(["Classic", "Pro", "Lite", "Plus", "Essential", "Signature", "Max", "Neo"])
                name = f"{brand} {item} {variant}"
                if name not in used_names:
                    break
            used_names.add(name)
            lo, hi = spec.price
            # log-uniform price, rounded to Indian retail price points (x99)
            price = float(np.exp(rng.uniform(np.log(lo), np.log(hi))))
            price = max(lo, round(price / 100) * 100 - 1)
            cost_ratio = rng.uniform(*spec.cost_ratio)
            if rng.random() < 0.10:  # thin-margin / clearance-sourced SKUs
                cost_ratio = min(0.95, spec.cost_ratio[1] + rng.uniform(0.15, 0.30))
            cost = round(price * cost_ratio, 2)
            weight = round(float(rng.uniform(*spec.weight_kg)), 2)
            rows.append(
                {
                    "product_id": f"P{pid:04d}",
                    "product_name": name,
                    "category": cat,
                    "subcategory": sub,
                    "unit_cost": cost,
                    "selling_price": float(price),
                    "supplier_id": str(rng.choice(suppliers)),
                    "product_weight": weight,
                    "product_status": "Discontinued" if rng.random() < 0.08 else "Active",
                    "return_window_days": spec.return_window_days,
                }
            )
            pid += 1
    df = pd.DataFrame(rows)
    # Hidden generator-only attribute: product-level return propensity.
    mult = np.exp(rng.normal(0.0, 0.25, len(df)))
    problem = rng.random(len(df)) < 0.14
    mult[problem] *= rng.uniform(1.8, 2.6, problem.sum())
    df["_return_mult"] = mult
    df["_popularity"] = np.exp(rng.normal(0, 0.6, len(df)))
    return df


def build_customers(rng: np.random.Generator, n: int = 7500) -> pd.DataFrame:
    seg_names = list(SEGMENTS)
    seg_p = np.array([SEGMENTS[s][0] for s in seg_names])
    reg_names = list(REGIONS)
    reg_p = np.array([REGIONS[r][0] for r in reg_names])
    segments = rng.choice(seg_names, n, p=seg_p / seg_p.sum())
    regions = rng.choice(reg_names, n, p=reg_p / reg_p.sum())
    # signup: 75 % before the analysis window, 25 % during it
    start = date(2019, 1, 1)
    before_days = (PERIOD_START - start).days
    during_days = (PERIOD_END - PERIOD_START).days
    signups = []
    bands = []
    for i in range(n):
        if rng.random() < 0.75:
            s = start + timedelta(days=int(rng.integers(0, before_days)))
            tenure_years = (PERIOD_START - s).days / 365.0
            freq = SEGMENTS[segments[i]][1]
            hist = rng.poisson(max(0.3, tenure_years * 2.2 * freq))
            band = "0" if hist == 0 else "1-3" if hist <= 3 else "4-10" if hist <= 10 else "11+"
        else:
            s = PERIOD_START + timedelta(days=int(rng.integers(0, during_days)))
            band = "0"
        signups.append(s)
        bands.append(band)
    return pd.DataFrame(
        {
            "customer_id": [f"C{i + 1:05d}" for i in range(n)],
            "customer_segment": segments,
            "customer_region": regions,
            "signup_date": [d.isoformat() for d in signups],
            "historical_order_count_band": bands,
        }
    )


def pick_reason(rng, spec: CategorySpec, delay: int, disc_pct: float, supplier_anomaly: bool) -> str:
    w = np.array(spec.reason_weights, dtype=float)
    if delay >= 3:
        w[RETURN_REASONS.index("Late delivery")] += 0.25
    if disc_pct >= 0.40:
        w[RETURN_REASONS.index("Changed mind / no longer needed")] += 0.12
    if supplier_anomaly:
        w[RETURN_REASONS.index("Quality not as expected")] += 0.9
        w[RETURN_REASONS.index("Defective / not working")] += 0.4
    return str(rng.choice(RETURN_REASONS, p=w / w.sum()))


def pick_condition(rng, reason: str, category: str) -> str:
    conds = list(CONDITION_WRITE_OFF)
    if reason == "Damaged in transit":
        return "Damaged"
    if reason == "Defective / not working":
        return "Defective"
    if reason == "Wrong item delivered":
        p = [0.80, 0.18, 0.02, 0.0, 0.0]
    elif reason in ("Quality not as expected", "Description or image mismatch"):
        p = [0.15, 0.48, 0.34, 0.03, 0.0]
    else:  # size, changed mind, late delivery
        p = [0.55, 0.30, 0.12, 0.03, 0.0]
    return str(rng.choice(conds, p=p))


# --------------------------------------------------------------------------- #
# Main generation
# --------------------------------------------------------------------------- #
def generate(seed: int = DEFAULT_SEED) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    products = build_products(rng)
    customers = build_customers(rng)

    cat_names = list(CATEGORIES)
    cat_pop = np.array([CATEGORIES[c].popularity for c in cat_names])
    cat_pop = cat_pop / cat_pop.sum()
    prod_by_cat = {c: products.index[products["category"] == c].to_numpy() for c in cat_names}
    prod_pop = {c: products.loc[idx, "_popularity"].to_numpy() / products.loc[idx, "_popularity"].sum()
                for c, idx in prod_by_cat.items()}
    cat_median_price = products.groupby("category")["selling_price"].median().to_dict()

    seg_of = customers.set_index("customer_id")["customer_segment"].to_dict()
    region_of = customers.set_index("customer_id")["customer_region"].to_dict()
    cust_ids = customers["customer_id"].to_numpy()
    cust_w = customers["customer_segment"].map(lambda s: SEGMENTS[s][1]).to_numpy(dtype=float)
    # customers who signed up during the window can only order after signup
    signup = pd.to_datetime(customers["signup_date"]).dt.date.to_numpy()
    cust_w = cust_w * np.exp(rng.normal(0, 0.5, len(cust_w)))
    reg_names = list(REGIONS)
    reg_p = np.array([REGIONS[r][0] for r in reg_names])
    reg_p = reg_p / reg_p.sum()

    order_rows: list[dict] = []
    return_rows: list[dict] = []
    order_no = 0
    line_no = 0
    return_no = 0

    d = PERIOD_START
    while d <= PERIOD_END:
        factor, is_sale = season_factor(d)
        weekday_f = 1.12 if d.weekday() >= 5 else 1.0
        n_orders = int(rng.poisson(BASE_ORDERS_PER_DAY * factor * weekday_f))
        eligible = signup <= d
        w = np.where(eligible, cust_w, 0.0)
        w = w / w.sum()
        chosen = rng.choice(cust_ids, n_orders, p=w)
        for cid in chosen:
            order_no += 1
            order_id = f"ORD-{order_no:07d}"
            seg = seg_of[cid]
            _, _, ch_p, pay_p, seg_ret_mult = SEGMENTS[seg]
            region = region_of[cid] if rng.random() < 0.92 else str(rng.choice(reg_names, p=reg_p))
            zone = REGIONS[region][1]
            channel = str(rng.choice(CHANNELS, p=ch_p))
            payment = str(rng.choice(PAYMENTS, p=np.array(pay_p) / np.sum(pay_p)))
            cancel_p = 0.085 if payment == "Cash on Delivery" else 0.04
            cancelled = rng.random() < cancel_p
            pmin, pmax = ZONE_PROMISE_DAYS[zone]
            promised = d + timedelta(days=int(rng.integers(pmin, pmax + 1)))
            if cancelled:
                delay = 0
                delivered = None
            else:
                r = rng.random()
                late_boost = (0.10 if is_sale else 0.0) + (0.08 if zone == "Remote" else 0.0)
                if r < 0.68 - late_boost:
                    delay = int(rng.integers(-1, 1))
                elif r < 0.88 - late_boost / 2:
                    delay = int(rng.integers(1, 3))
                elif r < 0.975:
                    delay = int(rng.integers(3, 6))
                else:
                    delay = int(rng.integers(6, 11))
                delivered = promised + timedelta(days=delay)
                if delivered <= d:
                    delivered = d + timedelta(days=1)
                    delay = (delivered - promised).days

            n_lines = int(rng.choice([1, 2, 3], p=[0.76, 0.18, 0.06]))
            cats = rng.choice(cat_names, n_lines, p=cat_pop)
            used_products: set[int] = set()
            lines_this_order: list[dict] = []
            for cat in cats:
                spec = CATEGORIES[cat]
                pidx = int(rng.choice(prod_by_cat[cat], p=prod_pop[cat]))
                if pidx in used_products:
                    continue
                used_products.add(pidx)
                prod = products.loc[pidx]
                qty = 1
                if rng.random() < spec.multi_qty_prob:
                    qty = int(rng.choice([2, 3], p=[0.8, 0.2]))
                if seg == "Business Buyer" and cat in ("Books & Stationery", "Electronics Accessories", "Home & Kitchen"):
                    qty += int(rng.integers(0, 4))
                price = float(prod["selling_price"])
                gross = qty * price
                disc_prob = 0.88 if is_sale else 0.50
                if rng.random() < disc_prob:
                    base = rng.beta(2.0, 5.0) * spec.max_discount
                    if is_sale:
                        base = min(spec.max_discount, base * 1.45)
                    disc_pct = float(np.clip(base, 0.02, spec.max_discount))
                else:
                    disc_pct = 0.0
                discount = round(gross * disc_pct, 2)
                line_no += 1
                lines_this_order.append(
                    dict(
                        order_line_id=f"OL-{line_no:07d}",
                        order_id=order_id,
                        order_date=d.isoformat(),
                        customer_id=cid,
                        product_id=prod["product_id"],
                        quantity=qty,
                        unit_price=price,
                        discount_amount=discount,
                        shipping_fee=0.0,
                        shipping_region=region,
                        shipping_zone=zone,
                        sales_channel=channel,
                        promised_delivery_date=promised.isoformat(),
                        actual_delivery_date=delivered.isoformat() if delivered else "",
                        order_status="Cancelled" if cancelled else "Delivered",
                        payment_method=payment,
                        _pidx=pidx,
                        _disc_pct=disc_pct,
                        _delay=delay,
                    )
                )
            if not lines_this_order:
                continue
            net_order = sum(l["quantity"] * l["unit_price"] - l["discount_amount"] for l in lines_this_order)
            if not cancelled and seg != "Plus Member" and net_order < 499:
                lines_this_order[0]["shipping_fee"] = 49.0

            # ------------------------------ returns ------------------------------ #
            if not cancelled:
                for line in lines_this_order:
                    prod = products.loc[line["_pidx"]]
                    cat = prod["category"]
                    spec = CATEGORIES[cat]
                    disc_pct = line["_disc_pct"]
                    delay = line["_delay"]
                    p = RETURN_CALIBRATION * spec.base_return_rate * prod["_return_mult"] * seg_ret_mult
                    if disc_pct >= 0.45:
                        p *= 1.55
                    elif disc_pct >= 0.30:
                        p *= 1.30
                    if delay >= 6:
                        p *= 1.70
                    elif delay >= 3:
                        p *= 1.40
                    if payment == "Cash on Delivery":
                        p *= 1.35
                    if channel == "Social Commerce":
                        p *= 1.25
                    value_ratio = (line["quantity"] * line["unit_price"] - line["discount_amount"]) / cat_median_price[cat]
                    if value_ratio >= 2.0:
                        p *= 1.15
                    if line["quantity"] >= 2 and cat in ("Women's Fashion", "Men's Fashion", "Footwear"):
                        p *= 1.45
                    supplier_anom = (
                        prod["supplier_id"] == ANOMALY_SUPPLIER
                        and ANOMALY_SUPPLIER_WINDOW[0] <= d <= ANOMALY_SUPPLIER_WINDOW[1]
                    )
                    if supplier_anom:
                        p *= 2.6
                    p = min(p, 0.85)
                    if rng.random() >= p:
                        continue
                    delivered = date.fromisoformat(line["actual_delivery_date"])
                    window = int(prod["return_window_days"])
                    ret_date = delivered + timedelta(days=int(min(window, 1 + rng.geometric(0.28))))
                    if ret_date > SNAPSHOT_DATE:
                        continue  # would happen after the data extract: unknown today
                    qty = line["quantity"]
                    if qty > 1 and rng.random() < 0.55:
                        rqty = int(rng.integers(1, qty))  # partial return
                    else:
                        rqty = qty
                    reason = pick_reason(rng, spec, delay, disc_pct, supplier_anom)
                    condition = pick_condition(rng, reason, cat)
                    if ret_date > SNAPSHOT_DATE - timedelta(days=PROCESSING_DAYS):
                        status = "Pending"
                    else:
                        reject_p = 0.10 if reason == "Changed mind / no longer needed" else 0.035
                        if cat == "Beauty & Personal Care" and condition != "Resellable - Unopened":
                            reject_p = 0.30
                        status = "Rejected" if rng.random() < reject_p else "Refunded"

                    net_unit = (line["quantity"] * line["unit_price"] - line["discount_amount"]) / line["quantity"]
                    unit_cost = float(prod["unit_cost"])
                    shipment_kg = rqty * float(prod["product_weight"])
                    rl = ZONE_REVERSE_BASE[line["shipping_zone"]] + 40.0 * max(0.0, shipment_kg - 0.5)
                    if line["shipping_region"] == ANOMALY_COURIER_REGION and ANOMALY_COURIER_WINDOW[0] <= ret_date <= ANOMALY_COURIER_WINDOW[1]:
                        rl *= 1.45
                    opened = condition in ("Resellable - Opened", "Open Box - B Grade")
                    rs = spec.inspection_cost + 15.0 * rqty + (35.0 * rqty if opened else 0.0)
                    if condition in ("Damaged", "Defective"):
                        rs += 20.0 * rqty  # disposal / RTV handling
                    wo_frac = CONDITION_WRITE_OFF[condition]
                    if cat == "Beauty & Personal Care" and condition != "Resellable - Unopened":
                        wo_frac = 1.0  # hygiene rule: opened beauty products cannot be resold

                    if status == "Refunded":
                        refund = round(rqty * net_unit, 2)
                        rev_cost = round(rl, 2)
                        restock = round(rs, 2)
                        write_off = round(rqty * unit_cost * wo_frac, 2)
                    elif status == "Rejected":
                        # pickup + re-shipment to customer, inspection only; customer keeps item
                        refund = 0.0
                        rev_cost = round(rl * 2, 2)
                        restock = round(spec.inspection_cost, 2)
                        write_off = 0.0
                    else:  # Pending: nothing booked yet
                        refund = rev_cost = restock = write_off = 0.0

                    return_no += 1
                    return_rows.append(
                        dict(
                            return_id=f"RET-{return_no:06d}",
                            order_id=line["order_id"],
                            order_line_id=line["order_line_id"],
                            product_id=line["product_id"],
                            return_date=ret_date.isoformat(),
                            return_reason=reason,
                            return_quantity=rqty,
                            refund_amount=refund,
                            reverse_logistics_cost=rev_cost,
                            restocking_cost=restock,
                            inventory_write_off=write_off,
                            item_condition=condition if status != "Pending" else "Awaiting inspection",
                            return_status=status,
                        )
                    )
                    if status == "Refunded":
                        line["order_status"] = "Returned" if rqty == qty else "Partially Returned"
                    elif status == "Pending":
                        line["order_status"] = "Return in Progress"
            order_rows.extend(lines_this_order)
        d += timedelta(days=1)

    orders = pd.DataFrame(order_rows).drop(columns=["_pidx", "_disc_pct", "_delay"])
    returns = pd.DataFrame(return_rows)
    products_out = products.drop(columns=["_return_mult", "_popularity"])
    return {"products": products_out, "customers": customers, "orders": orders, "returns": returns}


def generator_versions() -> dict[str, str]:
    """Library versions used. NumPy guarantees identical random streams only within a version."""
    import platform

    return {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__}


ORDER_COLUMNS = [
    "order_id", "order_line_id", "order_date", "customer_id", "product_id", "quantity", "unit_price",
    "discount_amount", "shipping_fee", "shipping_region", "shipping_zone", "sales_channel",
    "promised_delivery_date", "actual_delivery_date", "order_status", "payment_method",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ShopSphere synthetic datasets")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", type=Path, default=ROOT / "data")
    args = parser.parse_args()

    print(f"Generating synthetic data (seed={args.seed}) ...")
    frames = generate(args.seed)
    frames["orders"] = frames["orders"][ORDER_COLUMNS]

    report = run_validation(frames)
    for check in report["checks"]:
        mark = "PASS" if check["passed"] else ("WARN" if check["severity"] == "warning" else "FAIL")
        print(f"  [{mark}] {check['name']}: {check['detail']}")
    if not report["passed"]:
        print("\nValidation FAILED - CSV files were NOT written.", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    for name, df in frames.items():
        path = args.out / f"{name}.csv"
        df.to_csv(path, index=False, lineterminator="\n")
        print(f"  wrote {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}  ({len(df):,} rows)")

    o, r = frames["orders"], frames["returns"]
    elig = o[o["order_status"] != "Cancelled"]
    refunded = r[r["return_status"] == "Refunded"]
    info = {
        "description": "Synthetic data for the fictional ShopSphere marketplace. Not real business data.",
        "seed": args.seed,
        "snapshot_date": SNAPSHOT_DATE.isoformat(),
        "period_start": PERIOD_START.isoformat(),
        "period_end": PERIOD_END.isoformat(),
        "generated_with": generator_versions(),
        "rows": {name: int(len(df)) for name, df in frames.items()},
        "unit_return_rate": round(float(refunded["return_quantity"].sum() / elig["quantity"].sum()), 6),
        "order_return_rate": round(float(refunded["order_id"].nunique() / elig["order_id"].nunique()), 6),
        "injected_anomalies": [
            f"Footwear supplier {ANOMALY_SUPPLIER}: faulty batch, higher quality/defect returns "
            f"{ANOMALY_SUPPLIER_WINDOW[0]:%b %Y}-{ANOMALY_SUPPLIER_WINDOW[1]:%b %Y}",
            f"{ANOMALY_COURIER_REGION}: reverse-logistics courier cost +45% from {ANOMALY_COURIER_WINDOW[0]:%b %Y}",
        ],
    }
    (args.out / "dataset_info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    print(f"  wrote dataset_info.json")
    print("\nSummary")
    print(f"  order lines        : {len(o):,}  (orders: {o['order_id'].nunique():,})")
    print(f"  eligible lines     : {len(elig):,}  cancelled lines: {len(o) - len(elig):,}")
    print(f"  return records     : {len(r):,}  (refunded {len(refunded):,}, "
          f"rejected {(r['return_status'] == 'Rejected').sum():,}, pending {(r['return_status'] == 'Pending').sum():,})")
    print(f"  unit return rate   : {refunded['return_quantity'].sum() / elig['quantity'].sum():.2%}")
    print(f"  order return rate  : {refunded['order_id'].nunique() / elig['order_id'].nunique():.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
