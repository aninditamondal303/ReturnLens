import { useState } from "react";
import { CircleCheck, ChevronRight, CircleX } from "lucide-react";
import { api } from "../services/api";
import { useApi } from "../hooks/useApi";
import { useFilters } from "../state/FilterContext";
import type { CategoryRow, LeakageResponse, OrderLineRow, ProductMetricRow } from "../types/api";
import { EmptyState, ErrorState, InfoTip, KindBadge, Panel, PanelSkeleton, StatusText } from "../components/ui";
import { DataTable, Pagination, type Column, type SortState } from "../components/DataTable";
import { ExportButton } from "../components/ExportButton";
import { Waterfall } from "../charts/Waterfall";
import { dateLabel, inr, inrCompact, int, pct } from "../utils/format";

const BRIDGE_DEFS: Record<string, string> = {
  gmv: "Selling value of delivered lines before discounts.",
  discount: "Revenue reduction.",
  refund: "Revenue reduction on refunded units (once).",
  net_revenue: "GMV − discounts − refunds.",
  cogs: "Inventory cost of every delivered unit.",
  returned_cost: "Cost of refunded units taken back into stock — recovered value.",
  contribution_before: "Net revenue − (COGS − returned inventory).",
  reverse_logistics: "Incremental cost: pickup and transport of returns.",
  restocking: "Incremental cost: inspection, repackaging, disposal.",
  write_off: "Incremental cost: returned stock that cannot be resold.",
  contribution_after: "Estimated contribution after incremental return costs.",
};

