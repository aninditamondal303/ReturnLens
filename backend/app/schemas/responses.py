"""
Typed API response models (Pydantic v2).

Every route declares one of these as its `response_model`, so FastAPI validates the
service output and publishes an accurate OpenAPI schema at /docs. The frontend's
src/types/api.ts mirrors these models.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict

Num = Optional[float]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- common
class FiltersOut(_Base):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    categories: list[str] = []
    regions: list[str] = []
    channels: list[str] = []


class Meta(_Base):
    generated_at: str
    filters: FiltersOut
    record_count: int
    snapshot_date: str
    period_start: str
    period_end: str
    synthetic_data: bool = True


class MetricValues(BaseModel):
    """All engine measures; any subset may be present. Label columns are declared by subclasses."""
    model_config = ConfigDict(extra="ignore")
    gmv: Num = None
    discount: Num = None
    net_sales: Num = None
    units: Num = None
    cogs: Num = None
    returned_units: Num = None
    refund: Num = None
    returned_cost: Num = None
    reverse_logistics: Num = None
    restocking: Num = None
    write_off: Num = None
    rejected_units: Num = None
    pending_units: Num = None
    eligible_orders: Num = None
    returned_orders: Num = None
    eligible_lines: Num = None
    total_lines: Num = None
    total_orders: Num = None
    cancelled_lines: Num = None
    net_revenue: Num = None
    net_cogs: Num = None
    contribution_before: Num = None
    incremental_costs: Num = None
    contribution_after: Num = None
    recoverable_inventory: Num = None
    return_leakage: Num = None
    unit_return_rate: Num = None
    contribution_margin: Num = None
    contribution_margin_before: Num = None
    refund_rate: Num = None
    incremental_per_returned_unit: Num = None
    order_return_rate: Num = None
    avg_order_value: Num = None
    incremental_per_returned_order: Num = None
    gmv_share: Num = None
    reverse_logistics_share: Num = None


class WaterfallStep(_Base):
    key: str
    label: str
    value: float
    kind: Literal["total", "subtotal", "revenue_reduction", "cost", "recovery"]
    start: float
    end: float


class PageInfo(_Base):
    page: int
    page_size: int
    total_rows: int
    total_pages: int


class ErrorBody(_Base):
    code: str
    message: str
    detail: Any = None


class ErrorResponse(_Base):
    error: ErrorBody


# --------------------------------------------------------------------------- system
class HealthResponse(_Base):
    status: Literal["ok", "degraded", "unavailable"]
    version: str
    data_loaded: bool
    loaded_at: Optional[str] = None
    rows: dict[str, int] = {}
    validation_errors: Optional[int] = None
    error: Optional[str] = None


class MetadataResponse(_Base):
    app: str
    version: str
    synthetic_data_notice: str
    period_start: str
    period_end: str
    snapshot_date: str
    months: list[str]
    categories: list[str]
    regions: list[str]
    channels: list[str]
    loaded_at: Optional[str]
    rows: dict[str, int]
    return_rate_target: float
    risk_thresholds: dict[str, int]
    validation: Optional[dict[str, int]] = None


class MetricDefinition(_Base):
    key: str
    name: str
    kind: Literal["actual", "derived", "estimated"]
    unit: str
    formula: str
    definition: str
    grain: str
    source: str


class ReloadResponse(_Base):
    reloaded: bool
    message: str
    loaded_at: Optional[str]
    rows: dict[str, int]
    validation: Optional[dict[str, int]]


# --------------------------------------------------------------------------- overview
class Kpi(_Base):
    key: str
    label: str
    value: Num
    unit: str
    kind: str
    previous: Num
    change: Num
    change_type: Literal["points", "relative"]
    good_direction: Literal["up", "down"]
    definition: str
    formula: str
    secondary_key: Optional[str]
    secondary_label: Optional[str]
    secondary_value: Num
    sparkline: list[Num]


class Comparison(_Base):
    available: bool
    previous_start: Optional[str]
    previous_end: Optional[str]
    note: Optional[str]


class MonthRow(MetricValues):
    month: str


class CategoryRow(MetricValues):
    category: str
    negative_contribution: Optional[bool] = None
    weak_contribution: Optional[bool] = None


class StatusRow(_Base):
    status: str
    lines: float
    units: float
    share: float


class StatusDistribution(_Base):
    denominator: str
    rows: list[StatusRow]


class Insight(_Base):
    id: str
    tone: Literal["risk", "positive", "info"]
    title: str
    detail: str
    metric: str


class OverviewResponse(_Base):
    meta: Meta
    summary: MetricValues
    comparison: Comparison
    kpis: list[Kpi]
    monthly: list[MonthRow]
    return_rate_target: float
    leakage_map: list[CategoryRow]
    anatomy: list[WaterfallStep]
    status_distribution: StatusDistribution
    insights: list[Insight]


# --------------------------------------------------------------------------- risk
class RiskKpis(_Base):
    eligible_orders: int
    returned_orders: int
    order_return_rate: Num
    unit_return_rate: Num
    eligible_lines: int
    high_risk_orders: int
    high_risk_lines: int
    high_risk_exposure: Num
    high_risk_value: Num
    high_band_observed_rate: Num


class HistogramBin(_Base):
    bin_start: int
    bin_end: int
    lines: int
    returned_lines: int
    band: str


class BandRow(_Base):
    band: str
    lines: int
    orders: int
    units: float
    returned_units: float
    unit_return_rate: Num
    avg_score: Num
    exposure: Num


class RateRow(_Base):
    label: str
    lines: Num
    units: Num
    returned_units: Num
    exposure: Num
    unit_return_rate: Num


class RiskScatterPoint(_Base):
    order_line_id: str
    order_id: str
    product_name: str
    category: str
    risk_score: Num
    risk_exposure: Num
    risk_band: str
    actual_return_status: str


class ReasonRow(_Base):
    reason: str
    returns: float
    units: float
    refund: float
    share: Num


class ReasonMatrixRow(_Base):
    category: str
    total: float
    reasons: dict[str, Num]


class RiskFactor(_Base):
    key: str
    label: str
    max_points: float
    scale: str


class RiskBandDef(_Base):
    label: str
    min: int
    max: int


class RiskModelDescription(_Base):
    type: str
    prediction_point: str
    factors: list[RiskFactor]
    bands: list[RiskBandDef]
    leakage_controls: list[str]
    exposure_method: str


class RiskResponse(_Base):
    meta: Meta
    kpis: RiskKpis
    score_distribution: list[HistogramBin]
    by_band: list[BandRow]
    by_category: list[RateRow]
    by_discount: list[RateRow]
    by_delay: list[RateRow]
    by_value: list[RateRow]
    by_payment: list[RateRow]
    scatter: list[RiskScatterPoint]
    reasons: list[ReasonRow]
    reason_matrix: list[ReasonMatrixRow]
    model: RiskModelDescription
    band_return_rates: dict[str, Num]
    notes: list[str]


class RiskOrderRow(BaseModel):
    model_config = ConfigDict(extra="ignore")
    order_id: str
    order_line_id: str
    order_date: str
    product_id: str
    product_name: str
    category: str
    shipping_region: str
    sales_channel: str
    payment_method: str
    quantity: int
    line_net_value: float
    discount_pct: float
    shipping_delay_days: Num
    risk_score: Num
    risk_band: str
    top_factors: str
    risk_exposure: Num
    actual_return_status: str
    product_hist_rate: Num
    category_hist_rate: Num
    pts_product_history: Num
    pts_category_history: Num
    pts_discount: Num
    pts_shipping_delay: Num
    pts_order_value: Num
    pts_cash_on_delivery: Num
    pts_multi_unit: Num


class RiskOrdersResponse(PageInfo):
    meta: Meta
    rows: list[RiskOrderRow]


# --------------------------------------------------------------------------- leakage
class ProductMetricRow(MetricValues):
    product_id: str
    product_name: str
    category: Optional[str] = None
    subcategory: Optional[str] = None
    negative_contribution: Optional[bool] = None
    weak_contribution: Optional[bool] = None


class Reconciliation(_Base):
    net_revenue_check: float
    contribution_check: float
    category_sum_check: float
    note: str


class LeakageResponse(_Base):
    meta: Meta
    summary: MetricValues
    bridge: list[WaterfallStep]
    categories: list[CategoryRow]
    negative_products: list[ProductMetricRow]
    negative_product_count: int
    reconciliation: Reconciliation


class CategoryProductsResponse(_Base):
    meta: Meta
    category: str
    summary: MetricValues
    products: list[ProductMetricRow]


class OrderLineRow(BaseModel):
    model_config = ConfigDict(extra="ignore")
    order_id: str
    order_line_id: str
    order_date: str
    customer_id: str
    product_id: str
    product_name: str
    category: str
    shipping_region: str
    sales_channel: str
    payment_method: str
    quantity: int
    unit_price: float
    discount: float
    net_sales: float
    refund: float
    returned_units: float
    reverse_logistics: float
    restocking: float
    write_off: float
    order_status: str
    actual_return_status: str
    risk_score: Num
    risk_band: str
    primary_reason: str


class OrderLinesResponse(PageInfo):
    meta: Meta
    rows: list[OrderLineRow]


# --------------------------------------------------------------------------- products
class ProductRow(MetricValues):
    product_id: str
    product_name: str
    category: str
    subcategory: Optional[str] = None
    supplier_id: Optional[str] = None
    product_status: Optional[str] = None
    avg_risk_score: Num = None
    risk_indicator: Optional[str] = None


class ProductTableResponse(PageInfo):
    meta: Meta
    rows: list[ProductRow]


class DamageRow(_Base):
    product_id: str
    product_name: str
    category: str
    damage_units: float
    write_off: float


class ReasonProduct(BaseModel):
    model_config = ConfigDict(extra="ignore")
    product_id: str
    product_name: str
    category: str
    units: float
    share_of_product_returns: Num


class ReasonFocus(_Base):
    reason: str
    products: list[ReasonProduct]


class Spotlights(_Base):
    top_sales: list[ProductRow]
    highest_return_rate: list[ProductRow]
    highest_incremental_costs: list[ProductRow]
    negative_contribution: list[ProductRow]
    damage_returns: list[DamageRow]
    reason_focus: list[ReasonFocus]


class ProductsResponse(_Base):
    meta: Meta
    counts: dict[str, int]
    spotlights: Spotlights
    scatter: list[ProductRow]
    min_units_for_rate: int


class ProductInfo(_Base):
    product_id: str
    product_name: str
    category: str
    subcategory: str
    supplier_id: str
    product_status: str
    selling_price: Num
    unit_cost: Num
    return_window_days: int


class SimpleCountRow(BaseModel):
    model_config = ConfigDict(extra="ignore")
    units: float
    returns: Optional[float] = None
    write_off: Optional[float] = None
    return_reason: Optional[str] = None
    item_condition: Optional[str] = None


class ProductDetailResponse(_Base):
    meta: Meta
    product: ProductInfo
    metrics: MetricValues
    category_average: MetricValues
    category_products: int
    monthly: list[MonthRow]
    reasons: list[SimpleCountRow]
    conditions: list[SimpleCountRow]
    avg_risk_score: Num


# --------------------------------------------------------------------------- geography
class RegionRow(MetricValues):
    shipping_region: str
    shipping_zone: Optional[str] = None


class ZoneRow(MetricValues):
    shipping_zone: str


class SegmentRow(MetricValues):
    customer_segment: str
    active_customers: Num = None
    net_revenue_per_customer: Num = None
    contribution_per_customer: Num = None
    orders_per_customer: Num = None


class CustomerTypeRow(MetricValues):
    customer_type: str


class HistoryBandRow(MetricValues):
    historical_order_count_band: str


class ChannelRow(MetricValues):
    sales_channel: str


class PaymentRow(MetricValues):
    payment_method: str


class GeographyResponse(_Base):
    meta: Meta
    summary: MetricValues
    regions: list[RegionRow]
    zones: list[ZoneRow]
    segments: list[SegmentRow]
    customer_type: list[CustomerTypeRow]
    history_bands: list[HistoryBandRow]
    channels: list[ChannelRow]
    payments: list[PaymentRow]
    notes: list[str]


# --------------------------------------------------------------------------- what-if
class ScenarioParamsOut(_Base):
    return_reduction: float
    logistics_reduction: float
    write_off_reduction: float
    retained_sale_share: float
    prevention_spend: float
    category_overrides: dict[str, float] = {}


class ComponentRow(_Base):
    key: str
    baseline: float
    scenario: float
    savings: float


class ScenarioCategoryRow(_Base):
    category: str
    return_reduction: Num
    baseline_incremental: float
    scenario_incremental: float
    gross_savings: float
    retained_margin: float
    baseline_unit_return_rate: Num
    scenario_unit_return_rate: Num


class ScenarioResult(_Base):
    params: ScenarioParamsOut
    baseline_incremental_costs: float
    scenario_incremental_costs: float
    gross_cost_savings: float
    volume_savings: float
    efficiency_savings: float
    retained_margin: float
    prevention_spend: float
    net_improvement: float
    cost_reduction_pct: Num
    baseline_contribution: float
    scenario_contribution: float
    roi: Num
    payback_months: Num
    months_in_period: int
    baseline_unit_return_rate: Num
    scenario_unit_return_rate: Num
    avoided_returned_units: float
    components: list[ComponentRow]
    by_category: list[ScenarioCategoryRow]


class PresetResult(_Base):
    key: str
    label: str
    params: ScenarioParamsOut
    baseline_incremental_costs: float
    scenario_incremental_costs: float
    gross_cost_savings: float
    retained_margin: float
    prevention_spend: float
    net_improvement: float
    cost_reduction_pct: Num
    scenario_contribution: float
    roi: Num
    payback_months: Num
    scenario_unit_return_rate: Num


class WhatIfResponse(_Base):
    meta: Meta
    result: ScenarioResult
    presets: list[PresetResult]
    limits: dict[str, dict[str, float]]
    categories: list[str]
    formulas: list[str]
    disclaimer: str


# --------------------------------------------------------------------------- anomalies
class AnomalyFlag(_Base):
    dimension: str
    member: str
    month: str
    metric: str
    unit: str
    observed: Num
    baseline: Num
    lift: Num
    z_score: Num
    baseline_period: str
    reason: str
    severity: Literal["high", "medium"]


class AnomalyMethod(_Base):
    baseline_months: int
    min_units: int
    min_returns: int
    rate_lift: float
    z_threshold: float
    cost_lift: float
    refund_lift: float
    description: str


class AnomalyResponse(_Base):
    meta: Meta
    method: AnomalyMethod
    tests_run: int
    skipped_insufficient_volume: int
    flags: list[AnomalyFlag]
    disclaimer: str


# --------------------------------------------------------------------------- data quality
class QualityCheck(_Base):
    name: str
    passed: bool
    severity: Literal["error", "warning"]
    detail: str
    affected_rows: int
    impact: str


class ValidationReport(_Base):
    passed: bool
    checks: list[QualityCheck]
    summary: dict[str, int]


class ColumnProfile(_Base):
    name: str
    dtype: str
    missing: int
    missing_note: str
    distinct: int
    example: str


class DatasetProfile(_Base):
    name: str
    rows: int
    columns: list[ColumnProfile]
    duplicate_rows: int
    duplicate_keys: int
    date_coverage: dict[str, dict[str, str]]


class DataQualityResponse(_Base):
    status: dict[str, Any]
    dataset_info: dict[str, Any]
    validation: Optional[ValidationReport]
    profiles: list[DatasetProfile]
    dictionary: dict[str, dict[str, str]]
    snapshot_date: str


class DatasetPreviewResponse(PageInfo):
    dataset: str
    columns: list[str]
    rows: list[dict[str, Any]]
