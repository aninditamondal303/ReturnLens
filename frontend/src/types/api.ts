/**
 * TypeScript mirror of backend/app/schemas/responses.py.
 * Monetary values are INR; rates are fractions (0.124 = 12.4 %).
 */
export type Num = number | null;

export interface FiltersOut {
  start_date: string | null;
  end_date: string | null;
  categories: string[];
  regions: string[];
  channels: string[];
}

export interface Meta {
  generated_at: string;
  filters: FiltersOut;
  record_count: number;
  snapshot_date: string;
  period_start: string;
  period_end: string;
  synthetic_data: boolean;
}

export interface MetricValues {
  gmv?: Num;
  discount?: Num;
  net_sales?: Num;
  units?: Num;
  cogs?: Num;
  returned_units?: Num;
  refund?: Num;
  returned_cost?: Num;
  reverse_logistics?: Num;
  restocking?: Num;
  write_off?: Num;
  rejected_units?: Num;
  pending_units?: Num;
  eligible_orders?: Num;
  returned_orders?: Num;
  eligible_lines?: Num;
  total_lines?: Num;
  total_orders?: Num;
  cancelled_lines?: Num;
  net_revenue?: Num;
  net_cogs?: Num;
  contribution_before?: Num;
  incremental_costs?: Num;
  contribution_after?: Num;
  recoverable_inventory?: Num;
  return_leakage?: Num;
  unit_return_rate?: Num;
  contribution_margin?: Num;
  contribution_margin_before?: Num;
  refund_rate?: Num;
  incremental_per_returned_unit?: Num;
  order_return_rate?: Num;
  avg_order_value?: Num;
  incremental_per_returned_order?: Num;
  gmv_share?: Num;
  reverse_logistics_share?: Num;
}

export type MetricKey = keyof MetricValues;

export interface WaterfallStep {
  key: string;
  label: string;
  value: number;
  kind: "total" | "subtotal" | "revenue_reduction" | "cost" | "recovery";
  start: number;
  end: number;
}

export interface Paged<T> {
  meta: Meta;
  rows: T[];
  page: number;
  page_size: number;
  total_rows: number;
  total_pages: number;
}

export interface ApiErrorBody {
  error: { code: string; message: string; detail?: unknown };
}

// ------------------------------------------------------------------ system
export interface Health {
  status: "ok" | "degraded" | "unavailable";
  version: string;
  data_loaded: boolean;
  loaded_at: string | null;
  rows: Record<string, number>;
  validation_errors: number | null;
  error: string | null;
}

export interface Metadata {
  app: string;
  version: string;
  synthetic_data_notice: string;
  period_start: string;
  period_end: string;
  snapshot_date: string;
  months: string[];
  categories: string[];
  regions: string[];
  channels: string[];
  loaded_at: string | null;
  rows: Record<string, number>;
  return_rate_target: number;
  risk_thresholds: { medium: number; high: number };
  validation: { total_checks: number; passed: number; errors: number; warnings: number } | null;
}

export interface MetricDefinition {
  key: string;
  name: string;
  kind: "actual" | "derived" | "estimated";
  unit: string;
  formula: string;
  definition: string;
  grain: string;
  source: string;
}

export interface ReloadResult {
  reloaded: boolean;
  message: string;
  loaded_at: string | null;
  rows: Record<string, number>;
  validation: Metadata["validation"];
}

// ------------------------------------------------------------------ overview
export interface Kpi {
  key: string;
  label: string;
  value: Num;
  unit: string;
  kind: string;
  previous: Num;
  change: Num;
  change_type: "points" | "relative";
  good_direction: "up" | "down";
  definition: string;
  formula: string;
  secondary_key: string | null;
  secondary_label: string | null;
  secondary_value: Num;
  sparkline: Num[];
}

export interface MonthRow extends MetricValues {
  month: string;
}

export interface CategoryRow extends MetricValues {
  category: string;
  negative_contribution?: boolean | null;
  weak_contribution?: boolean | null;
}

export interface Insight {
  id: string;
  tone: "risk" | "positive" | "info";
  title: string;
  detail: string;
  metric: string;
}

export interface OverviewResponse {
  meta: Meta;
  summary: MetricValues;
  comparison: { available: boolean; previous_start: string | null; previous_end: string | null; note: string | null };
  kpis: Kpi[];
  monthly: MonthRow[];
  return_rate_target: number;
  leakage_map: CategoryRow[];
  anatomy: WaterfallStep[];
  status_distribution: { denominator: string; rows: { status: string; lines: number; units: number; share: number }[] };
  insights: Insight[];
}

// ------------------------------------------------------------------ risk
export interface RateRow {
  label: string;
  lines: Num;
  units: Num;
  returned_units: Num;
  exposure: Num;
  unit_return_rate: Num;
}