export default function ProfitLeakage() {
  const { query, queryKey, resetFilters } = useFilters();
  const { data, error, loading, refreshing, reload } = useApi<LeakageResponse>((s) => api.profitLeakage(query, { signal: s }), queryKey);
  const [category, setCategory] = useState<string | null>(null);
  const [product, setProduct] = useState<ProductMetricRow | null>(null);

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading || !data) return <div className="flex flex-col gap-4"><PanelSkeleton height={120} label="financial metrics" /><PanelSkeleton height={340} label="financial bridge" /></div>;
  const s = data.summary;
  if (!s.units) return <div className="panel"><EmptyState hint="No delivered order lines in this selection." onReset={resetFilters} /></div>;

  const checks = [
    { label: "GMV − discounts − refunds = net revenue", v: data.reconciliation.net_revenue_check },
    { label: "Bridge steps sum to estimated contribution", v: data.reconciliation.contribution_check },
    { label: "Category rows sum to the total", v: data.reconciliation.category_sum_check },
  ];

  return (
    <div className={`flex flex-col gap-4 transition-opacity duration-150 ${refreshing ? "opacity-70" : ""}`}>
      <section className="grid grid-cols-1 gap-px overflow-hidden rounded-[14px] border border-line bg-line shadow-[0_8px_24px_-12px_rgba(23,26,25,0.18)] lg:grid-cols-[3fr_4fr_2fr]" aria-label="Financial metrics">
        <MetricGroup title="Revenue effects" items={[
          { label: "Gross merchandise value", v: s.gmv, kind: "actual" },
          { label: "Discount value", v: s.discount, kind: "actual", loss: true },
          { label: "Refund value", v: s.refund, kind: "actual", loss: true },
        ]} />
        <MetricGroup title="Incremental return costs" items={[
          { label: "Reverse logistics", v: s.reverse_logistics, kind: "actual", loss: true },
          { label: "Restocking & inspection", v: s.restocking, kind: "actual", loss: true },
          { label: "Inventory write-off", v: s.write_off, kind: "estimated", loss: true },
          { label: "Total incremental", v: s.incremental_costs, kind: "estimated", loss: true, strong: true },
        ]} />
        <div className="bg-ink p-4 text-paper">
          <div className="section-label !text-slate">Result</div>
          <div className="mt-2 flex items-center gap-1.5 text-[12px] text-slate">Est. contribution after return costs <KindBadge dark kind="estimated" /></div>
          <div className={`num mt-1 text-[26px] leading-none ${(s.contribution_after ?? 0) < 0 ? "text-[#f08a73]" : "text-paper"}`}>{inrCompact(s.contribution_after)}</div>
          <div className="mt-2 text-[12px] text-slate">Margin on net revenue <span className="num text-paper">{pct(s.contribution_margin)}</span></div>
          <div className="mt-1 text-[12px] text-slate">Return profit leakage <span className="num text-[#f08a73]">{inrCompact(s.return_leakage)}</span></div>
        </div>
      </section>

      <Panel
        label="Contribution after returns / reconciliation"
        title="Financial bridge"
        subtitle="Every step is a signed amount from the same engine. Returned inventory is added back once at cost; the unrecoverable part is charged once as a write-off."
      >
        <Waterfall steps={data.bridge} definitions={BRIDGE_DEFS} height={330} />
        <ul className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3" aria-label="Reconciliation checks">
          {checks.map((c) => {
            const ok = Math.abs(c.v) < 0.01;
            return (
              <li key={c.label} className="flex items-center gap-2 rounded-[8px] border border-line px-3 py-1.5 text-[12px]">
                {ok ? <CircleCheck size={14} className="text-teal" aria-label="Passed" /> : <CircleX size={14} className="text-vermilion" aria-label="Failed" />}
                <span className="flex-1">{c.label}</span>
                <span className="num">{inr(c.v, true)}</span>
              </li>
            );
          })}
        </ul>
        <p className="mt-2 text-[11.5px] text-slate-ink">
          Recoverable inventory value (returned stock at cost − write-offs): <span className="num text-ink">{inr(s.recoverable_inventory)}</span>. Contribution excludes shipping fees,
          forward fulfilment, payment and marketing costs, so it is not profit.
        </p>
      </Panel>

      <Breadcrumbs category={category} product={product} onAll={() => { setCategory(null); setProduct(null); }} onCategory={() => setProduct(null)} />
      {!category && <CategoryTable rows={data.categories} portfolioMargin={s.contribution_margin ?? 0} onOpen={(c) => { setCategory(c); setProduct(null); }} />}
      {category && !product && <ProductDrill category={category} onOpen={setProduct} />}
      {category && product && <OrderDrill product={product} />}

      {data.negative_product_count > 0 && (
        <Panel label="Exceptions" title={`${data.negative_product_count} products with negative estimated contribution`} subtitle="After refunds, cost of goods and incremental return costs, these products lose money in this selection." bodyClass="p-0">
          <DataTable
            caption="Products with negative contribution"
            rows={data.negative_products}
            rowKey={(r) => r.product_id}
            localSort
            sort={{ by: "contribution_after", dir: "asc" }}
            dense
            maxHeight={320}
            columns={[
              { key: "product_name", header: "Product", sortable: true, render: (r) => <span className="font-medium">{r.product_name}</span> },
              { key: "category", header: "Category", sortable: true },
              { key: "gmv", header: "GMV", align: "right", sortable: true, render: (r) => inrCompact(r.gmv) },
              { key: "unit_return_rate", header: "Return rate", align: "right", sortable: true, render: (r) => pct(r.unit_return_rate) },
              { key: "incremental_costs", header: "Incremental costs", align: "right", sortable: true, render: (r) => inrCompact(r.incremental_costs) },
              { key: "contribution_after", header: "Est. contribution", align: "right", sortable: true, render: (r) => <span className="text-vermilion-ink">{inrCompact(r.contribution_after)}</span> },
            ]}
          />
        </Panel>
      )}
    </div>
  );
}

