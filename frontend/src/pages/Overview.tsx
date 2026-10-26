import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, Sparkles, TrendingDown, TrendingUp } from "lucide-react";
import { api } from "../services/api";
import { useApi } from "../hooks/useApi";
import { useFilters } from "../state/FilterContext";
import type { CategoryRow, Insight, OverviewResponse, ProductRow } from "../types/api";
import { KpiLedger, KpiLedgerSkeleton } from "../components/KpiLedger";
import { EmptyState, ErrorState, Notice, Panel, PanelSkeleton, RateBar, RiskBadge } from "../components/ui";
import { DataTable, type Column } from "../components/DataTable";
import { LeakageMap } from "../charts/LeakageMap";
import { Waterfall } from "../charts/Waterfall";
import { ReturnRateTrend, SalesTrend } from "../charts/charts";
import { inrCompact, int, pct } from "../utils/format";

const ANATOMY_DEFS: Record<string, string> = {
  gmv: "Merchandise selling value of delivered (non-cancelled) lines before discounts.",
  discount: "Price reductions on those sales — a revenue reduction.",
  refund: "Money returned for refunded units — a revenue reduction, never counted as a cost.",
  net_cogs: "Inventory cost of units customers kept; returned units go back to stock at cost.",
  reverse_logistics: "Pickup and return transport (incremental return cost).",
  restocking: "Inspection, repackaging and disposal handling (incremental return cost).",
  write_off: "Returned stock that cannot be resold, at cost (incremental return cost).",
  contribution_after: "Estimated merchandise contribution after return costs. Excludes forward shipping, marketing and overheads.",
};