export interface BandRow {
  band: string;
  lines: number;
  orders: number;
  units: number;
  returned_units: number;
  unit_return_rate: Num;
  avg_score: Num;
  exposure: Num;
}

export interface RiskModel {
  type: string;
  prediction_point: string;
  factors: { key: string; label: string; max_points: number; scale: string }[];
  bands: { label: string; min: number; max: number }[];
  leakage_controls: string[];
  exposure_method: string;
}

export interface RiskResponse {
  meta: Meta;
  kpis: {
    eligible_orders: number;
    returned_orders: number;
    order_return_rate: Num;
    unit_return_rate: Num;
    eligible_lines: number;
    high_risk_orders: number;
    high_risk_lines: number;
    high_risk_exposure: Num;
    high_risk_value: Num;
    high_band_observed_rate: Num;
  };
  score_distribution: { bin_start: number; bin_end: number; lines: number; returned_lines: number; band: string }[];
  by_band: BandRow[];
  by_category: RateRow[];
  by_discount: RateRow[];
  by_delay: RateRow[];
  by_value: RateRow[];
  by_payment: RateRow[];
  scatter: {
    order_line_id: string;
    order_id: string;
    product_name: string;
    category: string;
    risk_score: Num;
    risk_exposure: Num;
    risk_band: string;
    actual_return_status: string;
  }[];
  reasons: { reason: string; returns: number; units: number; refund: number; share: Num }[];
  reason_matrix: { category: string; total: number; reasons: Record<string, Num> }[];
  model: RiskModel;
  band_return_rates: Record<string, Num>;
  notes: string[];
}

export interface RiskOrderRow {
  order_id: string;
  order_line_id: string;
  order_date: string;
  product_id: string;
  product_name: string;
  category: string;
  shipping_region: string;
  sales_channel: string;
  payment_method: string;
  quantity: number;
  line_net_value: number;
  discount_pct: number;
  shipping_delay_days: Num;
  risk_score: Num;
  risk_band: string;
  top_factors: string;
  risk_exposure: Num;
  actual_return_status: string;
  product_hist_rate: Num;
  category_hist_rate: Num;
  pts_product_history: Num;
  pts_category_history: Num;
  pts_discount: Num;
  pts_shipping_delay: Num;
  pts_order_value: Num;
  pts_cash_on_delivery: Num;
  pts_multi_unit: Num;
}

// ------------------------------------------------------------------ leakage
export interface ProductMetricRow extends MetricValues {
  product_id: string;
  product_name: string;
  category?: string | null;
  subcategory?: string | null;
  negative_contribution?: boolean | null;
  weak_contribution?: boolean | null;
}

export interface LeakageResponse {
  meta: Meta;
  summary: MetricValues;
  bridge: WaterfallStep[];
  categories: CategoryRow[];
  negative_products: ProductMetricRow[];
  negative_product_count: number;
  reconciliation: { net_revenue_check: number; contribution_check: number; category_sum_check: number; note: string };
}

export interface CategoryProductsResponse {
  meta: Meta;
  category: string;
  summary: MetricValues;
  products: ProductMetricRow[];
}

export interface OrderLineRow {
  order_id: string;
  order_line_id: string;
  order_date: string;
  customer_id: string;
  product_id: string;
  product_name: string;
  category: string;
  shipping_region: string;
  sales_channel: string;
  payment_method: string;
  quantity: number;
  unit_price: number;
  discount: number;
  net_sales: number;
  refund: number;
  returned_units: number;
  reverse_logistics: number;
  restocking: number;
  write_off: number;
  order_status: string;
  actual_return_status: string;
  risk_score: Num;
  risk_band: string;
  primary_reason: string;
}

// ------------------------------------------------------------------ products
export interface ProductRow extends MetricValues {
  product_id: string;
  product_name: string;
  category: string;
  subcategory?: string | null;
  supplier_id?: string | null;
  product_status?: string | null;
  avg_risk_score?: Num;
  risk_indicator?: "High" | "Elevated" | "Normal" | null;
}

export interface ProductsResponse {
  meta: Meta;
  counts: Record<string, number>;
  spotlights: {
    top_sales: ProductRow[];
    highest_return_rate: ProductRow[];
    highest_incremental_costs: ProductRow[];
    negative_contribution: ProductRow[];
    damage_returns: { product_id: string; product_name: string; category: string; damage_units: number; write_off: number }[];
    reason_focus: {
      reason: string;
      products: { product_id: string; product_name: string; category: string; units: number; share_of_product_returns: Num }[];
    }[];
  };
  scatter: ProductRow[];
  min_units_for_rate: number;
}

