"""
Metric dictionary — the single written specification of every KPI.

Served by GET /api/metrics-dictionary and rendered in the UI tooltips, so the
definitions shown to users can never drift from what the code reports.

kind: "actual"    = sum of recorded transaction values
      "derived"   = arithmetic on actual values
      "estimated" = depends on modelling assumptions
"""
from __future__ import annotations

METRICS: list[dict] = [
    {
        "key": "gmv", "name": "Gross Merchandise Value (GMV)", "kind": "actual", "unit": "INR",
        "formula": "Σ quantity × unit_price over eligible (non-cancelled) order lines",
        "definition": "Merchandise selling value before discounts and refunds. Cancelled lines and shipping fees are excluded.",
        "grain": "order line", "source": "orders.csv",
    },
    {
        "key": "discount", "name": "Discount Value", "kind": "actual", "unit": "INR",
        "formula": "Σ discount_amount over eligible order lines",
        "definition": "Price reductions granted on completed sales.",
        "grain": "order line", "source": "orders.csv",
    },
    {
        "key": "net_sales", "name": "Net Merchandise Sales (before refunds)", "kind": "derived", "unit": "INR",
        "formula": "GMV − Discount Value", "definition": "What customers paid for merchandise before any returns.",
        "grain": "order line", "source": "orders.csv",
    },
    {
        "key": "refund", "name": "Refund Value", "kind": "actual", "unit": "INR",
        "formula": "Σ refund_amount where return_status = 'Refunded'",
        "definition": ("Merchandise refunds on processed returns. Refund = returned units × net price paid per unit "
                       "(after discount). Shipping fees are never refunded in this model."),
        "grain": "return", "source": "returns.csv",
    },
    {
        "key": "net_revenue", "name": "Net Merchandise Revenue (after refunds)", "kind": "derived", "unit": "INR",
        "formula": "Net Merchandise Sales − Refund Value", "definition": "Merchandise revenue retained after refunds.",
        "grain": "order line", "source": "orders.csv + returns.csv",
    },
    {
        "key": "units", "name": "Units Sold", "kind": "actual", "unit": "units",
        "formula": "Σ quantity over eligible order lines",
        "definition": "Units delivered to customers (gross of later returns).", "grain": "order line", "source": "orders.csv",
    },
    {
        "key": "returned_units", "name": "Returned Units", "kind": "actual", "unit": "units",
        "formula": "Σ return_quantity where return_status = 'Refunded'",
        "definition": "Units returned and refunded. Rejected and pending returns are excluded.",
        "grain": "return", "source": "returns.csv",
    },
    {
        "key": "unit_return_rate", "name": "Unit Return Rate", "kind": "derived", "unit": "percent",
        "formula": "Returned Units ÷ Units Sold",
        "definition": "Share of delivered units that came back and were refunded (returns attributed to the order month).",
        "grain": "order line", "source": "orders.csv + returns.csv",
    },
    {
        "key": "order_return_rate", "name": "Order Return Rate", "kind": "derived", "unit": "percent",
        "formula": "Distinct orders with ≥1 refunded return ÷ distinct orders with ≥1 eligible line",
        "definition": ("Share of orders containing at least one refunded return. When filters are active, only the "
                       "order lines matching the filters are considered."),
        "grain": "order", "source": "orders.csv + returns.csv",
    },
    {
        "key": "cogs", "name": "Cost of Goods Delivered (gross COGS)", "kind": "derived", "unit": "INR",
        "formula": "Σ Units Sold × unit_cost", "definition": "Inventory cost of everything delivered.",
        "grain": "order line", "source": "orders.csv + products.csv",
    },
    {
        "key": "returned_cost", "name": "Returned Inventory (at cost)", "kind": "derived", "unit": "INR",
        "formula": "Σ Returned Units × unit_cost",
        "definition": "Cost of refunded units taken back into stock; reversed out of COGS once.",
        "grain": "return", "source": "returns.csv + products.csv",
    },
    {
        "key": "reverse_logistics", "name": "Reverse Logistics Cost", "kind": "actual", "unit": "INR",
        "formula": "Σ reverse_logistics_cost on Refunded and Rejected returns",
        "definition": "Pickup and return transport. Rejected returns also include re-shipping the item to the customer.",
        "grain": "return", "source": "returns.csv",
    },
    {
        "key": "restocking", "name": "Restocking & Inspection Cost", "kind": "actual", "unit": "INR",
        "formula": "Σ restocking_cost on Refunded and Rejected returns",
        "definition": "Inspection, testing, repackaging and disposal handling.", "grain": "return", "source": "returns.csv",
    },
    {
        "key": "write_off", "name": "Inventory Write-Off", "kind": "estimated", "unit": "INR",
        "formula": "Σ inventory_write_off (returned units × unit_cost × condition write-off share)",
        "definition": ("Cost of returned stock that cannot be recovered. Condition shares: unopened 0 %, opened 10 %, "
                       "B-grade 45 %, defective 65 % (35 % vendor credit), damaged 100 %; opened beauty items 100 %."),
        "grain": "return", "source": "returns.csv",
    },
    {
        "key": "incremental_costs", "name": "Estimated Incremental Return Costs", "kind": "estimated", "unit": "INR",
        "formula": "Reverse Logistics + Restocking & Inspection + Inventory Write-Off",
        "definition": "Extra operating cost caused by returns. Refunds are NOT included (they are revenue reductions).",
        "grain": "return", "source": "returns.csv",
    },
    {
        "key": "contribution_before", "name": "Estimated Contribution Before Return Costs", "kind": "estimated",
        "unit": "INR", "formula": "Net Merchandise Revenue − (Gross COGS − Returned Inventory)",
        "definition": "Merchandise margin on units customers kept.", "grain": "order line",
        "source": "all datasets",
    },
    {
        "key": "contribution_after", "name": "Estimated Contribution After Return Costs", "kind": "estimated",
        "unit": "INR", "formula": "Contribution Before Return Costs − Estimated Incremental Return Costs",
        "definition": ("Merchandise contribution after returns. Excludes shipping fees, forward fulfilment, payment, "
                       "marketing and overheads, so it is a contribution measure, not profit."),
        "grain": "order line", "source": "all datasets",
    },
    {
        "key": "contribution_margin", "name": "Contribution Margin (after return costs)", "kind": "estimated",
        "unit": "percent", "formula": "Contribution After Return Costs ÷ Net Merchandise Revenue",
        "definition": "Share of retained merchandise revenue left as contribution.", "grain": "order line",
        "source": "all datasets",
    },
    {
        "key": "recoverable_inventory", "name": "Recoverable Inventory Value", "kind": "estimated", "unit": "INR",
        "formula": "Returned Inventory (at cost) − Inventory Write-Off",
        "definition": "Value of returned stock expected to be resold.", "grain": "return", "source": "returns.csv + products.csv",
    },
    {
        "key": "return_leakage", "name": "Return Profit Leakage", "kind": "estimated", "unit": "INR",
        "formula": "(Refund Value − Returned Inventory) + Estimated Incremental Return Costs",
        "definition": ("Contribution lost because of returns: the margin forgone on refunded units plus the extra costs. "
                       "Equals contribution if no refunded return had happened minus actual contribution. "
                       "Used as bubble size in the Leakage Map."),
        "grain": "return", "source": "all datasets",
    },
    {
        "key": "risk_score", "name": "Heuristic Return-Risk Score", "kind": "estimated", "unit": "score 0-100",
        "formula": "Σ factor weight × scaled factor (see Return Risk page)",
        "definition": ("Rule-based ranking using only pre-return information. Not a probability and not a trained "
                       "model. Bands: Low 0-34, Medium 35-64, High 65-100."),
        "grain": "order line", "source": "orders.csv + historical returns",
    },
    {
        "key": "risk_exposure", "name": "Estimated High-Risk Financial Exposure", "kind": "estimated", "unit": "INR",
        "formula": "Σ over High-risk lines: band historical return rate × quantity × (forgone margin per unit + category incremental cost per returned unit)",
        "definition": "Expected return-related cost of high-risk lines. Not a confirmed loss; band rates are in-sample.",
        "grain": "order line", "source": "orders.csv + returns.csv",
    },
]

METRICS_BY_KEY = {m["key"]: m for m in METRICS}
