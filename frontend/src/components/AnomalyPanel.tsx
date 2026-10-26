/** Explainable anomaly flags with user-adjustable sensitivity (all computed by the API). */
import { useState } from "react";
import { api } from "../services/api";
import { useApi, useDebounced } from "../hooks/useApi";
import { useFilters } from "../state/FilterContext";
import type { AnomalyFlag, AnomalyResponse } from "../types/api";
import { inr, int, monthLabel, pct } from "../utils/format";
import { DataTable, type Column } from "./DataTable";
import { ErrorState, Notice, Panel } from "./ui";

export function AnomalyPanel() {
  const { query, queryKey } = useFilters();
  const [minUnits, setMinUnits] = useState(120);
  const [z, setZ] = useState(2.5);
  const dMin = useDebounced(minUnits, 300);
  const dZ = useDebounced(z, 300);
  const { data, error, loading, refreshing, reload } = useApi<AnomalyResponse>(
    (s) => api.anomalies({ ...query, min_units: dMin, z_threshold: dZ }, { signal: s }),
    `${queryKey}|${dMin}|${dZ}`,
  );
  const fmt = (f: AnomalyFlag, v: number | null) => (f.unit === "percent" ? pct(v) : inr(v));
  const columns: Column<AnomalyFlag>[] = [
    { key: "month", header: "Month", render: (f) => <span className="num">{monthLabel(f.month)}</span> },
    { key: "dimension", header: "Group", render: (f) => <span><span className="text-slate-ink">{f.dimension}:</span> <span className="font-medium">{f.member}</span></span> },
    { key: "metric", header: "Metric" },
    { key: "observed", header: "Observed", align: "right", render: (f) => <span className="text-vermilion-ink">{fmt(f, f.observed)}</span> },
    { key: "baseline", header: "Baseline", align: "right", render: (f) => fmt(f, f.baseline) },
    { key: "lift", header: "Lift", align: "right", render: (f) => `${((f.lift ?? 1) - 1) * 100 > 0 ? "+" : ""}${(((f.lift ?? 1) - 1) * 100).toFixed(0)}%` },
    { key: "z_score", header: "z", align: "right", render: (f) => (f.z_score === null ? "—" : f.z_score.toFixed(1)) },
    { key: "reason", header: "Why flagged", render: (f) => <span className="whitespace-normal text-[11.5px] text-slate-ink">{f.reason}</span> },
  ];
  return (
    <Panel
      label="Anomaly watch / monthly"
      title="Unusual changes in return rates and return costs"
      subtitle="Each month is compared with the pooled previous three months for the same category, supplier or region."
      bodyClass="p-0"
    >
      <div className="flex flex-wrap items-end gap-5 border-b border-line px-4 py-2.5 text-[12.5px]">
        <label className="flex flex-col gap-0.5">
          <span className="section-label">Minimum units per month</span>
          <input type="number" min={10} max={5000} step={10} value={minUnits} onChange={(e) => setMinUnits(Math.max(10, Number(e.target.value) || 10))} className="field w-28 num" />
        </label>
        <label className="flex flex-col gap-0.5">
          <span className="section-label">Significance (z)</span>
          <select value={z} onChange={(e) => setZ(Number(e.target.value))} className="field w-28">
            {[2, 2.5, 3, 3.5].map((v) => <option key={v} value={v}>{v.toFixed(1)}</option>)}
          </select>
        </label>
        {data && (
          <span className="pb-1.5 text-slate-ink">
            <span className="num text-ink">{int(data.flags.length)}</span> flags from <span className="num text-ink">{int(data.tests_run)}</span> tests ·{" "}
            <span className="num text-ink">{int(data.skipped_insufficient_volume)}</span> group-months skipped for low volume
          </span>
        )}
        {refreshing && <span className="pb-1.5 text-slate-ink">Updating…</span>}
      </div>
      {error && <div className="p-3"><ErrorState error={error} onRetry={reload} /></div>}
      {loading && <div className="p-6 text-[12.5px] text-slate-ink">Running tests…</div>}
      {data && data.flags.length === 0 && <p className="px-4 py-6 text-[12.5px] text-slate-ink">No month crosses the thresholds for this selection.</p>}
      {data && data.flags.length > 0 && <DataTable caption="Anomaly flags" rows={data.flags} columns={columns} rowKey={(f) => `${f.dimension}|${f.member}|${f.month}|${f.metric}`} dense maxHeight={380} />}
      <div className="p-3">
        <Notice>
          {data?.disclaimer ?? "Statistical signals for investigation."} Lower thresholds find more flags, including chance fluctuations: with hundreds of monthly tests a few flags are expected even without a real change.
        </Notice>
      </div>
    </Panel>
  );
}