export interface ProductDetailResponse {
  meta: Meta;
  product: {
    product_id: string;
    product_name: string;
    category: string;
    subcategory: string;
    supplier_id: string;
    product_status: string;
    selling_price: Num;
    unit_cost: Num;
    return_window_days: number;
  };
  metrics: MetricValues;
  category_average: MetricValues;
  category_products: number;
  monthly: MonthRow[];
  reasons: { return_reason?: string | null; units: number; returns?: number | null }[];
  conditions: { item_condition?: string | null; units: number; write_off?: number | null }[];
  avg_risk_score: Num;
}

// ------------------------------------------------------------------ geography
export interface GroupRow extends MetricValues {
  shipping_region?: string;
  shipping_zone?: string | null;
  customer_segment?: string;
  customer_type?: string;
  historical_order_count_band?: string;
  sales_channel?: string;
  payment_method?: string;
  active_customers?: Num;
  net_revenue_per_customer?: Num;
  contribution_per_customer?: Num;
  orders_per_customer?: Num;
}

export interface GeographyResponse {
  meta: Meta;
  summary: MetricValues;
  regions: GroupRow[];
  zones: GroupRow[];
  segments: GroupRow[];
  customer_type: GroupRow[];
  history_bands: GroupRow[];
  channels: GroupRow[];
  payments: GroupRow[];
  notes: string[];
}

// ------------------------------------------------------------------ what-if
export interface ScenarioParams {
  return_reduction: number;
  logistics_reduction: number;
  write_off_reduction: number;
  retained_sale_share: number;
  prevention_spend: number;
  category_overrides: Record<string, number>;
}

export interface ScenarioResult {
  params: ScenarioParams;
  baseline_incremental_costs: number;
  scenario_incremental_costs: number;
  gross_cost_savings: number;
  volume_savings: number;
  efficiency_savings: number;
  retained_margin: number;
  prevention_spend: number;
  net_improvement: number;
  cost_reduction_pct: Num;
  baseline_contribution: number;
  scenario_contribution: number;
  roi: Num;
  payback_months: Num;
  months_in_period: number;
  baseline_unit_return_rate: Num;
  scenario_unit_return_rate: Num;
  avoided_returned_units: number;
  components: { key: string; baseline: number; scenario: number; savings: number }[];
  by_category: {
    category: string;
    return_reduction: Num;
    baseline_incremental: number;
    scenario_incremental: number;
    gross_savings: number;
    retained_margin: number;
    baseline_unit_return_rate: Num;
    scenario_unit_return_rate: Num;
  }[];
}

export interface PresetResult {
  key: string;
  label: string;
  params: ScenarioParams;
  baseline_incremental_costs: number;
  scenario_incremental_costs: number;
  gross_cost_savings: number;
  retained_margin: number;
  prevention_spend: number;
  net_improvement: number;
  cost_reduction_pct: Num;
  scenario_contribution: number;
  roi: Num;
  payback_months: Num;
  scenario_unit_return_rate: Num;
}

export interface WhatIfResponse {
  meta: Meta;
  result: ScenarioResult;
  presets: PresetResult[];
  limits: Record<string, { min: number; max: number }>;
  categories: string[];
  formulas: string[];
  disclaimer: string;
}

// ------------------------------------------------------------------ anomalies
export interface AnomalyFlag {
  dimension: string;
  member: string;
  month: string;
  metric: string;
  unit: string;
  observed: Num;
  baseline: Num;
  lift: Num;
  z_score: Num;
  baseline_period: string;
  reason: string;
  severity: "high" | "medium";
}

export interface AnomalyResponse {
  meta: Meta;
  method: {
    baseline_months: number;
    min_units: number;
    min_returns: number;
    rate_lift: number;
    z_threshold: number;
    cost_lift: number;
    refund_lift: number;
    description: string;
  };
  tests_run: number;
  skipped_insufficient_volume: number;
  flags: AnomalyFlag[];
  disclaimer: string;
}

// ------------------------------------------------------------------ data explorer
export interface QualityCheck {
  name: string;
  passed: boolean;
  severity: "error" | "warning";
  detail: string;
  affected_rows: number;
  impact: string;
}

export interface DatasetProfile {
  name: string;
  rows: number;
  columns: { name: string; dtype: string; missing: number; missing_note: string; distinct: number; example: string }[];
  duplicate_rows: number;
  duplicate_keys: number;
  date_coverage: Record<string, { min: string; max: string }>;
}

export interface DataQualityResponse {
  status: { loaded: boolean; loaded_at: string | null; data_dir: string; rows: Record<string, number>; error: string | null };
  dataset_info: Record<string, unknown>;
  validation: { passed: boolean; checks: QualityCheck[]; summary: Record<string, number> } | null;
  profiles: DatasetProfile[];
  dictionary: Record<string, Record<string, string>>;
  snapshot_date: string;
}

export interface DatasetPreview {
  dataset: string;
  columns: string[];
  rows: Record<string, string>[];
  page: number;
  page_size: number;
  total_rows: number;
  total_pages: number;
}