export default function Overview() {
  const { query, queryKey, resetFilters } = useFilters();
  const { data, error, loading, refreshing, reload } = useApi<OverviewResponse>((s) => api.overview(query, { signal: s }), queryKey);
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <div className={`flex flex-col gap-4 transition-opacity duration-150 ${refreshing ? "opacity-70" : ""}`} aria-busy={loading || refreshing}>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="panel-dark relative flex min-h-[230px] flex-col overflow-hidden p-6 lg:col-span-5">
          <ReturnLoopArt />
          <span className="relative inline-flex w-fit items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider text-[#c9a35e]">
            <Sparkles size={11} aria-hidden /> Return intelligence
          </span>
          <h2 className="relative mt-3 text-[36px] font-bold leading-[1.04] tracking-[-0.03em] text-white max-sm:text-[29px]">
            The cost of
            <br />
            <span className="gradient-text">getting it back.</span>
          </h2>
          <p className="relative mt-2.5 max-w-[42ch] text-[14px] leading-relaxed text-[#b9bfbb]">
            An operational and financial view of product returns, recovered inventory, and preventable margin erosion.
          </p>
          {data && (
            <div className="relative mt-4 flex flex-wrap gap-2 lg:mt-auto lg:pt-4">
              <HeroChip value={int(data.summary.eligible_orders)} label="delivered orders" />
              <HeroChip value={int(data.summary.units)} label="units" />
              <HeroChip value={int(data.summary.returned_units)} label="refunded returns" />
            </div>
          )}
        </div>
        <div className="lg:col-span-7">
          {data ? <Insights items={data.insights} /> : loading ? <PanelSkeleton height={170} label="insights" /> : null}
        </div>
      </div>

      {error && <ErrorState error={error} onRetry={reload} />}
      {loading && <KpiLedgerSkeleton />}
      {data && data.summary.units === 0 && (
        <div className="panel">
          <EmptyState hint="No delivered order lines exist for this combination of period, category, region and channel." onReset={resetFilters} />
        </div>
      )}

      {data && (data.summary.units ?? 0) > 0 && (
        <>
          <KpiLedger kpis={data.kpis} comparisonNote={data.comparison.note} />
          {!data.comparison.available && (
            <p className="-mt-2 text-[11.5px] text-slate-ink">{data.comparison.note}</p>
          )}

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
            <Panel
              className="xl:col-span-7"
              label="Leakage map / category exposure"
              title="Where returns erode contribution"
              subtitle="Bubble area = return profit leakage (margin forgone on refunded units + incremental return costs). Click a category to inspect its products."
              actions={selected && (
                <button type="button" className="btn h-7" onClick={() => setSelected(null)}>
                  Clear selection
                </button>
              )}
            >
              <LeakageMap rows={data.leakage_map} target={data.return_rate_target} selected={selected} onSelect={setSelected} />
              <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[11.5px] text-slate-ink" aria-label="Legend">
                <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-[#9CC7C0] ring-1 ring-teal" />At or below target</span>
                <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-[#EDA595] ring-1 ring-vermilion" />Above example target</span>
                <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-vermilion" />Negative contribution</span>
              </div>
            </Panel>
            <div className="flex flex-col gap-4 xl:col-span-5">
              <CategoryLedger rows={data.leakage_map} target={data.return_rate_target} selected={selected} onSelect={setSelected} />
              {selected && <CategoryProducts category={selected} />}
            </div>
          </div>

          <Panel
            label="Return cost anatomy / financial bridge"
            title="From merchandise sales to estimated contribution"
            subtitle="Revenue reductions (brass) are separated from incremental return costs (vermilion). Refunds appear once, as a revenue effect."
            actions={<Link to="/leakage" className="btn h-7">Full bridge <ArrowUpRight size={13} /></Link>}
          >
            <Waterfall steps={data.anatomy} definitions={ANATOMY_DEFS} height={280} />
          </Panel>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
            <Panel className="xl:col-span-7" label="Financial exposure / monthly view" title="Sales versus revenue kept" subtitle="GMV against net merchandise revenue after discounts and refunds, by order month.">
              <SalesTrend rows={data.monthly} />
            </Panel>
            <Panel className="xl:col-span-5" label="Return operations / trend" title="Return rate by order month" subtitle="Returns are attributed to the month the order was placed.">
              <ReturnRateTrend rows={data.monthly} target={data.return_rate_target} />
            </Panel>
          </div>

          <StatusPanel data={data} />
        </>
      )}
    </div>
  );
}

function Insights({ items }: { items: Insight[] }) {
  return (
    <section className="panel h-full" aria-label="Automatically generated insights">
      <header className="flex items-center justify-between gap-2 border-b border-line px-4 pb-2 pt-3">
        <span className="section-label">Findings from the current selection</span>
        <span className="rounded-full bg-teal-wash px-2 py-0.5 text-[10.5px] font-medium text-teal">Generated from calculated values</span>
      </header>
      {items.length === 0 ? (
        <p className="px-4 py-6 text-[12.5px] text-slate-ink">Not enough data in this selection to state a finding.</p>
      ) : (
        <ul className="divide-y divide-line/70">
          {items.map((i, n) => {
            const positive = i.tone === "positive";
            return (
              <li key={i.id} className="group flex gap-3 px-4 py-2.5 transition-colors hover:bg-paper/60">
                <span
                  className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-white"
                  style={{
                    background: positive ? "linear-gradient(135deg,#4FA394,#287C72)" : "linear-gradient(135deg,#E07A4F,#D94F36)",
                    boxShadow: positive ? "0 5px 12px -6px #287C72" : "0 5px 12px -6px #D94F36",
                  }}
                >
                  {positive ? <TrendingUp size={14} aria-label="Opportunity" /> : <TrendingDown size={14} aria-label="Risk" />}
                </span>
                <div className="min-w-0">
                  <div className="text-[13px] font-semibold leading-snug">
                    <span className="num mr-1.5 text-[11px] text-slate-ink">{String(n + 1).padStart(2, "0")}</span>
                    {i.title}
                  </div>
                  <div className="text-[12.5px] leading-snug text-slate-ink">{i.detail}</div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function CategoryLedger({
  rows,
  target,
  selected,
  onSelect,
}: {
  rows: CategoryRow[];
  target: number;
  selected: string | null;
  onSelect: (c: string | null) => void;
}) {
  const maxRate = Math.max(...rows.map((r) => r.unit_return_rate ?? 0));
  const columns: Column<CategoryRow>[] = [
    { key: "category", header: "Category", sortable: true, render: (r) => <span className="font-medium">{r.category}</span> },
    { key: "gmv", header: "Sales", align: "right", sortable: true, render: (r) => inrCompact(r.gmv), tip: "Gross merchandise value" },
    { key: "unit_return_rate", header: "Return rate", sortable: true, render: (r) => <RateBar value={r.unit_return_rate} max={maxRate} target={target} /> },
    {
      key: "contribution_after",
      header: "Est. contribution",
      align: "right",
      sortable: true,
      tip: "Estimated contribution after return costs",
      render: (r) => <span className={(r.contribution_after ?? 0) < 0 ? "text-vermilion-ink" : "text-teal"}>{inrCompact(r.contribution_after)}</span>,
    },
  ];
  return (
    <Panel label="Category performance" title="Sales, return rate and contribution" bodyClass="p-0" subtitle={`Marker on each bar = ${pct(target, 0)} example target.`}>
      <DataTable
        caption="Category performance"
        rows={rows}
        columns={columns}
        rowKey={(r) => r.category}
        localSort
        sort={{ by: "gmv", dir: "desc" }}
        onRowClick={(r) => onSelect(selected === r.category ? null : r.category)}
        selectedKey={selected}
        maxHeight={380}
        dense
      />
    </Panel>
  );
}

function CategoryProducts({ category }: { category: string }) {
  const { query, queryKey } = useFilters();
  const q = { ...query, product_category: category, sort_by: "return_leakage", sort_dir: "desc", page_size: 6 };
  const { data, error, loading, reload } = useApi((s) => api.productTable(q, { signal: s }), `${queryKey}|${category}`);
  const columns: Column<ProductRow>[] = [
    { key: "product_name", header: "Product", render: (r) => <span className="block max-w-[200px] truncate" title={r.product_name}>{r.product_name}</span> },
    { key: "unit_return_rate", header: "Return rate", align: "right", render: (r) => pct(r.unit_return_rate) },
    { key: "return_leakage", header: "Leakage", align: "right", render: (r) => inrCompact(r.return_leakage) },
    { key: "risk_indicator", header: "Risk", render: (r) => <RiskBadge band={r.risk_indicator} /> },
  ];
  return (
    <Panel
      label={`Selected category / ${category}`}
      title="Products with the most return leakage"
      bodyClass="p-0"
      actions={<Link to="/products" state={{ category }} className="btn h-7">All products <ArrowUpRight size={13} /></Link>}
    >
      {error && <div className="p-3"><ErrorState error={error} onRetry={reload} /></div>}
      {loading && <div className="p-4 text-[12px] text-slate-ink">Loading products…</div>}
      {data && <DataTable caption={`Top products in ${category}`} rows={data.rows} columns={columns} rowKey={(r) => r.product_id} dense maxHeight={260} />}
    </Panel>
  );
}

function StatusPanel({ data }: { data: OverviewResponse }) {
  const colors: Record<string, string> = {
    Delivered: "#287C72",
    "Partially Returned": "#B18A48",
    Returned: "#D94F36",
    "Return in Progress": "#E3C79A",
    Cancelled: "#777D79",
  };
  const rows = data.status_distribution.rows;
  return (
    <Panel label="Operational status" title="Order line status distribution" subtitle={data.status_distribution.denominator}>
      <div className="flex h-7 w-full overflow-hidden rounded-full" role="img" aria-label={rows.map((r) => `${r.status} ${pct(r.share)}`).join(", ")}>
        {rows.filter((r) => r.share > 0).map((r) => (
          <div key={r.status} style={{ width: `${r.share * 100}%`, background: colors[r.status] ?? "#777D79" }} title={`${r.status}: ${pct(r.share)}`} />
        ))}
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-3 lg:grid-cols-5">
        {rows.map((r) => (
          <div key={r.status} className="min-w-0">
            <dt className="flex items-center gap-1.5 text-[12px] text-slate-ink">
              <span className="inline-block h-2.5 w-2.5" style={{ background: colors[r.status] }} aria-hidden />
              {r.status}
            </dt>
            <dd className="num mt-0.5 text-[15px]">
              {pct(r.share)} <span className="text-[11.5px] text-slate-ink">· {int(r.lines)} lines</span>
            </dd>
          </div>
        ))}
      </dl>
      <div className="mt-3">
        <Notice>
          "Returned" means every unit on the line was refunded; "Partially Returned" means some units were. Rejected returns stay "Delivered"
          (the customer kept the item) but their logistics and inspection costs are still counted.
        </Notice>
      </div>
    </Panel>
  );
}

function HeroChip({ value, label }: { value: string; label: string }) {
  return (
    <span className="inline-flex items-baseline gap-1.5 rounded-full border border-white/10 bg-white/[0.06] px-3 py-1 text-[11.5px] text-[#b9bfbb] backdrop-blur">
      <span className="num text-[13px] font-semibold text-white">{value}</span>
      {label}
    </span>
  );
}

/** Decorative illustration: a parcel travelling out and back along a loop. */
function ReturnLoopArt() {
  return (
    <svg className="pointer-events-none absolute -right-6 -top-4 h-[230px] w-[230px] opacity-90 max-sm:opacity-40" viewBox="0 0 230 230" aria-hidden>
      <defs>
        <linearGradient id="loopA" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#D94F36" />
          <stop offset="0.5" stopColor="#B18A48" />
          <stop offset="1" stopColor="#4FA394" />
        </linearGradient>
        <linearGradient id="boxA" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#E3C489" />
          <stop offset="1" stopColor="#B18A48" />
        </linearGradient>
      </defs>
      <g className="spin-slow">
        <circle cx="128" cy="100" r="74" fill="none" stroke="url(#loopA)" strokeWidth="2" strokeDasharray="5 7" opacity="0.65" />
        <circle cx="54" cy="100" r="5" fill="#D94F36" />
        <circle cx="202" cy="100" r="5" fill="#4FA394" />
      </g>
      <circle cx="128" cy="100" r="52" fill="none" stroke="rgba(245,243,237,0.08)" strokeWidth="14" />
      <g className="float">
        <path d="M100 92 L128 78 L156 92 L128 106 Z" fill="#F0D9A8" />
        <path d="M100 92 L128 106 L128 138 L100 124 Z" fill="url(#boxA)" />
        <path d="M156 92 L128 106 L128 138 L156 124 Z" fill="#8F6E37" />
        <path d="M114 85 L142 99 L142 108 L136 105 L136 98 L108 84 Z" fill="#D94F36" opacity="0.9" />
        <path d="M120 116 l-6 -3 m6 3 l-3 5" stroke="#171A19" strokeWidth="1.6" fill="none" strokeLinecap="round" opacity="0.55" />
      </g>
      <path d="M150 46 a62 62 0 0 1 40 30" fill="none" stroke="#4FA394" strokeWidth="2.5" strokeLinecap="round" />
      <path d="M186 66 l4 10 l-10 -2" fill="none" stroke="#4FA394" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M106 154 a62 62 0 0 1 -40 -30" fill="none" stroke="#D94F36" strokeWidth="2.5" strokeLinecap="round" />
      <path d="M70 134 l-4 -10 l10 2" fill="none" stroke="#D94F36" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