function MetricGroup({ title, items }: { title: string; items: { label: string; v: number | null | undefined; kind: string; loss?: boolean; strong?: boolean }[] }) {
  return (
    <div className="bg-white p-4">
      <div className="section-label">{title}</div>
      <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4" style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }}>
        {items.map((i) => (
          <div key={i.label} className="min-w-0">
            <dt className="text-[11.5px] leading-tight text-slate-ink">{i.label}</dt>
            <dd className={`num mt-0.5 ${i.strong ? "text-[20px]" : "text-[17px]"} ${i.loss ? "text-vermilion-ink" : "text-ink"}`} title={inr(i.v)}>
              {i.loss && (i.v ?? 0) > 0 ? "−" : ""}{inrCompact(i.v)}
            </dd>
            <dd className="mt-0.5"><KindBadge kind={i.kind} /></dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function Breadcrumbs({ category, product, onAll, onCategory }: { category: string | null; product: ProductMetricRow | null; onAll: () => void; onCategory: () => void }) {
  return (
    <nav aria-label="Drill-down" className="flex items-center gap-1 text-[12.5px]">
      <span className="section-label mr-2">Drill-down</span>
      <button type="button" onClick={onAll} className={category ? "text-slate-ink underline-offset-2 hover:underline" : "font-semibold"}>All categories</button>
      {category && <><ChevronRight size={13} className="text-slate" aria-hidden /><button type="button" onClick={onCategory} className={product ? "text-slate-ink underline-offset-2 hover:underline" : "font-semibold"}>{category}</button></>}
      {product && <><ChevronRight size={13} className="text-slate" aria-hidden /><span className="font-semibold">{product.product_name}</span></>}
    </nav>
  );
}

function money(v: number | null | undefined, loss = false) {
  return <span className={loss && (v ?? 0) !== 0 ? "text-vermilion-ink" : ""}>{inrCompact(v)}</span>;
}

function contributionCell(v: number | null | undefined) {
  return <span className={(v ?? 0) < 0 ? "font-semibold text-vermilion-ink" : "text-teal"}>{inrCompact(v)}</span>;
}

function flagCell(r: { negative_contribution?: boolean | null; weak_contribution?: boolean | null }) {
  if (r.negative_contribution) return <span className="rounded-[8px] bg-vermilion px-1.5 py-[1px] text-[10.5px] font-semibold text-white">Negative</span>;
  if (r.weak_contribution) return <span className="rounded-[8px] border border-brass px-1.5 py-[1px] text-[10.5px] font-semibold text-brass-ink">High sales · weak margin</span>;
  return null;
}

function CategoryTable({ rows, portfolioMargin, onOpen }: { rows: CategoryRow[]; portfolioMargin: number; onOpen: (c: string) => void }) {
  const columns: Column<CategoryRow>[] = [
    { key: "category", header: "Category", sortable: true, render: (r) => <span className="font-medium">{r.category}</span> },
    { key: "flag", header: "Flag", render: flagCell },
    { key: "gmv", header: "GMV", align: "right", sortable: true, render: (r) => inrCompact(r.gmv) },
    { key: "discount", header: "Discounts", align: "right", sortable: true, render: (r) => money(r.discount) },
    { key: "refund", header: "Refunds", align: "right", sortable: true, render: (r) => money(r.refund) },
    { key: "cogs", header: "COGS", align: "right", sortable: true, render: (r) => inrCompact(r.cogs), tip: "Gross cost of goods delivered (before returned stock is added back)." },
    { key: "reverse_logistics", header: "Rev. logistics", align: "right", sortable: true, render: (r) => money(r.reverse_logistics, true) },
    { key: "restocking", header: "Restocking", align: "right", sortable: true, render: (r) => money(r.restocking, true) },
    { key: "write_off", header: "Write-off", align: "right", sortable: true, render: (r) => money(r.write_off, true) },
    { key: "incremental_costs", header: "Incr. costs", align: "right", sortable: true, render: (r) => money(r.incremental_costs, true) },
    { key: "contribution_before", header: "Contrib. before", align: "right", sortable: true, render: (r) => contributionCell(r.contribution_before), tip: "Estimated contribution before incremental return costs." },
    { key: "contribution_after", header: "Contrib. after", align: "right", sortable: true, render: (r) => contributionCell(r.contribution_after), tip: "Estimated contribution after incremental return costs." },
    { key: "unit_return_rate", header: "Return rate", align: "right", sortable: true, render: (r) => <span className={(r.unit_return_rate ?? 0) > 0.08 ? "text-vermilion-ink" : ""}>{pct(r.unit_return_rate)}</span> },
  ];
  return (
    <Panel
      label="Profitability by category"
      title="Category profitability after returns"
      subtitle={<>Click a category to drill into products, then orders. “Weak margin” = above-median sales share with a contribution margin below half of the portfolio’s {pct(portfolioMargin)}.<InfoTip text="Flags are calculated by the API from the current selection." /></>}
      bodyClass="p-0"
    >
      <DataTable caption="Category profitability" rows={rows} columns={columns} rowKey={(r) => r.category} localSort sort={{ by: "return_leakage", dir: "desc" }} onRowClick={(r) => onOpen(r.category)} dense maxHeight={480} />
    </Panel>
  );
}

function ProductDrill({ category, onOpen }: { category: string; onOpen: (p: ProductMetricRow) => void }) {
  const { query, queryKey } = useFilters();
  const { data, error, loading, reload } = useApi((s) => api.leakageProducts({ ...query, category }, { signal: s }), `${queryKey}|${category}`);
  const columns: Column<ProductMetricRow>[] = [
    { key: "product_name", header: "Product", sortable: true, render: (r) => <span className="font-medium">{r.product_name}</span> },
    { key: "flag", header: "Flag", render: flagCell },
    { key: "subcategory", header: "Subcategory", sortable: true },
    { key: "units", header: "Units", align: "right", sortable: true, render: (r) => int(r.units) },
    { key: "gmv", header: "GMV", align: "right", sortable: true, render: (r) => inrCompact(r.gmv) },
    { key: "refund", header: "Refunds", align: "right", sortable: true, render: (r) => money(r.refund) },
    { key: "incremental_costs", header: "Incr. costs", align: "right", sortable: true, render: (r) => money(r.incremental_costs, true) },
    { key: "contribution_before", header: "Contrib. before", align: "right", sortable: true, render: (r) => contributionCell(r.contribution_before) },
    { key: "contribution_after", header: "Contrib. after", align: "right", sortable: true, render: (r) => contributionCell(r.contribution_after) },
    { key: "unit_return_rate", header: "Return rate", align: "right", sortable: true, render: (r) => pct(r.unit_return_rate) },
  ];
  return (
    <Panel label={`Category / ${category}`} title="Products in this category" subtitle="Click a product to list its order lines." bodyClass="p-0">
      {error && <div className="p-3"><ErrorState error={error} onRetry={reload} /></div>}
      {loading && <div className="p-6 text-[12.5px] text-slate-ink">Loading products…</div>}
      {data && <DataTable caption={`Products in ${category}`} rows={data.products} columns={columns} rowKey={(r) => r.product_id} localSort sort={{ by: "return_leakage", dir: "desc" }} onRowClick={onOpen} dense maxHeight={480} />}
    </Panel>
  );
}

function OrderDrill({ product }: { product: ProductMetricRow }) {
  const { query, queryKey } = useFilters();
  const [page, setPage] = useState(1);
  const [returnedOnly, setReturnedOnly] = useState(false);
  const [sort, setSort] = useState<SortState>({ by: "order_date", dir: "desc" });
  const params = { ...query, product_id: product.product_id, returned_only: returnedOnly || undefined, sort_by: sort.by, sort_dir: sort.dir };
  const { data, error, loading, reload } = useApi(
    (s) => api.orderLines({ ...params, page, page_size: 15 }, { signal: s }),
    `${queryKey}|${product.product_id}|${page}|${returnedOnly}|${sort.by}|${sort.dir}`,
  );
  const columns: Column<OrderLineRow>[] = [
    { key: "order_id", header: "Order", sortable: true, render: (r) => <span className="num text-[12px]">{r.order_id}</span> },
    { key: "order_date", header: "Date", sortable: true, render: (r) => <span className="num text-[12px]">{dateLabel(r.order_date)}</span> },
    { key: "shipping_region", header: "Region" },
    { key: "quantity", header: "Qty", align: "right", sortable: true },
    { key: "net_sales", header: "Net sales", align: "right", sortable: true, render: (r) => inr(r.net_sales) },
    { key: "refund", header: "Refund", align: "right", sortable: true, render: (r) => money(r.refund) },
    { key: "costs", header: "Return costs", align: "right", render: (r) => money(r.reverse_logistics + r.restocking + r.write_off, true) },
    { key: "primary_reason", header: "Reason", render: (r) => r.primary_reason || "—" },
    { key: "actual_return_status", header: "Outcome", render: (r) => <StatusText status={r.actual_return_status} /> },
  ];
  return (
    <Panel
      label={`Product / ${product.product_id}`}
      title={`Order lines for ${product.product_name}`}
      bodyClass="p-0"
      actions={
        <>
          <label className="flex items-center gap-1.5 text-[12px]">
            <input type="checkbox" checked={returnedOnly} onChange={(e) => { setReturnedOnly(e.target.checked); setPage(1); }} /> Returns only
          </label>
          <ExportButton path="/api/order-lines" params={params} fileName={`shopsphere_order_lines_${product.product_id}.csv`} />
        </>
      }
    >
      {error && <div className="p-3"><ErrorState error={error} onRetry={reload} /></div>}
      {loading && <div className="p-6 text-[12.5px] text-slate-ink">Loading order lines…</div>}
      {data && data.rows.length === 0 && <EmptyState title="No order lines" />}
      {data && data.rows.length > 0 && (
        <>
          <DataTable caption="Order lines" rows={data.rows} columns={columns} rowKey={(r) => r.order_line_id} sort={sort} onSort={(s) => { setSort(s); setPage(1); }} dense maxHeight={480} />
          <Pagination page={data.page} totalPages={data.total_pages} totalRows={data.total_rows} pageSize={data.page_size} onPage={setPage} label="order lines" />
        </>
      )}
    </Panel>
  );
}
