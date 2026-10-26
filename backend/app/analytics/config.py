"""
Business configuration shared by every analytical module.

Changing a value here changes it everywhere (API, insights, simulator, tests).
All thresholds are illustrative modelling choices, not industry benchmarks.
"""
from __future__ import annotations

# Illustrative business target shown on charts. NOT an industry benchmark.
RETURN_RATE_TARGET = 0.08

# Order statuses that represent completed (eligible) sales.
CANCELLED_STATUS = "Cancelled"

# Return statuses
PROCESSED_REFUND = "Refunded"   # counted in returned units and refund value
REJECTED = "Rejected"           # costs incurred, customer keeps item, no refund
PENDING = "Pending"             # nothing booked yet

DAMAGE_REASONS = ("Damaged in transit", "Defective / not working")
SIZE_QUALITY_MISMATCH_REASONS = ("Size or fit issue", "Quality not as expected", "Description or image mismatch")

# --------------------------------------------------------------------------- #
# Heuristic return-risk score (0-100). Weights must sum to 100.
# Each factor is scaled to 0..1 between `low` and `high` (linear, clipped).
# Only information available before a potential return is used.
# --------------------------------------------------------------------------- #
RISK_WEIGHTS: dict[str, float] = {
    "product_history": 28.0,   # product's historical unit return rate (prior orders only)
    "category_history": 14.0,  # category's historical unit return rate (prior orders only)
    "discount": 16.0,          # discount % on the line
    "shipping_delay": 14.0,    # days delivered after the promised date (known at delivery)
    "order_value": 8.0,        # line value relative to the category's median list price
    "cash_on_delivery": 12.0,  # payment method chosen at checkout
    "multi_unit": 8.0,         # 2+ units of the same item (size/colour bracketing)
}
RISK_SCALES: dict[str, tuple[float, float]] = {
    "product_history": (0.04, 0.24),
    "category_history": (0.03, 0.16),
    "discount": (0.0, 0.45),
    "shipping_delay": (0.0, 5.0),
    "order_value": (0.8, 2.5),
}
RISK_FACTOR_LABELS: dict[str, str] = {
    "product_history": "Product return history",
    "category_history": "Category return history",
    "discount": "Discount depth",
    "shipping_delay": "Late delivery",
    "order_value": "High value vs category",
    "cash_on_delivery": "Cash on delivery",
    "multi_unit": "Multiple units",
}
RISK_BANDS = (("Low", 0, 34), ("Medium", 35, 64), ("High", 65, 100))
MEDIUM_THRESHOLD = 35
HIGH_THRESHOLD = 65

# Historical features: a return only becomes "known" this many days after it is
# initiated (pickup + inspection), and only orders delivered before the scored
# order's date contribute to the denominator. Prevents look-ahead leakage.
HISTORY_LAG_DAYS = 7
GLOBAL_PRIOR_RETURN_RATE = 0.10    # used before any history exists (documented assumption)
CATEGORY_SMOOTHING_UNITS = 100.0   # pseudo-units pulling sparse category history to the prior
PRODUCT_SMOOTHING_UNITS = 40.0     # pseudo-units pulling sparse product history to the category

# --------------------------------------------------------------------------- #
# What-if simulator presets (all values are hypothetical assumptions).
# Spend is expressed as a share of baseline incremental return costs so presets
# scale sensibly when filters narrow the data; the UI shows the INR amount.
# --------------------------------------------------------------------------- #
SCENARIO_PRESETS = {
    "conservative": {"label": "Conservative", "return_reduction": 0.05, "logistics_reduction": 0.05,
                     "write_off_reduction": 0.10, "retained_sale_share": 0.60, "spend_share_of_baseline": 0.04},
    "moderate": {"label": "Moderate", "return_reduction": 0.12, "logistics_reduction": 0.10,
                 "write_off_reduction": 0.20, "retained_sale_share": 0.65, "spend_share_of_baseline": 0.10},
    "aggressive": {"label": "Aggressive", "return_reduction": 0.22, "logistics_reduction": 0.20,
                   "write_off_reduction": 0.35, "retained_sale_share": 0.70, "spend_share_of_baseline": 0.22},
}
SCENARIO_LIMITS = {
    "return_reduction": (0.0, 0.30),
    "logistics_reduction": (0.0, 0.30),
    "write_off_reduction": (0.0, 0.50),
    "retained_sale_share": (0.0, 1.0),
}

# --------------------------------------------------------------------------- #
# Anomaly detection defaults
# --------------------------------------------------------------------------- #
ANOMALY_BASELINE_MONTHS = 3
ANOMALY_MIN_UNITS = 120          # minimum units sold in the month for a rate test
ANOMALY_MIN_RETURNS = 20         # minimum returned units for cost/refund tests
ANOMALY_RATE_LIFT = 1.30         # observed must be >= 130 % of baseline ...
ANOMALY_Z = 2.5                  # ... and at least 2.5 standard errors above it (limits false alarms
                                 #     across ~500 monthly tests)
ANOMALY_COST_LIFT = 1.25         # reverse-logistics cost per returned unit >= 125 % of baseline
ANOMALY_REFUND_LIFT = 1.50       # refund rate >= 150 % of baseline
