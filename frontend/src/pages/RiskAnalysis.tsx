import { useState } from "react";
import { api } from "../services/api";
import { useApi, useDebounced } from "../hooks/useApi";
import { useFilters } from "../state/FilterContext";
import type { RiskOrderRow, RiskResponse } from "../types/api";
import { EmptyState, ErrorState, Notice, Panel, PanelSkeleton, RiskBadge, Stat, StatusText } from "../components/ui";
import { DataTable, Pagination, type Column, type SortState } from "../components/DataTable";
import { Segmented, SearchInput, SelectField } from "../components/controls";
import { ExportButton } from "../components/ExportButton";
import { AnomalyPanel } from "../components/AnomalyPanel";
import { PointScatter, RateBars, ScoreHistogram } from "../charts/charts";
import { C } from "../charts/theme";
import { dateLabel, inr, inrCompact, int, pct } from "../utils/format";

const STATUS_OPTIONS = ["Returned", "Return in progress", "Return rejected", "Window open", "Not returned"];
const FACTOR_KEYS = [
  ["pts_product_history", "Product return history"],
  ["pts_category_history", "Category return history"],
  ["pts_discount", "Discount depth"],
  ["pts_shipping_delay", "Late delivery"],
  ["pts_order_value", "High value vs category"],
  ["pts_cash_on_delivery", "Cash on delivery"],
  ["pts_multi_unit", "Multiple units"],
] as const;

