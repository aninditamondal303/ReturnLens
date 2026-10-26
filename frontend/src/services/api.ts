/**
 * Typed API client. Every request goes to the FastAPI backend; there is no
 * fallback data. Failures surface as ApiError with the server's message.
 */
import type {
  AnomalyResponse,
  CategoryProductsResponse,
  DataQualityResponse,
  DatasetPreview,
  GeographyResponse,
  Health,
  LeakageResponse,
  Metadata,
  MetricDefinition,
  OrderLineRow,
  OverviewResponse,
  Paged,
  ProductDetailResponse,
  ProductRow,
  ProductsResponse,
  ReloadResult,
  RiskOrderRow,
  RiskResponse,
  ScenarioParams,
  WhatIfResponse,
} from "../types/api";

export const API_BASE_URL: string = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export type QueryValue = string | number | boolean | null | undefined;
export type Query = Record<string, QueryValue>;

export class ApiError extends Error {
  status: number;
  code: string;
  detail?: unknown;
  constructor(message: string, status: number, code: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

/** Build a query string, skipping empty values. */
export function buildQuery(params: Query = {}): string {
  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    sp.append(key, String(value));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export function apiUrl(path: string, params?: Query): string {
  return `${API_BASE_URL}${path}${buildQuery(params)}`;
}

async function request<T>(path: string, params?: Query, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(apiUrl(path, params), { headers: { Accept: "application/json" }, ...init });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError(
      `Cannot reach the API at ${API_BASE_URL}. Start the backend (uvicorn app.main:app --reload) and try again.`,
      0,
      "network_error",
    );
  }
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    let code = "http_error";
    let detail: unknown;
    try {
      const body = await res.json();
      if (body?.error) {
        message = body.error.message;
        code = body.error.code;
        detail = body.error.detail;
      }
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(message, res.status, code, detail);
  }
  return (await res.json()) as T;
}

/** Download a CSV produced by the backend for the current filters. */
export async function downloadCsv(path: string, params: Query, fallbackName: string): Promise<number> {
  const res = await fetch(apiUrl(path, { ...params, format: "csv" }));
  if (!res.ok) throw new ApiError(`Export failed (${res.status})`, res.status, "export_failed");
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = /filename="?([^";]+)"?/.exec(disposition);
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = match?.[1] ?? fallbackName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  return Number(res.headers.get("X-Row-Count") ?? 0);
}

type Opt = { signal?: AbortSignal };

export const api = {
  health: (o?: Opt) => request<Health>("/api/health", undefined, o),
  metadata: (o?: Opt) => request<Metadata>("/api/metadata", undefined, o),
  metricsDictionary: (o?: Opt) => request<MetricDefinition[]>("/api/metrics-dictionary", undefined, o),
  reload: () => request<ReloadResult>("/api/data/reload", undefined, { method: "POST" }),

  overview: (q: Query, o?: Opt) => request<OverviewResponse>("/api/overview", q, o),
  returns: (q: Query, o?: Opt) => request<RiskResponse>("/api/returns", q, o),
  riskOrders: (q: Query, o?: Opt) => request<Paged<RiskOrderRow>>("/api/risk-orders", q, o),
  profitLeakage: (q: Query, o?: Opt) => request<LeakageResponse>("/api/profit-leakage", q, o),
  leakageProducts: (q: Query, o?: Opt) => request<CategoryProductsResponse>("/api/profit-leakage/products", q, o),
  orderLines: (q: Query, o?: Opt) => request<Paged<OrderLineRow>>("/api/order-lines", q, o),
  products: (q: Query, o?: Opt) => request<ProductsResponse>("/api/products", q, o),
  productTable: (q: Query, o?: Opt) => request<Paged<ProductRow>>("/api/products/table", q, o),
  productDetail: (id: string, q: Query, o?: Opt) =>
    request<ProductDetailResponse>(`/api/products/${encodeURIComponent(id)}`, q, o),
  geography: (q: Query, o?: Opt) => request<GeographyResponse>("/api/geography", q, o),
  whatIf: (q: Query, o?: Opt) => request<WhatIfResponse>("/api/what-if", q, o),
  anomalies: (q: Query, o?: Opt) => request<AnomalyResponse>("/api/anomalies", q, o),
  dataQuality: (o?: Opt) => request<DataQualityResponse>("/api/data-quality", undefined, o),
  dataset: (name: string, q: Query, o?: Opt) => request<DatasetPreview>(`/api/data/${name}`, q, o),
  datasetDownloadUrl: (name: string) => apiUrl(`/api/data/${name}/download`),
};

/** Serialise simulator inputs into query parameters. */
export function scenarioQuery(p: ScenarioParams): Query {
  const overrides = Object.entries(p.category_overrides)
    .map(([k, v]) => `${k}:${Math.round(v * 1000) / 10}`)
    .join(",");
  return {
    return_reduction: p.return_reduction,
    logistics_reduction: p.logistics_reduction,
    write_off_reduction: p.write_off_reduction,
    retained_sale_share: p.retained_sale_share,
    prevention_spend: Math.round(p.prevention_spend),
    category_overrides: overrides || undefined,
  };
}
