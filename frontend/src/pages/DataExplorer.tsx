import { useEffect, useState } from "react";
import { CircleCheck, Download, RefreshCw, TriangleAlert, CircleX } from "lucide-react";
import { api } from "../services/api";
import { useApi, useDebounced } from "../hooks/useApi";
import { useFilters } from "../state/FilterContext";
import type { DataQualityResponse, DatasetProfile, MetricDefinition, QualityCheck } from "../types/api";
import { ErrorState, KindBadge, Panel, PanelSkeleton } from "../components/ui";
import { DataTable, Pagination, type Column, type SortState } from "../components/DataTable";
import { Segmented, SearchInput } from "../components/controls";
import { int, timeLabel } from "../utils/format";

type Tab = "orders" | "returns" | "products" | "customers" | "metrics";

export default function DataExplorer() {
  const { reloadMetadata } = useFilters();
  const { data, error, loading, reload } = useApi<DataQualityResponse>((s) => api.dataQuality({ signal: s }), "quality");
  const [tab, setTab] = useState<Tab>("orders");
  const [reloadState, setReloadState] = useState<{ busy: boolean; msg: string | null; ok: boolean }>({ busy: false, msg: null, ok: true });

  const doReload = async () => {
    setReloadState({ busy: true, msg: null, ok: true });
    try {
      const r = await api.reload();
      setReloadState({ busy: false, msg: r.message + (r.reloaded ? ` Loaded ${timeLabel(r.loaded_at)}.` : ""), ok: r.reloaded });
      if (r.reloaded) {
        reload();
        reloadMetadata();
      }
    } catch (e) {
      setReloadState({ busy: false, msg: `Reload request failed: ${(e as Error).message}`, ok: false });
    }
  };

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading || !data) return <PanelSkeleton label="data quality" height={300} />;
  const v = data.validation;
  const info = data.dataset_info as {
    seed?: number;
    snapshot_date?: string;
    period_start?: string;
    period_end?: string;
    injected_anomalies?: string[];
    description?: string;
    generated_with?: { python?: string; numpy?: string; pandas?: string };
  };

  return (
    <div className="flex flex-col gap-4">
      <section className="grid grid-cols-1 gap-px overflow-hidden rounded-[14px] border border-line bg-line shadow-[0_8px_24px_-12px_rgba(23,26,25,0.18)] lg:grid-cols-[2fr_3fr]">
        <div className="flex flex-col gap-3 bg-ink p-5 text-paper">
          <div className="section-label !text-slate">Validation status</div>
          <div className="flex items-center gap-3">
            {v?.passed ? <CircleCheck size={28} className="text-[#7fcabd]" aria-hidden /> : <CircleX size={28} className="text-[#f08a73]" aria-hidden />}
            <div>
              <div className="text-[18px] font-semibold">{v?.passed ? "All integrity checks passed" : "Integrity issues found"}</div>
              <div className="num text-[12.5px] text-slate">
                {int(v?.summary.passed)} / {int(v?.summary.total_checks)} checks · {int(v?.summary.errors)} errors · {int(v?.summary.warnings)} warnings
              </div>
            </div>
          </div>
          <div className="text-[12px] text-slate">
            Loaded <span className="num text-paper">{timeLabel(data.status.loaded_at)}</span> from <span className="num text-paper">{data.status.data_dir}/</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className="inline-flex h-8 items-center gap-1.5 rounded-[8px] bg-paper px-3 text-[13px] font-medium text-ink hover:bg-white disabled:opacity-50" onClick={doReload} disabled={reloadState.busy}>
              <RefreshCw size={14} className={reloadState.busy ? "animate-spin" : ""} /> {reloadState.busy ? "Reloading…" : "Reload CSV files from disk"}
            </button>
          </div>
          {reloadState.msg && (
            <p role="status" className={`text-[12px] ${reloadState.ok ? "text-[#7fcabd]" : "text-[#f08a73]"}`}>{reloadState.msg}</p>
          )}
        </div>
        <div className="bg-white p-5">
          <div className="section-label">Dataset</div>
          <p className="mt-1 text-[13px]">{info.description ?? "Synthetic dataset."}</p>
          <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-[12.5px] sm:grid-cols-4">
            <div>
              <dt className="text-slate-ink">Random seed</dt>
              <dd className="num">{info.seed ?? "—"}</dd>
              {info.generated_with && (
                <dd className="num text-[11px] text-slate-ink" title="Identical output is guaranteed for the same seed and library versions">
                  numpy {info.generated_with.numpy} · pandas {info.generated_with.pandas}
                </dd>
              )}
            </div>
            <div><dt className="text-slate-ink">Order period</dt><dd className="num">{info.period_start} → {info.period_end}</dd></div>
            <div><dt className="text-slate-ink">Snapshot date</dt><dd className="num">{data.snapshot_date}</dd></div>
            <div><dt className="text-slate-ink">Rows</dt><dd className="num">{Object.entries(data.status.rows).map(([k, n]) => `${k} ${int(n)}`).join(" · ")}</dd></div>
          </dl>
          {info.injected_anomalies && (
            <div className="mt-3 text-[12px]">
              <div className="text-slate-ink">Documented patterns injected for the anomaly detector to find:</div>
              <ul className="mt-1 list-disc pl-4">{info.injected_anomalies.map((a) => <li key={a}>{a}</li>)}</ul>
            </div>
          )}
        </div>
      </section>

      <Segmented
        label="Dataset"
        value={tab}
        onChange={setTab}
        options={[
          { value: "orders", label: "Orders" },
          { value: "returns", label: "Returns" },
          { value: "products", label: "Products" },
          { value: "customers", label: "Customers" },
          { value: "metrics", label: "Metric dictionary" },
        ]}
      />
      {tab === "metrics" ? (
        <MetricDictionary />
      ) : (
        <DatasetView key={tab} name={tab} profile={data.profiles.find((p) => p.name === tab)!} dictionary={data.dictionary[tab] ?? {}} />
      )}

      {v && <ChecksTable checks={v.checks} />}
    </div>
  );
}