export default function RiskAnalysis() {
  const { query, queryKey, resetFilters } = useFilters();
  const { data, error, loading, refreshing, reload } = useApi<RiskResponse>((s) => api.returns(query, { signal: s }), queryKey);

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading || !data) {
    return (
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <PanelSkeleton label="risk metrics" height={120} />
        <PanelSkeleton label="score distribution" />
      </div>
    );
  }
  if (data.kpis.eligible_lines === 0) {
    return <div className="panel"><EmptyState hint="No delivered order lines in this selection." onReset={resetFilters} /></div>;
  }
  const k = data.kpis;
  const target = 0.08;
  return (
    <div className={`flex flex-col gap-4 transition-opacity duration-150 ${refreshing ? "opacity-70" : ""}`}>
      <Notice tone="warn">
        <b>Historical risk assessment, not a prediction model.</b> Each past order line is re-scored with only the information that existed at
        delivery. Scores are a transparent heuristic ranking (0–100), not probabilities, and have not been validated against real outcomes.
      </Notice>

      <section className="panel grid grid-cols-2 divide-line md:grid-cols-3 xl:grid-cols-6 xl:divide-x" aria-label="Risk metrics">
        <div className="p-4"><Stat label="Eligible orders" value={int(k.eligible_orders)} sub={`${int(k.eligible_lines)} order lines`} kind="actual" /></div>
        <div className="p-4"><Stat label="Returned orders" value={int(k.returned_orders)} sub="≥1 refunded return" kind="actual" /></div>
        <div className="p-4">
          <Stat label="Order return rate" value={pct(k.order_return_rate)} tone="loss" kind="derived"
            tip="Orders with at least one refunded return ÷ orders with at least one delivered line. Counts each order once, however many units came back." />
        </div>
        <div className="p-4">
          <Stat label="Unit return rate" value={pct(k.unit_return_rate)} tone="loss" kind="derived"
            tip="Refunded units ÷ delivered units. Lower than the order rate when only some items in an order are returned." />
        </div>
        <div className="p-4">
          <Stat label="High-risk orders" value={int(k.high_risk_orders)} sub={`${int(k.high_risk_lines)} lines scored ≥ 65`} kind="estimated"
            tip="Orders containing at least one order line with a heuristic score of 65 or more." />
        </div>
        <div className="p-4">
          <Stat label="High-risk exposure" value={inrCompact(k.high_risk_exposure)} tone="loss" kind="estimated"
            sub={`of ${inrCompact(k.high_risk_value)} order value`}
            tip={data.model.exposure_method + " This is an expected cost, not a confirmed loss."} />
        </div>
      </section>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Panel className="xl:col-span-7" label="Risk score distribution" title="How order lines spread across the 0–100 score" subtitle="Bars coloured by band: Low 0–34, Medium 35–64, High 65–100. Tooltips show how many lines were later returned.">
          <ScoreHistogram bins={data.score_distribution} height={250} />
        </Panel>
        <Panel className="xl:col-span-5" label="Band check / in-sample" title="Observed return rate by score band" subtitle="Measured on this synthetic history — a sanity check that the ranking is sensible, not an accuracy claim." bodyClass="p-0">
          <table className="w-full text-[12.5px]">
            <caption className="sr-only">Observed return rate by risk band</caption>
            <thead>
              <tr>
                {["Band", "Lines", "Avg score", "Unit return rate", "Exposure"].map((h, i) => (
                  <th key={h} scope="col" className={`table-head border-b border-line px-3 py-2 ${i > 0 ? "text-right" : ""}`}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.by_band.map((b) => (
                <tr key={b.band} className="border-b border-line/70">
                  <td className="px-3 py-2.5"><RiskBadge band={b.band} /></td>
                  <td className="num px-3 text-right">{int(b.lines)}</td>
                  <td className="num px-3 text-right">{b.avg_score?.toFixed(1) ?? "—"}</td>
                  <td className="px-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <div className="h-1.5 w-20 bg-paper-2" aria-hidden>
                        <div className={b.band === "High" ? "h-full bg-vermilion" : b.band === "Medium" ? "h-full bg-brass" : "h-full bg-slate"} style={{ width: `${Math.min(100, (b.unit_return_rate ?? 0) * 200)}%` }} />
                      </div>
                      <span className="num">{pct(b.unit_return_rate)}</span>
                    </div>
                  </td>
                  <td className="num px-3 text-right">{inrCompact(b.exposure)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="p-3"><ModelCard data={data} /></div>
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Panel label="By category" title="Return rate by category"><RateBars rows={[...data.by_category].sort((a, b) => (b.unit_return_rate ?? 0) - (a.unit_return_rate ?? 0))} target={target} /></Panel>
        <Panel label="By discount band" title="Deeper discounts, more returns?"><RateBars rows={data.by_discount} target={target} /></Panel>
        <Panel label="By delivery delay" title="Late deliveries and returns"><RateBars rows={data.by_delay} target={target} /></Panel>
        <Panel label="By line value" title="Order value bands"><RateBars rows={data.by_value} target={target} /></Panel>
      </div>
      <p className="-mt-2 text-[11.5px] text-slate-ink">Associations in historical data, not proof of cause. Dashed line = {pct(target, 0)} example target.</p>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Panel className="xl:col-span-6" label="Score vs exposure" title="Risk score against estimated exposure" subtitle="All high-risk lines (up to 250) plus a fixed random sample of the rest. Exposure is an expected cost, not a loss.">
          <PointScatter
            height={280}
            xLabel="Heuristic risk score"
            yLabel="Estimated exposure"
            xFormat={(v) => v.toFixed(0)}
            yFormat={(v) => inrCompact(v)}
            points={data.scatter.map((p) => ({
              id: p.order_line_id,
              x: p.risk_score ?? 0,
              y: p.risk_exposure ?? 0,
              color: p.risk_band === "High" ? C.vermilion : p.risk_band === "Medium" ? C.brass : C.slate,
              title: `${p.order_id} · ${p.product_name}`,
              rows: [
                { label: "Score", value: (p.risk_score ?? 0).toFixed(1) },
                { label: "Exposure", value: inr(p.risk_exposure) },
                { label: "Category", value: p.category },
                { label: "Actual outcome", value: p.actual_return_status },
              ],
            }))}
          />
        </Panel>
        <Panel className="xl:col-span-6" label="Return reasons" title="Why customers send items back" subtitle="Processed returns (refunded and rejected) in this selection." bodyClass="p-0">
          <ReasonList data={data} />
        </Panel>
      </div>

      <RiskOrdersTable />
      <AnomalyPanel />
    </div>
  );
}

function ModelCard({ data }: { data: RiskResponse }) {
  const total = data.model.factors.reduce((s, f) => s + f.max_points, 0);
  return (
    <details className="group rounded-[8px] border border-line bg-paper">
      <summary className="cursor-pointer list-none px-3 py-2 text-[12.5px] font-semibold marker:hidden">
        How the score is calculated <span className="text-slate-ink group-open:hidden">(show)</span>
      </summary>
      <div className="border-t border-line px-3 py-2.5 text-[12px]">
        <p className="text-slate-ink">{data.model.type}. Prediction point: {data.model.prediction_point}</p>
        <ul className="mt-2 space-y-1">
          {data.model.factors.map((f) => (
            <li key={f.key} className="grid grid-cols-[1fr_auto] items-center gap-2">
              <span>
                {f.label} <span className="text-slate-ink">— {f.scale}</span>
              </span>
              <span className="flex items-center gap-2">
                <span className="h-1.5 bg-ink" style={{ width: `${(f.max_points / total) * 160}px` }} aria-hidden />
                <span className="num w-10 text-right">{f.max_points} pts</span>
              </span>
            </li>
          ))}
        </ul>
        <div className="mt-2 font-medium">Leakage controls</div>
        <ul className="mt-1 list-disc space-y-0.5 pl-4 text-slate-ink">
          {data.model.leakage_controls.map((c) => <li key={c}>{c}</li>)}
        </ul>
      </div>
    </details>
  );
}

function ReasonList({ data }: { data: RiskResponse }) {
  const max = Math.max(...data.reasons.map((r) => r.share ?? 0), 0.01);
  const reasonNames = data.reasons.map((r) => r.reason);
  return (
    <div>
      <ul className="divide-y divide-line">
        {data.reasons.map((r) => (
          <li key={r.reason} className="grid grid-cols-[minmax(0,1fr)_120px_70px_80px] items-center gap-3 px-4 py-2 text-[12.5px]">
            <span className="truncate">{r.reason}</span>
            <span className="h-1.5 bg-paper-2" aria-hidden>
              <span className="block h-full bg-ink" style={{ width: `${((r.share ?? 0) / max) * 100}%` }} />
            </span>
            <span className="num text-right">{pct(r.share)}</span>
            <span className="num text-right text-slate-ink">{int(r.units)} units</span>
          </li>
        ))}
      </ul>
      <details className="border-t border-line">
        <summary className="cursor-pointer px-4 py-2 text-[12.5px] font-semibold">Reason mix by category (share of returned units)</summary>
        <div className="overflow-auto">
          <table className="w-full text-[11.5px]">
            <caption className="sr-only">Return reason share by category</caption>
            <thead>
              <tr>
                <th scope="col" className="table-head px-3 py-1.5">Category</th>
                {reasonNames.map((n) => <th key={n} scope="col" className="table-head px-2 py-1.5 text-right" title={n}>{n.split(" ")[0]}</th>)}
              </tr>
            </thead>
            <tbody>
              {data.reason_matrix.map((row) => (
                <tr key={row.category} className="border-b border-line/70">
                  <td className="whitespace-nowrap px-3 py-1.5">{row.category}</td>
                  {reasonNames.map((n) => {
                    const v = row.reasons[n] ?? 0;
                    return (
                      <td key={n} className="num px-2 text-right" style={{ background: `rgba(217,79,54,${Math.min(0.55, (v ?? 0) * 0.9)})` }}>
                        {v ? pct(v, 0) : "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}

function RiskOrdersTable() {
  const { query, queryKey } = useFilters();
  const [band, setBand] = useState<"High" | "Medium" | "Low" | "all">("High");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortState>({ by: "risk_score", dir: "desc" });
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<string | null>(null);
  const debounced = useDebounced(search);
  const params = { ...query, risk_band: band, return_status: status || undefined, search: debounced || undefined, sort_by: sort.by, sort_dir: sort.dir };
  const key = `${queryKey}|${band}|${status}|${debounced}|${sort.by}|${sort.dir}`;
  const pageKey = `${key}|${page}`;
  const { data, error, loading, refreshing, reload } = useApi((s) => api.riskOrders({ ...params, page, page_size: 15 }, { signal: s }), pageKey);
  const reset = (fn: () => void) => { fn(); setPage(1); };

  const columns: Column<RiskOrderRow>[] = [
    { key: "order_id", header: "Order", sortable: true, render: (r) => <span className="num text-[12px]">{r.order_id}</span> },
    { key: "order_date", header: "Date", sortable: true, render: (r) => <span className="num text-[12px]">{dateLabel(r.order_date)}</span> },
    { key: "product_name", header: "Product", sortable: true, render: (r) => <span className="block max-w-[190px] truncate" title={r.product_name}>{r.product_name}</span> },
    { key: "category", header: "Category", sortable: true },
    { key: "shipping_region", header: "Region", sortable: true },
    { key: "line_net_value", header: "Order value", align: "right", sortable: true, render: (r) => inr(r.line_net_value) },
    { key: "discount_pct", header: "Disc.", align: "right", sortable: true, render: (r) => pct(r.discount_pct, 0) },
    { key: "shipping_delay_days", header: "Delay", align: "right", sortable: true, render: (r) => (r.shipping_delay_days === null ? "—" : r.shipping_delay_days > 0 ? `+${r.shipping_delay_days}d` : "on time") },
    { key: "risk_score", header: "Score", align: "right", sortable: true, render: (r) => <span className={r.risk_band === "High" ? "font-semibold text-vermilion-ink" : ""}>{r.risk_score?.toFixed(1)}</span> },
    { key: "risk_band", header: "Class", render: (r) => <RiskBadge band={r.risk_band} /> },
    { key: "risk_exposure", header: "Exposure", align: "right", sortable: true, tip: "Estimated expected return-related cost — not a loss.", render: (r) => inrCompact(r.risk_exposure) },
    { key: "actual_return_status", header: "Actual outcome", render: (r) => <StatusText status={r.actual_return_status} /> },
  ];

  const selectedRow = data?.rows.find((r) => r.order_line_id === open) ?? null;
  return (
    <Panel
      label="Scored order lines"
      title={band === "all" ? "All scored order lines" : `${band}-risk order lines`}
      subtitle="Click a row to see which factors produced its score. Export includes every row matching the filters, not just this page."
      bodyClass="p-0"
      actions={<ExportButton path="/api/risk-orders" params={params} fileName="shopsphere_risk_orders.csv" />}
    >
      <div className="flex flex-wrap items-end gap-3 border-b border-line px-4 py-2.5">
        <Segmented
          label="Risk band"
          value={band}
          onChange={(v) => reset(() => setBand(v))}
          options={[{ value: "High", label: "High" }, { value: "Medium", label: "Medium" }, { value: "Low", label: "Low" }, { value: "all", label: "All" }]}
        />
        <SelectField label="Actual outcome" value={status} onChange={(v) => reset(() => setStatus(v))} options={STATUS_OPTIONS} allLabel="Any outcome" className="w-[170px]" />
        <SearchInput value={search} onChange={(v) => reset(() => setSearch(v))} placeholder="Order ID or product" label="Search order lines" className="w-[230px]" />
        {refreshing && <span className="text-[11.5px] text-slate-ink">Updating…</span>}
      </div>
      {error && <div className="p-3"><ErrorState error={error} onRetry={reload} /></div>}
      {loading && <div className="p-6 text-[12.5px] text-slate-ink">Loading order lines…</div>}
      {data && data.rows.length === 0 && <EmptyState title="No order lines match" hint="Try another band, outcome or search term." />}
      {data && data.rows.length > 0 && (
        <>
          <DataTable
            caption="Scored order lines"
            rows={data.rows}
            columns={columns}
            rowKey={(r) => r.order_line_id}
            sort={sort}
            onSort={(s) => reset(() => setSort(s))}
            onRowClick={(r) => setOpen(open === r.order_line_id ? null : r.order_line_id)}
            selectedKey={open}
            maxHeight={560}
          />
          {selectedRow && <FactorBreakdown row={selectedRow} />}
          <Pagination page={data.page} totalPages={data.total_pages} totalRows={data.total_rows} pageSize={data.page_size} onPage={setPage} label="order lines" />
        </>
      )}
    </Panel>
  );
}

function FactorBreakdown({ row }: { row: RiskOrderRow }) {
  return (
    <div className="border-t border-line bg-paper px-4 py-3" aria-live="polite">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="text-[13px] font-semibold">
          Score breakdown · <span className="num">{row.order_line_id}</span> · {row.product_name}
        </div>
        <div className="text-[12px] text-slate-ink">
          Product history rate at order time <span className="num text-ink">{pct(row.product_hist_rate)}</span> · category{" "}
          <span className="num text-ink">{pct(row.category_hist_rate)}</span> · payment {row.payment_method} · qty {row.quantity}
        </div>
      </div>
      <ul className="mt-2 grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-2 lg:grid-cols-4">
        {FACTOR_KEYS.map(([k, label]) => {
          const v = (row[k] as number | null) ?? 0;
          return (
            <li key={k} className="flex items-center justify-between gap-2 text-[12px]">
              <span>{label}</span>
              <span className="flex items-center gap-2">
                <span className="h-1.5 w-16 bg-paper-2" aria-hidden><span className="block h-full bg-vermilion" style={{ width: `${Math.min(100, (v / 28) * 100)}%` }} /></span>
                <span className="num w-10 text-right">+{v.toFixed(1)}</span>
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
