import { useEffect, useMemo, useState } from "react";
import { Plus, X } from "lucide-react";
import { api, scenarioQuery } from "../services/api";
import { useApi, useDebounced } from "../hooks/useApi";
import { useFilters } from "../state/FilterContext";
import type { PresetResult, ScenarioParams, WhatIfResponse } from "../types/api";
import { ErrorState, Notice, Panel, PanelSkeleton } from "../components/ui";
import { Segmented, Slider } from "../components/controls";
import { CompareBars } from "../charts/charts";
import { inr, inrCompact, pct } from "../utils/format";

const DEFAULT: ScenarioParams = {
  return_reduction: 0.12,
  logistics_reduction: 0.1,
  write_off_reduction: 0.2,
  retained_sale_share: 0.65,
  prevention_spend: 0,
  category_overrides: {},
};

const COMPONENT_LABEL: Record<string, string> = {
  reverse_logistics: "Reverse logistics",
  restocking: "Restocking & inspection",
  write_off: "Inventory write-off",
};

export default function WhatIfSimulator() {
  const { query, queryKey } = useFilters();
  const [params, setParams] = useState<ScenarioParams>(DEFAULT);
  const [preset, setPreset] = useState<string>("moderate");
  const debounced = useDebounced(params, 200);
  const q = useMemo(() => ({ ...query, ...scenarioQuery(debounced) }), [query, debounced]);
  const { data, error, loading, refreshing, reload } = useApi<WhatIfResponse>((s) => api.whatIf(q, { signal: s }), `${queryKey}|${JSON.stringify(debounced)}`);

  // While a preset is active, keep the levers in sync with that preset as computed by the API
  // for the current filters (preset spending scales with the filtered baseline).
  useEffect(() => {
    if (!data || preset === "custom") return;
    const p = data.presets.find((x) => x.key === preset);
    if (!p) return;
    const same =
      p.params.return_reduction === params.return_reduction &&
      p.params.logistics_reduction === params.logistics_reduction &&
      p.params.write_off_reduction === params.write_off_reduction &&
      p.params.retained_sale_share === params.retained_sale_share &&
      p.params.prevention_spend === params.prevention_spend &&
      Object.keys(params.category_overrides).length === 0;
    if (!same) setParams({ ...p.params, category_overrides: {} });
  }, [data, preset, params]);

  const update = (patch: Partial<ScenarioParams>) => {
    setParams((p) => ({ ...p, ...patch }));
    setPreset("custom");
  };
  const applyPreset = (key: string) => {
    setPreset(key);
    const p = data?.presets.find((x) => x.key === key);
    if (p) setParams({ ...p.params, category_overrides: {} });
  };

  if (error && !data) return <ErrorState error={error} onRetry={reload} />;
  if (loading || !data) return <div className="grid grid-cols-1 gap-4 lg:grid-cols-3"><PanelSkeleton label="controls" height={420} /><div className="lg:col-span-2"><PanelSkeleton label="scenario results" height={420} /></div></div>;
  const r = data.result;
  const maxSpend = Math.max(100000, Math.ceil((r.baseline_incremental_costs * 0.6) / 50000) * 50000);

  return (
    <div className="flex flex-col gap-4">
      <Notice tone="warn"><b>Scenario results are hypothetical.</b> {data.disclaimer} Every number below is recalculated by the API from the same historical baseline when a control changes.</Notice>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <section className="panel-dark flex flex-col gap-5 self-start p-5 xl:sticky xl:top-[150px] xl:col-span-4" aria-label="Scenario controls">
          <div>
            <div className="section-label !text-slate">Scenario lab / assumptions</div>
            <h2 className="mt-1 text-[16px] font-semibold text-paper">Intervention levers</h2>
          </div>
          <Segmented
            dark
            label="Preset scenario"
            value={preset}
            onChange={applyPreset}
            options={[{ value: "conservative", label: "Conservative" }, { value: "moderate", label: "Moderate" }, { value: "aggressive", label: "Aggressive" }, { value: "custom", label: "Custom" }]}
          />
          <Slider label="Return-rate reduction" value={params.return_reduction} onChange={(v) => update({ return_reduction: v })} min={0} max={0.3} step={0.01} format={(v) => pct(v, 0)} hint="share of refunded returns avoided" />
          <Slider label="Reverse-logistics cost reduction" value={params.logistics_reduction} onChange={(v) => update({ logistics_reduction: v })} min={0} max={0.3} step={0.01} format={(v) => pct(v, 0)} hint="cheaper pickups on remaining returns" />
          <Slider label="Inventory write-off reduction" value={params.write_off_reduction} onChange={(v) => update({ write_off_reduction: v })} min={0} max={0.5} step={0.01} format={(v) => pct(v, 0)} hint="better grading / refurbishment" />
          <Slider label="Avoided returns kept as sales" value={params.retained_sale_share} onChange={(v) => update({ retained_sale_share: v })} min={0} max={1} step={0.05} format={(v) => pct(v, 0)} hint="the rest become no-sale" />
          <div className="flex flex-col gap-1.5">
            <Slider label="Prevention spending" value={Math.min(params.prevention_spend, maxSpend)} onChange={(v) => update({ prevention_spend: v })} min={0} max={maxSpend} step={5000} format={(v) => inrCompact(v)} hint={`for ${r.months_in_period} months`} />
            <label className="flex items-center gap-2 text-[12px] text-slate">
              Exact amount (₹)
              <input
                type="number"
                min={0}
                step={1000}
                value={Math.round(params.prevention_spend)}
                onChange={(e) => update({ prevention_spend: Math.max(0, Number(e.target.value) || 0) })}
                className="num h-7 w-32 rounded-[8px] border border-ink-3 bg-ink-2 px-2 text-paper focus:border-paper focus:outline-none"
              />
            </label>
          </div>
          <CategoryOverrides categories={data.categories} overrides={params.category_overrides} onChange={(o) => update({ category_overrides: o })} />
          {error && <p role="alert" className="text-[12px] text-[#f08a73]">Last update failed: {error.message}</p>}
        </section>

        <div className={`flex flex-col gap-4 xl:col-span-8 transition-opacity duration-150 ${refreshing ? "opacity-70" : ""}`} aria-live="polite">
          <section className="panel grid grid-cols-2 gap-px overflow-hidden bg-line md:grid-cols-4" aria-label="Scenario results">
            <Result label="Baseline incremental return costs" value={inrCompact(r.baseline_incremental_costs)} sub="historical, selected period" />
            <Result label="Scenario incremental return costs" value={inrCompact(r.scenario_incremental_costs)} sub={`${pct(r.cost_reduction_pct)} lower`} tone="gain" />
            <Result label="Estimated gross savings" value={inrCompact(r.gross_cost_savings)} sub={`volume ${inrCompact(r.volume_savings)} · efficiency ${inrCompact(r.efficiency_savings)}`} tone="gain" />
            <Result label="Retained margin on kept sales" value={inrCompact(r.retained_margin)} sub={`${Math.round(r.avoided_returned_units)} returns avoided`} tone="gain" />
            <Result label="Additional intervention spending" value={inrCompact(r.prevention_spend)} sub="entered assumption" tone="loss" />
            <Result
              label="Net estimated improvement"
              value={inrCompact(r.net_improvement)}
              sub={r.roi !== null ? `ROI ${(r.roi * 100).toFixed(0)}%${r.payback_months !== null ? ` · payback ${r.payback_months.toFixed(1)} mo` : ""}` : "ROI needs spending > 0"}
              tone={r.net_improvement >= 0 ? "gain" : "loss"}
              strong
            />
            <Result label="Scenario contribution after return costs" value={inrCompact(r.scenario_contribution)} sub={`baseline ${inrCompact(r.baseline_contribution)}`} />
            <Result label="Unit return rate" value={pct(r.scenario_unit_return_rate)} sub={`baseline ${pct(r.baseline_unit_return_rate)}`} />
          </section>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Panel label="Cost components" title="Baseline versus scenario" subtitle="Each component is modelled separately; restocking has no efficiency lever.">
              <CompareBars rows={r.components.map((c) => ({ label: COMPONENT_LABEL[c.key] ?? c.key, baseline: c.baseline, scenario: c.scenario }))} />
            </Panel>
            <Panel label="Method" title="Formulas used">
              <ol className="list-decimal space-y-1.5 pl-4 text-[12.5px] leading-snug">
                {data.formulas.map((f) => <li key={f}>{f}</li>)}
              </ol>
              <p className="mt-3 text-[11.5px] text-slate-ink">
                Refunds are revenue effects, not costs: an avoided return only adds back margin (refund minus the cost of the unit) for the share kept as a sale.
              </p>
            </Panel>
          </div>

          <PresetTable presets={data.presets} custom={r} />

          <Panel label="By category" title="Where the scenario saves most" bodyClass="p-0">
            <div className="max-h-[320px] overflow-auto">
              <table className="w-full text-[12.5px]">
                <caption className="sr-only">Scenario results by category</caption>
                <thead><tr>{["Category", "Return reduction", "Return rate (base → scenario)", "Baseline costs", "Scenario costs", "Gross savings", "Retained margin"].map((h, i) => <th key={h} scope="col" className={`table-head border-b border-line px-3 py-2 ${i ? "text-right" : ""}`}>{h}</th>)}</tr></thead>
                <tbody>
                  {r.by_category.map((c) => (
                    <tr key={c.category} className="border-b border-line/70">
                      <td className="px-3 py-1.5 font-medium">{c.category}{params.category_overrides[c.category] !== undefined && <span className="ml-1.5 text-[10.5px] text-brass-ink">override</span>}</td>
                      <td className="num px-3 text-right">{pct(c.return_reduction, 0)}</td>
                      <td className="num px-3 text-right">{pct(c.baseline_unit_return_rate)} → {pct(c.scenario_unit_return_rate)}</td>
                      <td className="num px-3 text-right">{inrCompact(c.baseline_incremental)}</td>
                      <td className="num px-3 text-right">{inrCompact(c.scenario_incremental)}</td>
                      <td className="num px-3 text-right text-teal">{inrCompact(c.gross_savings)}</td>
                      <td className="num px-3 text-right text-teal">{inrCompact(c.retained_margin)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}

function Result({ label, value, sub, tone, strong }: { label: string; value: string; sub?: string; tone?: "gain" | "loss"; strong?: boolean }) {
  return (
    <div className={`p-4 ${strong ? "bg-gradient-to-br from-[#1f302c] via-[#24403b] to-[#287C72] text-paper" : "bg-white"}`}>
      <div className={`text-[11.5px] ${strong ? "text-slate" : "text-slate-ink"}`}>{label}</div>
      <div className={`num mt-1 ${strong ? "text-[24px]" : "text-[19px]"} leading-none ${tone === "gain" ? (strong ? "text-[#7fcabd]" : "text-teal") : tone === "loss" ? (strong ? "text-[#f08a73]" : "text-vermilion-ink") : ""}`}>{value}</div>
      {sub && <div className={`mt-1 text-[11px] ${strong ? "text-slate" : "text-slate-ink"}`}>{sub}</div>}
    </div>
  );
}

function CategoryOverrides({ categories, overrides, onChange }: { categories: string[]; overrides: Record<string, number>; onChange: (o: Record<string, number>) => void }) {
  const unused = categories.filter((c) => overrides[c] === undefined);
  const [pick, setPick] = useState("");
  return (
    <div className="border-t border-ink-3 pt-4">
      <div className="text-[12.5px] font-medium text-paper">Category-specific return reduction</div>
      <p className="mt-0.5 text-[11.5px] text-slate">Overrides the general return-rate reduction for chosen categories.</p>
      <ul className="mt-2 flex flex-col gap-3">
        {Object.entries(overrides).map(([cat, v]) => (
          <li key={cat} className="flex items-end gap-2">
            <div className="flex-1">
              <Slider label={cat} value={v} onChange={(nv) => onChange({ ...overrides, [cat]: nv })} min={0} max={0.3} step={0.01} format={(x) => pct(x, 0)} />
            </div>
            <button type="button" aria-label={`Remove override for ${cat}`} className="mb-5 text-slate hover:text-paper" onClick={() => { const n = { ...overrides }; delete n[cat]; onChange(n); }}>
              <X size={14} />
            </button>
          </li>
        ))}
      </ul>
      {unused.length > 0 && (
        <div className="mt-2 flex items-center gap-2">
          <label className="sr-only" htmlFor="ovr-cat">Category to override</label>
          <select id="ovr-cat" value={pick} onChange={(e) => setPick(e.target.value)} className="h-7 flex-1 rounded-[8px] border border-ink-3 bg-ink-2 px-2 text-[12.5px] text-paper">
            <option value="">Choose a category…</option>
            {unused.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <button type="button" className="inline-flex h-7 items-center gap-1 rounded-[8px] border border-ink-3 px-2 text-[12px] text-paper hover:bg-ink-2 disabled:opacity-40" disabled={!pick} onClick={() => { onChange({ ...overrides, [pick]: 0.2 }); setPick(""); }}>
            <Plus size={13} /> Add
          </button>
        </div>
      )}
    </div>
  );
}

function PresetTable({ presets, custom }: { presets: PresetResult[]; custom: WhatIfResponse["result"] }) {
  const cols = [
    { key: "baseline", label: "Baseline", values: { cost: custom.baseline_incremental_costs, gross: 0, retained: 0, spend: 0, net: 0, roi: null as number | null, payback: null as number | null, rate: custom.baseline_unit_return_rate } },
    ...presets.map((p) => ({ key: p.key, label: p.label, values: { cost: p.scenario_incremental_costs, gross: p.gross_cost_savings, retained: p.retained_margin, spend: p.prevention_spend, net: p.net_improvement, roi: p.roi, payback: p.payback_months, rate: p.scenario_unit_return_rate } })),
    { key: "current", label: "Your scenario", values: { cost: custom.scenario_incremental_costs, gross: custom.gross_cost_savings, retained: custom.retained_margin, spend: custom.prevention_spend, net: custom.net_improvement, roi: custom.roi, payback: custom.payback_months, rate: custom.scenario_unit_return_rate } },
  ];
  const rows: { label: string; get: (v: (typeof cols)[number]["values"]) => string }[] = [
    { label: "Incremental return costs", get: (v) => inrCompact(v.cost) },
    { label: "Unit return rate", get: (v) => pct(v.rate) },
    { label: "Gross cost savings", get: (v) => inrCompact(v.gross) },
    { label: "Retained margin", get: (v) => inrCompact(v.retained) },
    { label: "Prevention spending", get: (v) => inrCompact(v.spend) },
    { label: "Net improvement", get: (v) => inrCompact(v.net) },
    { label: "ROI", get: (v) => (v.roi === null ? "—" : `${(v.roi * 100).toFixed(0)}%`) },
    { label: "Payback", get: (v) => (v.payback === null ? "—" : `${v.payback.toFixed(1)} months`) },
  ];
  return (
    <Panel label="Scenario comparison" title="Presets side by side" subtitle="Preset spending scales with the baseline (4%, 10%, 22% of baseline return costs). Projections, not historical results." bodyClass="p-0">
      <div className="overflow-auto">
        <table className="w-full text-[12.5px]">
          <caption className="sr-only">Scenario comparison</caption>
          <thead>
            <tr>
              <th scope="col" className="table-head border-b border-line px-3 py-2">Measure</th>
              {cols.map((c) => <th key={c.key} scope="col" className={`table-head border-b border-line px-3 py-2 text-right ${c.key === "current" ? "!bg-ink !text-paper" : ""}`}>{c.label}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label} className="border-b border-line/70">
                <th scope="row" className="px-3 py-1.5 text-left font-normal text-slate-ink">{row.label}</th>
                {cols.map((c) => <td key={c.key} className={`num px-3 text-right ${c.key === "current" ? "bg-paper font-medium" : ""}`}>{row.get(c.values)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="px-3 py-2 text-[11px] text-slate-ink">Full precision: your scenario net improvement {inr(custom.net_improvement)}.</p>
    </Panel>
  );
}
