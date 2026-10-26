import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { X } from "lucide-react";
import { api } from "../services/api";
import { useApi, useDebounced } from "../hooks/useApi";
import { useFilters } from "../state/FilterContext";
import type { ProductDetailResponse, ProductRow, ProductsResponse } from "../types/api";
import { EmptyState, ErrorState, Panel, PanelSkeleton, RiskBadge, Stat } from "../components/ui";
import { DataTable, Pagination, type Column, type SortState } from "../components/DataTable";
import { Segmented, SearchInput, SelectField } from "../components/controls";
import { ExportButton } from "../components/ExportButton";
import { PointScatter, UnitsAndRate } from "../charts/charts";
import { C } from "../charts/theme";
import { inr, inrCompact, int, pct } from "../utils/format";

type Spot = "top_sales" | "highest_return_rate" | "highest_incremental_costs" | "negative_contribution" | "damage" | "reasons";

export default function ProductIntelligence() {
  const { query, queryKey, metadata } = useFilters();
  const location = useLocation();
  const initialCategory = (location.state as { category?: string } | null)?.category ?? "";
  const { data, error, loading, refreshing, reload } = useApi<ProductsResponse>((s) => api.products(query, { signal: s }), queryKey);
  const [selected, setSelected] = useState<string | null>(null);
  const [pageCategory, setPageCategory] = useState(initialCategory);

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading || !data) return <div className="grid grid-cols-1 gap-4 lg:grid-cols-2"><PanelSkeleton label="product scatter" /><PanelSkeleton label="spotlights" /></div>;
  if (data.counts.products === 0) return <div className="panel"><EmptyState hint="No products sold in this selection." /></div>;

  return (
    <div className={`flex flex-col gap-4 transition-opacity duration-150 ${refreshing ? "opacity-70" : ""}`}>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Panel
          className="xl:col-span-7"
          label="Assortment map"
          title="Sales, return rate and contribution per product"
          subtitle="Each dot is a product (log scale sales). Vermilion = negative estimated contribution; dot size = units sold. Click a dot to open its detail."
        >
          <div className="mb-2 grid grid-cols-3 gap-4">
            <Stat label="Products sold" value={int(data.counts.products)} />
            <Stat label="Negative contribution" value={int(data.counts.negative_contribution)} tone="loss" kind="estimated" />
            <Stat label="High risk indicator" value={int(data.counts.high_risk_indicator)} tone="loss" tip="High = negative contribution, or a return rate at least 2x the portfolio rate (min. 30 units)." />
          </div>
          <PointScatter
            height={300}
            xLog
            xLabel="Gross merchandise value (log)"
            yLabel="Unit return rate"
            xFormat={(v) => inrCompact(v)}
            yFormat={(v) => pct(v, 0)}
            onPointClick={setSelected}
            points={data.scatter
              .filter((p) => (p.gmv ?? 0) > 0)
              .map((p) => ({
                id: p.product_id,
                x: p.gmv ?? 0,
                y: p.unit_return_rate ?? 0,
                z: p.units ?? 0,
                color: (p.contribution_after ?? 0) < 0 ? C.vermilion : p.risk_indicator === "Elevated" ? C.brass : C.teal,
                title: p.product_name,
                rows: [
                  { label: "Category", value: p.category },
                  { label: "GMV", value: inrCompact(p.gmv) },
                  { label: "Return rate", value: pct(p.unit_return_rate) },
                  { label: "Est. contribution", value: inrCompact(p.contribution_after) },
                  { label: "Risk indicator", value: p.risk_indicator ?? "—" },
                ],
              }))}
          />
        </Panel>
        <Spotlights data={data} onOpen={setSelected} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <div className={selected ? "xl:col-span-8" : "xl:col-span-12"}>
          <ProductTable categories={metadata?.categories ?? []} pageCategory={pageCategory} setPageCategory={setPageCategory} selected={selected} onSelect={setSelected} />
        </div>
        {selected && (
          <div className="xl:col-span-4">
            <ProductDetail productId={selected} onClose={() => setSelected(null)} />
          </div>
        )}
      </div>
    </div>
  );
}