function DatasetView({ name, profile, dictionary }: { name: string; profile: DatasetProfile; dictionary: Record<string, string> }) {
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
      <Panel
        className="xl:col-span-5"
        label={`${name}.csv / profile`}
        title={`${int(profile.rows)} rows · ${profile.columns.length} columns`}
        subtitle={`Duplicate rows ${int(profile.duplicate_rows)} · duplicate keys ${int(profile.duplicate_keys)}`}
        bodyClass="p-0"
        actions={<a className="btn h-7" href={api.datasetDownloadUrl(name)} download><Download size={13} /> Source CSV</a>}
      >
        {Object.keys(profile.date_coverage).length > 0 && (
          <div className="flex flex-wrap gap-x-5 gap-y-1 border-b border-line px-4 py-2 text-[12px]">
            {Object.entries(profile.date_coverage).map(([col, c]) => (
              <span key={col}><span className="text-slate-ink">{col}</span> <span className="num">{c.min} → {c.max}</span></span>
            ))}
          </div>
        )}
        <div className="max-h-[520px] overflow-auto">
          <table className="w-full text-[12px]">
            <caption className="sr-only">Column profile and data dictionary for {name}</caption>
            <thead><tr>{["Column", "Type", "Missing", "Distinct", "Description"].map((h, i) => <th key={h} scope="col" className={`table-head border-b border-line px-3 py-2 ${i === 2 || i === 3 ? "text-right" : ""}`}>{h}</th>)}</tr></thead>
            <tbody>
              {profile.columns.map((c) => (
                <tr key={c.name} className="border-b border-line/70 align-top">
                  <td className="num whitespace-nowrap px-3 py-1.5">{c.name}</td>
                  <td className="whitespace-nowrap px-3 py-1.5 text-slate-ink">{c.dtype}</td>
                  <td className="num px-3 py-1.5 text-right" title={c.missing_note || undefined}>
                    {c.missing === 0 ? "0" : <span className={c.missing_note ? "text-brass-ink" : "text-vermilion-ink"}>{int(c.missing)}{c.missing_note ? "*" : ""}</span>}
                  </td>
                  <td className="num px-3 py-1.5 text-right">{int(c.distinct)}</td>
                  <td className="px-3 py-1.5 text-slate-ink">{dictionary[c.name] ?? ""}{c.missing_note && <div className="text-brass-ink">* {c.missing_note}</div>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <Preview name={name} />
    </div>
  );
}

function Preview({ name }: { name: string }) {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortState | undefined>(undefined);
  const [page, setPage] = useState(1);
  const debounced = useDebounced(search);
  useEffect(() => setPage(1), [debounced, sort?.by, sort?.dir]);
  const { data, error, loading, refreshing, reload } = useApi(
    (s) => api.dataset(name, { search: debounced || undefined, sort_by: sort?.by, sort_dir: sort?.dir, page, page_size: 20 }, { signal: s }),
    `${name}|${debounced}|${sort?.by}|${sort?.dir}|${page}`,
  );
  const columns: Column<Record<string, string>>[] = (data?.columns ?? []).map((c) => ({
    key: c,
    header: c,
    sortable: true,
    render: (r: Record<string, string>) => <span className={/_(id|date)$/.test(c) || /^[\d.]+$/.test(r[c] ?? "") ? "num text-[11.5px]" : ""}>{r[c] === "" ? <span className="text-slate">∅</span> : r[c]}</span>,
  }));
  return (
    <Panel className="xl:col-span-7" label={`${name}.csv / preview`} title="Raw records" subtitle="Server-side search across all columns; sorting is numeric where the column is numeric." bodyClass="p-0">
      <div className="flex items-center gap-3 border-b border-line px-4 py-2.5">
        <SearchInput value={search} onChange={setSearch} placeholder={`Search ${name}`} label={`Search ${name}`} className="w-[260px]" />
        {refreshing && <span className="text-[11.5px] text-slate-ink">Updating…</span>}
      </div>
      {error && <div className="p-3"><ErrorState error={error} onRetry={reload} /></div>}
      {loading && <div className="p-6 text-[12.5px] text-slate-ink">Loading records…</div>}
      {data && (
        <>
          <DataTable caption={`${name} preview`} rows={data.rows} columns={columns} rowKey={(r) => Object.values(r).slice(0, 2).join("|")} sort={sort} onSort={setSort} dense maxHeight={520} />
          <Pagination page={data.page} totalPages={data.total_pages} totalRows={data.total_rows} pageSize={data.page_size} onPage={setPage} label="rows" />
        </>
      )}
    </Panel>
  );
}

function ChecksTable({ checks }: { checks: QualityCheck[] }) {
  const columns: Column<QualityCheck>[] = [
    {
      key: "passed",
      header: "Result",
      render: (c) =>
        c.passed ? (
          <span className="inline-flex items-center gap-1 text-teal"><CircleCheck size={13} aria-hidden /> Pass</span>
        ) : c.severity === "warning" ? (
          <span className="inline-flex items-center gap-1 text-brass-ink"><TriangleAlert size={13} aria-hidden /> Warning</span>
        ) : (
          <span className="inline-flex items-center gap-1 text-vermilion-ink"><CircleX size={13} aria-hidden /> Fail</span>
        ),
    },
    { key: "name", header: "Check", render: (c) => <span className="font-medium">{c.name}</span> },
    { key: "detail", header: "Detail", render: (c) => <span className="text-slate-ink">{c.detail}</span> },
    { key: "affected_rows", header: "Rows", align: "right", render: (c) => int(c.affected_rows) },
    { key: "impact", header: "Why it matters", render: (c) => <span className="whitespace-normal text-[11.5px] text-slate-ink">{c.impact}</span> },
  ];
  return (
    <Panel label="Validation results" title="Integrity and business-rule checks" subtitle="Run by the API on every load. Issues are reported, never silently corrected." bodyClass="p-0">
      <DataTable caption="Validation checks" rows={checks} columns={columns} rowKey={(c) => c.name} dense maxHeight={460} />
    </Panel>
  );
}

function MetricDictionary() {
  const { data, error, loading, reload } = useApi<MetricDefinition[]>((s) => api.metricsDictionary({ signal: s }), "dictionary");
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading || !data) return <PanelSkeleton label="metric dictionary" />;
  return (
    <Panel label="Metric dictionary" title="Every KPI, its formula and its source" subtitle="Served by /api/metrics-dictionary — the same definitions the engine, tests and Power BI guide use." bodyClass="p-0">
      <div className="max-h-[620px] overflow-auto">
        <table className="w-full text-[12.5px]">
          <caption className="sr-only">Metric dictionary</caption>
          <thead><tr>{["Metric", "Kind", "Formula", "Definition", "Unit", "Grain", "Source"].map((h) => <th key={h} scope="col" className="table-head border-b border-line px-3 py-2">{h}</th>)}</tr></thead>
          <tbody>
            {data.map((m) => (
              <tr key={m.key} className="border-b border-line/70 align-top">
                <td className="px-3 py-2 font-medium">{m.name}</td>
                <td className="px-3 py-2"><KindBadge kind={m.kind} /></td>
                <td className="num px-3 py-2 text-[11.5px]">{m.formula}</td>
                <td className="px-3 py-2 text-slate-ink">{m.definition}</td>
                <td className="px-3 py-2 text-slate-ink">{m.unit}</td>
                <td className="px-3 py-2 text-slate-ink">{m.grain}</td>
                <td className="num px-3 py-2 text-[11.5px] text-slate-ink">{m.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