function Spotlights({ data, onOpen }: { data: ProductsResponse; onOpen: (id: string) => void }) {
  const [tab, setTab] = useState<Spot>("highest_return_rate");
  const s = data.spotlights;
  const list = (rows: ProductRow[], metric: (r: ProductRow) => string, metricLabel: string) =>
    rows.length === 0 ? (
      <p className="px-4 py-6 text-[12.5px] text-slate-ink">No products in this list for the current selection.</p>
    ) : (
      <ol className="divide-y divide-line">
        {rows.map((r, i) => (
          <li key={r.product_id}>
            <button type="button" onClick={() => onOpen(r.product_id)} className="grid w-full grid-cols-[20px_minmax(0,1fr)_auto] items-center gap-3 px-4 py-2 text-left hover:bg-paper">
              <span className="num text-[11px] text-slate-ink">{i + 1}</span>
              <span className="min-w-0">
                <span className="block truncate text-[12.5px] font-medium">{r.product_name}</span>
                <span className="text-[11.5px] text-slate-ink">{r.category}</span>
              </span>
              <span className="text-right">
                <span className="num block text-[13px]">{metric(r)}</span>
                <span className="text-[10.5px] text-slate-ink">{metricLabel}</span>
              </span>
            </button>
          </li>
        ))}
      </ol>
    );
  return (
    <Panel className="xl:col-span-5" label="Investigation lists" title="Products that need attention" bodyClass="p-0">
      <div className="overflow-x-auto border-b border-line px-4 py-2">
        <SelectField
          label="List"
          hideLabel
          value={tab}
          onChange={(v) => setTab(v as Spot)}
          options={[
            { value: "highest_return_rate", label: `Highest return rate (min. ${data.min_units_for_rate} units)` },
            { value: "top_sales", label: "Top products by sales" },
            { value: "highest_incremental_costs", label: "Highest incremental return costs" },
            { value: "negative_contribution", label: "Negative estimated contribution" },
            { value: "damage", label: "Damage and defect returns" },
            { value: "reasons", label: "Size, quality and description-mismatch returns" },
          ]}
          className="w-full"
        />
      </div>
      <div className="max-h-[360px] overflow-auto">
        {tab === "top_sales" && list(s.top_sales, (r) => inrCompact(r.gmv), "GMV")}
        {tab === "highest_return_rate" && list(s.highest_return_rate, (r) => pct(r.unit_return_rate), "return rate")}
        {tab === "highest_incremental_costs" && list(s.highest_incremental_costs, (r) => inrCompact(r.incremental_costs), "return costs")}
        {tab === "negative_contribution" && list(s.negative_contribution, (r) => inrCompact(r.contribution_after), "contribution")}
        {tab === "damage" && (
          <ol className="divide-y divide-line">
            {s.damage_returns.map((r) => (
              <li key={r.product_id}>
                <button type="button" onClick={() => onOpen(r.product_id)} className="grid w-full grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-4 px-4 py-2 text-left hover:bg-paper">
                  <span className="min-w-0"><span className="block truncate text-[12.5px] font-medium">{r.product_name}</span><span className="text-[11.5px] text-slate-ink">{r.category}</span></span>
                  <span className="num text-right text-[12.5px]">{int(r.damage_units)} units</span>
                  <span className="num text-right text-[12.5px] text-vermilion-ink">{inrCompact(r.write_off)} w/o</span>
                </button>
              </li>
            ))}
          </ol>
        )}
        {tab === "reasons" && (
          <div className="divide-y divide-line">
            {s.reason_focus.map((g) => (
              <div key={g.reason} className="px-4 py-2">
                <div className="section-label mb-1">{g.reason}</div>
                <ul>
                  {g.products.map((p) => (
                    <li key={p.product_id}>
                      <button type="button" onClick={() => onOpen(p.product_id)} className="flex w-full items-center justify-between gap-3 py-1 text-left text-[12.5px] hover:underline">
                        <span className="truncate">{p.product_name}</span>
                        <span className="num shrink-0 text-slate-ink">{int(p.units)} units · {pct(p.share_of_product_returns, 0)} of its returns</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </div>
    </Panel>
  );
}

function ProductTable({
  categories,
  pageCategory,
  setPageCategory,
  selected,
  onSelect,
}: {
  categories: string[];
  pageCategory: string;
  setPageCategory: (c: string) => void;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const { query, queryKey } = useFilters();
  const [search, setSearch] = useState("");
  const [risk, setRisk] = useState("");
  const [sort, setSort] = useState<SortState>({ by: "gmv", dir: "desc" });
  const [page, setPage] = useState(1);
  const debounced = useDebounced(search);
  useEffect(() => setPage(1), [queryKey, pageCategory, risk, debounced, sort.by, sort.dir]);
  const params = { ...query, product_category: pageCategory || undefined, risk: risk || undefined, search: debounced || undefined, sort_by: sort.by, sort_dir: sort.dir };
  const { data, error, loading, refreshing, reload } = useApi(
    (s) => api.productTable({ ...params, page, page_size: 15 }, { signal: s }),
    `${queryKey}|${pageCategory}|${risk}|${debounced}|${sort.by}|${sort.dir}|${page}`,
  );
  const columns: Column<ProductRow>[] = [
    { key: "product_id", header: "ID", sortable: true, render: (r) => <span className="num text-[12px]">{r.product_id}</span> },
    { key: "product_name", header: "Product", sortable: true, render: (r) => <span className="block max-w-[180px] truncate font-medium" title={r.product_name}>{r.product_name}</span> },
    { key: "category", header: "Category", sortable: true },
    { key: "units", header: "Units sold", align: "right", sortable: true, render: (r) => int(r.units) },
    { key: "returned_units", header: "Returned", align: "right", sortable: true, render: (r) => int(r.returned_units) },
    { key: "gmv", header: "GMV", align: "right", sortable: true, render: (r) => inrCompact(r.gmv) },
    { key: "unit_return_rate", header: "Return rate", align: "right", sortable: true, render: (r) => pct(r.unit_return_rate) },
    { key: "refund", header: "Refunds", align: "right", sortable: true, render: (r) => inrCompact(r.refund) },
    { key: "incremental_costs", header: "Incr. costs", align: "right", sortable: true, render: (r) => <span className="text-vermilion-ink">{inrCompact(r.incremental_costs)}</span> },
    { key: "contribution_after", header: "Est. contrib.", align: "right", sortable: true, render: (r) => <span className={(r.contribution_after ?? 0) < 0 ? "font-semibold text-vermilion-ink" : "text-teal"}>{inrCompact(r.contribution_after)}</span> },
    { key: "risk_indicator", header: "Risk", render: (r) => <RiskBadge band={r.risk_indicator} />, tip: "High: negative contribution or return rate ≥ 2x portfolio (min. 30 units). Elevated: rate ≥ 1.3x portfolio or margin below half the portfolio margin." },
  ];
  return (
    <Panel label="Product table" title="All products" subtitle="Search, sort and filter; click a row for the product detail panel." bodyClass="p-0" actions={<ExportButton path="/api/products/table" params={params} fileName="shopsphere_products.csv" />}>
      <div className="flex flex-wrap items-end gap-3 border-b border-line px-4 py-2.5">
        <SearchInput value={search} onChange={setSearch} placeholder="Product, ID, supplier" label="Search products" className="w-[240px]" />
        <SelectField label="Category" value={pageCategory} onChange={setPageCategory} options={categories} allLabel="All categories" className="w-[200px]" />
        <Segmented label="Risk indicator" value={(risk || "all") as string} onChange={(v) => setRisk(v === "all" ? "" : v)} options={[{ value: "all", label: "All" }, { value: "High", label: "High" }, { value: "Elevated", label: "Elevated" }, { value: "Normal", label: "Normal" }]} />
        {refreshing && <span className="text-[11.5px] text-slate-ink">Updating…</span>}
      </div>
      {error && <div className="p-3"><ErrorState error={error} onRetry={reload} /></div>}
      {loading && <div className="p-6 text-[12.5px] text-slate-ink">Loading products…</div>}
      {data && data.rows.length === 0 && <EmptyState title="No products match" hint="Clear the search or choose another category." />}
      {data && data.rows.length > 0 && (
        <>
          <DataTable caption="Products" rows={data.rows} columns={columns} rowKey={(r) => r.product_id} sort={sort} onSort={setSort} onRowClick={(r) => onSelect(r.product_id)} selectedKey={selected} maxHeight={560} />
          <Pagination page={data.page} totalPages={data.total_pages} totalRows={data.total_rows} pageSize={data.page_size} onPage={setPage} label="products" />
        </>
      )}
    </Panel>
  );
}

function ProductDetail({ productId, onClose }: { productId: string; onClose: () => void }) {
  const { query, queryKey } = useFilters();
  const { data, error, loading, reload } = useApi<ProductDetailResponse>((s) => api.productDetail(productId, query, { signal: s }), `${queryKey}|${productId}`);
  return (
    <aside className="panel sticky top-[150px]" aria-label="Product detail">
      <header className="flex items-start justify-between gap-2 border-b border-line px-4 py-3">
        <div className="min-w-0">
          <div className="section-label">Product detail / {productId}</div>
          <h2 className="mt-0.5 text-[15px] font-semibold leading-snug">{data?.product.product_name ?? "Loading…"}</h2>
          {data && <p className="text-[12px] text-slate-ink">{data.product.category} · {data.product.subcategory} · {data.product.supplier_id} · {data.product.product_status}</p>}
        </div>
        <button type="button" className="btn h-7 px-2" onClick={onClose} aria-label="Close product detail"><X size={14} /></button>
      </header>
      {error && <div className="p-3"><ErrorState error={error} onRetry={reload} /></div>}
      {loading && <div className="p-6 text-[12.5px] text-slate-ink">Loading…</div>}
      {data && <DetailBody d={data} />}
    </aside>
  );
}

function DetailBody({ d }: { d: ProductDetailResponse }) {
  const m = d.metrics;
  const c = d.category_average;
  const rows: { label: string; p: string; c: string; worse: boolean }[] = [
    { label: "Unit return rate", p: pct(m.unit_return_rate), c: pct(c.unit_return_rate), worse: (m.unit_return_rate ?? 0) > (c.unit_return_rate ?? 0) },
    { label: "Contribution margin", p: pct(m.contribution_margin), c: pct(c.contribution_margin), worse: (m.contribution_margin ?? 0) < (c.contribution_margin ?? 0) },
    { label: "GMV", p: inrCompact(m.gmv), c: inrCompact(c.gmv), worse: false },
    { label: "Incremental return costs", p: inrCompact(m.incremental_costs), c: inrCompact(c.incremental_costs), worse: (m.incremental_costs ?? 0) > (c.incremental_costs ?? 0) },
    { label: "Est. contribution", p: inrCompact(m.contribution_after), c: inrCompact(c.contribution_after), worse: (m.contribution_after ?? 0) < (c.contribution_after ?? 0) },
  ];
  const reasonMax = Math.max(1, ...d.reasons.map((r) => r.units));
  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="grid grid-cols-3 gap-3">
        <Stat label="Units sold" value={int(m.units)} sub={`${int(m.returned_units)} returned`} />
        <Stat label="Return rate" value={pct(m.unit_return_rate)} tone={(m.unit_return_rate ?? 0) > (c.unit_return_rate ?? 0) ? "loss" : "neutral"} />
        <Stat label="Est. contribution" value={inrCompact(m.contribution_after)} tone={(m.contribution_after ?? 0) < 0 ? "loss" : "gain"} kind="estimated" />
      </div>
      <div>
        <div className="section-label mb-1">Monthly sales and returns</div>
        {d.monthly.length ? <UnitsAndRate rows={d.monthly} height={170} /> : <p className="text-[12px] text-slate-ink">No sales in this selection.</p>}
      </div>
      <div>
        <div className="section-label mb-1">Refunds and return costs</div>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-[12.5px]">
          {([["Refunds", m.refund], ["Reverse logistics", m.reverse_logistics], ["Restocking & inspection", m.restocking], ["Inventory write-off", m.write_off], ["Recoverable inventory", m.recoverable_inventory], ["Return profit leakage", m.return_leakage]] as const).map(([l, v]) => (
            <div key={l} className="flex justify-between gap-2 border-b border-line/60 py-1">
              <dt className="text-slate-ink">{l}</dt>
              <dd className={`num ${l === "Recoverable inventory" ? "text-teal" : ""}`}>{inr(v)}</dd>
            </div>
          ))}
        </dl>
      </div>
      <div>
        <div className="section-label mb-1">Return reasons</div>
        {d.reasons.length === 0 ? (
          <p className="text-[12px] text-slate-ink">No processed returns in this selection.</p>
        ) : (
          <ul className="space-y-1">
            {d.reasons.map((r) => (
              <li key={r.return_reason ?? "?"} className="grid grid-cols-[minmax(0,1fr)_80px_44px] items-center gap-2 text-[12px]">
                <span className="truncate">{r.return_reason}</span>
                <span className="h-1.5 bg-paper-2"><span className="block h-full bg-vermilion" style={{ width: `${(r.units / reasonMax) * 100}%` }} /></span>
                <span className="num text-right">{int(r.units)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <div className="section-label mb-1">Versus category average ({d.category_products} products)</div>
        <table className="w-full text-[12px]">
          <caption className="sr-only">Product versus category average</caption>
          <thead><tr><th scope="col" className="table-head px-2 py-1">Metric</th><th scope="col" className="table-head px-2 py-1 text-right">Product</th><th scope="col" className="table-head px-2 py-1 text-right">Category</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.label} className="border-b border-line/60">
                <td className="px-2 py-1">{r.label}</td>
                <td className={`num px-2 text-right ${r.worse ? "text-vermilion-ink" : ""}`}>{r.p}{r.worse ? " ▲" : ""}</td>
                <td className="num px-2 text-right text-slate-ink">{r.c}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-1 text-[11px] text-slate-ink">Rates compare with the whole category; amounts compare with the average product in the category.</p>
      </div>
    </div>
  );
}
