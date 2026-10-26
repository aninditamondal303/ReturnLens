/** Application shell: carbon navigation rail + contextual header with global filters. */
import { useState, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { Database, FlaskConical, Gauge, Map as MapIcon, PackageSearch, ShieldAlert, SlidersHorizontal, Waves, X, type LucideIcon } from "lucide-react";
import { useFilters } from "../state/FilterContext";
import { monthLabel, timeLabel, dateLabel } from "../utils/format";
import { SelectField } from "./controls";

export interface PageDef {
  path: string;
  label: string;
  section: string;
  icon: LucideIcon;
  /** short label under the rail icon */
  short: string;
  /** accent colour pair for the page hero tile */
  accent: [string, string];
  /** pages that ignore the global filters (Data Explorer) */
  noFilters?: boolean;
}

export const PAGES: PageDef[] = [
  { path: "/", label: "Executive Overview", short: "Overview", section: "Return operations / executive view", icon: Gauge, accent: ["#D94F36", "#B18A48"] },
  { path: "/risk", label: "Return Risk Analysis", short: "Risk", section: "Risk assessment / historical", icon: ShieldAlert, accent: ["#C2402B", "#E07A4F"] },
  { path: "/leakage", label: "Profit Leakage", short: "Leakage", section: "Financial exposure / reconciliation", icon: Waves, accent: ["#287C72", "#4FA394"] },
  { path: "/products", label: "Product Intelligence", short: "Products", section: "Assortment / product investigation", icon: PackageSearch, accent: ["#86672F", "#C9A35E"] },
  { path: "/geography", label: "Customer & Geography", short: "Regions", section: "Regions / customer segments", icon: MapIcon, accent: ["#2F6F8F", "#4FA394"] },
  { path: "/simulator", label: "What-If Simulator", short: "What-if", section: "Scenario lab / hypothetical", icon: FlaskConical, accent: ["#6B4FA0", "#B07AC9"] },
  { path: "/data", label: "Data Explorer", short: "Data", section: "Data laboratory / quality", icon: Database, accent: ["#3A3F3D", "#777D79"] },
];

function NavRail() {
  return (
    <nav
      aria-label="Main"
      className="fixed inset-y-0 left-0 z-40 flex w-[78px] flex-col items-center py-4 max-md:inset-y-auto max-md:bottom-0 max-md:h-16 max-md:w-full max-md:flex-row max-md:justify-around max-md:py-0"
      style={{
        background:
          "radial-gradient(rgba(245,243,237,0.06) 1px, transparent 1.2px) 0 0 / 14px 14px, radial-gradient(180px 260px at 50% 0%, rgba(217,79,54,0.28), transparent 70%), radial-gradient(200px 300px at 50% 100%, rgba(40,124,114,0.35), transparent 70%), linear-gradient(180deg, #171a19, #1b2422 60%, #1d2d2a)",
      }}
    >
      <div
        className="mb-6 flex h-11 w-11 items-center justify-center rounded-[13px] font-mono text-[15px] font-semibold text-white max-md:hidden"
        style={{ background: "linear-gradient(135deg, #D94F36, #B18A48)", boxShadow: "0 8px 20px -6px rgba(217,79,54,0.7)" }}
        title="ShopSphere Return Intelligence Lab"
      >
        S<span className="text-ink/70">/</span>
      </div>
      <ul className="flex flex-col gap-1.5 max-md:flex-row max-md:gap-0">
        {PAGES.map((p) => (
          <li key={p.path}>
            <NavLink
              to={p.path}
              end={p.path === "/"}
              aria-label={p.label}
              className={({ isActive }) =>
                `group relative flex h-[54px] w-[62px] flex-col items-center justify-center gap-1 rounded-[12px] transition-all duration-200 max-md:h-14 max-md:w-12 ${
                  isActive ? "bg-white/10 text-white shadow-[inset_0_0_0_1px_rgba(255,255,255,0.08)]" : "text-[#9aa09c] hover:bg-white/5 hover:text-white"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span
                      className="absolute -left-2 top-3 h-7 w-[4px] rounded-full max-md:left-3 max-md:top-auto max-md:-bottom-1 max-md:h-[4px] max-md:w-6"
                      style={{ background: `linear-gradient(180deg, ${p.accent[0]}, ${p.accent[1]})`, boxShadow: `0 0 12px ${p.accent[0]}` }}
                      aria-hidden
                    />
                  )}
                  <span
                    className={`flex h-7 w-7 items-center justify-center rounded-[8px] transition-all duration-200 ${isActive ? "text-white" : ""}`}
                    style={isActive ? { background: `linear-gradient(135deg, ${p.accent[0]}, ${p.accent[1]})`, boxShadow: `0 6px 14px -6px ${p.accent[0]}` } : undefined}
                  >
                    <p.icon size={17} strokeWidth={1.8} aria-hidden />
                  </span>
                  <span className="text-[9.5px] font-medium leading-none tracking-wide max-md:hidden">{p.short}</span>
                  <span className="pointer-events-none absolute left-[70px] z-50 hidden whitespace-nowrap rounded-[8px] bg-ink px-2.5 py-1.5 text-[12px] text-paper shadow-lg ring-1 ring-ink-3 group-hover:block group-focus-visible:block max-md:hidden">
                    {p.label}
                  </span>
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
      <div
        className="mt-auto rounded-[8px] border border-white/10 px-1.5 py-1 text-center font-mono text-[8.5px] leading-tight text-[#c9a35e] max-md:hidden"
        title="All data is synthetic"
      >
        SYN
        <br />
        DATA
      </div>
    </nav>
  );
}

const PRESETS = [
  { value: "all", label: "Full 12 months" },
  { value: "q4", label: "Last quarter" },
  { value: "h2", label: "Last 6 months" },
  { value: "h1", label: "First 6 months" },
  { value: "festive", label: "Festive quarter (first 3 months)" },
  { value: "custom", label: "Custom range" },
];

function FilterBar({ page }: { page: PageDef }) {
  const { filters, setFilters, resetFilters, metadata, activeCount } = useFilters();
  const months = metadata?.months ?? [];
  const [showMobile, setShowMobile] = useState(false);
  if (page.noFilters) return null;

  const start = filters.startMonth ?? months[0];
  const end = filters.endMonth ?? months[months.length - 1];
  const preset = (() => {
    if (!filters.startMonth && !filters.endMonth) return "all";
    const n = months.length;
    if (start === months[n - 3] && end === months[n - 1]) return "q4";
    if (start === months[n - 6] && end === months[n - 1]) return "h2";
    if (start === months[0] && end === months[5]) return "h1";
    if (start === months[0] && end === months[2]) return "festive";
    return "custom";
  })();
  const applyPreset = (v: string) => {
    const n = months.length;
    if (!n) return;
    if (v === "all") setFilters({ startMonth: null, endMonth: null });
    if (v === "q4") setFilters({ startMonth: months[n - 3], endMonth: months[n - 1] });
    if (v === "h2") setFilters({ startMonth: months[n - 6], endMonth: months[n - 1] });
    if (v === "h1") setFilters({ startMonth: months[0], endMonth: months[5] });
    if (v === "festive") setFilters({ startMonth: months[0], endMonth: months[2] });
    if (v === "custom") setFilters({ startMonth: start, endMonth: end });
  };
  const monthOpts = months.map((m) => ({ value: m, label: monthLabel(m, true) }));

  const chips: { label: string; clear: () => void }[] = [];
  if (filters.startMonth || filters.endMonth)
    chips.push({ label: `${monthLabel(start)} – ${monthLabel(end)}`, clear: () => setFilters({ startMonth: null, endMonth: null }) });
  if (filters.category) chips.push({ label: filters.category, clear: () => setFilters({ category: "" }) });
  if (filters.region) chips.push({ label: filters.region, clear: () => setFilters({ region: "" }) });
  if (filters.channel) chips.push({ label: filters.channel, clear: () => setFilters({ channel: "" }) });

  return (
    <div className="px-5 pb-3">
      <button type="button" className="btn md:hidden" onClick={() => setShowMobile((s) => !s)} aria-expanded={showMobile}>
        <SlidersHorizontal size={14} /> Filters {activeCount > 0 && `(${activeCount})`}
      </button>
      <div
        className={`${showMobile ? "flex" : "hidden"} flex-wrap items-end gap-x-3 gap-y-2 rounded-[14px] border border-line bg-white/80 px-3.5 py-2.5 shadow-[0_6px_20px_-14px_rgba(23,26,25,0.35)] backdrop-blur md:flex`}
      >
        <div className="mr-1 flex items-center gap-1.5 self-center pt-3 text-[11px] font-semibold uppercase tracking-wider text-teal max-lg:hidden">
          <SlidersHorizontal size={14} aria-hidden /> Filters
        </div>
        <SelectField label="Reporting period" value={preset} onChange={applyPreset} options={PRESETS} className="w-[190px]" />
        {preset === "custom" && (
          <>
            <SelectField
              label="From"
              value={start ?? ""}
              onChange={(v) => setFilters({ startMonth: v, endMonth: end && v > end ? v : end })}
              options={monthOpts}
              className="w-[120px]"
            />
            <SelectField
              label="To"
              value={end ?? ""}
              onChange={(v) => setFilters({ endMonth: v, startMonth: start && v < start ? v : start })}
              options={monthOpts}
              className="w-[120px]"
            />
          </>
        )}
        <SelectField label="Category" value={filters.category} onChange={(v) => setFilters({ category: v })} options={metadata?.categories ?? []} allLabel="All categories" className="w-[200px]" />
        <SelectField label="Region" value={filters.region} onChange={(v) => setFilters({ region: v })} options={metadata?.regions ?? []} allLabel="All regions" className="w-[160px]" />
        <SelectField label="Sales channel" value={filters.channel} onChange={(v) => setFilters({ channel: v })} options={metadata?.channels ?? []} allLabel="All channels" className="w-[160px]" />
        <button type="button" className="btn" onClick={resetFilters} disabled={activeCount === 0}>
          Reset filters
        </button>
        {chips.length > 0 && (
          <ul className="flex flex-wrap items-center gap-1.5" aria-label="Active filters">
            {chips.map((c) => (
              <li key={c.label}>
                <button
                  type="button"
                  onClick={c.clear}
                  className="inline-flex h-6 items-center gap-1 rounded-full px-2.5 text-[11.5px] text-white shadow-sm transition-opacity hover:opacity-85"
                  style={{ background: "linear-gradient(135deg, #287C72, #4FA394)" }}
                  aria-label={`Remove filter ${c.label}`}
                >
                  {c.label} <X size={11} aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function Header({ page, actions }: { page: PageDef; actions?: ReactNode }) {
  const { metadata, metadataError, periodLabel } = useFilters();
  const Icon = page.icon;
  return (
    <header className="sticky top-0 z-30 border-b border-line/70 bg-paper/85 backdrop-blur-md">
      <div className="relative overflow-hidden">
        <HeaderOrnament color={page.accent[0]} />
        <div className="relative flex flex-wrap items-center justify-between gap-x-6 gap-y-2 px-5 pt-3.5 pb-3">
          <div className="flex min-w-0 items-center gap-3">
            <span
              className="icon-tile h-11 w-11"
              style={{ background: `linear-gradient(135deg, ${page.accent[0]}, ${page.accent[1]})`, color: page.accent[0] }}
            >
              <Icon size={21} strokeWidth={1.8} className="text-white" aria-hidden />
            </span>
            <div className="min-w-0">
              <div className="section-label no-marker">{page.section}</div>
              <h1 className="mt-0.5 text-[22px] font-bold leading-tight tracking-[-0.015em]">{page.label}</h1>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-[12px] text-slate-ink">
            {!page.noFilters && <MetaPill label="Period" value={periodLabel || "—"} />}
            <MetaPill label="Snapshot" value={dateLabel(metadata?.snapshot_date)} title="Date of the data extract; returns after this date are not yet known" />
            <MetaPill label="Loaded" value={timeLabel(metadata?.loaded_at)} title="When the API last loaded the CSV files" />
            <span className="rounded-full border border-brass/60 bg-brass-wash px-2.5 py-[3px] font-mono text-[10px] uppercase tracking-wide text-brass-ink">
              Synthetic data
            </span>
            {actions}
          </div>
        </div>
      </div>
      {metadataError && (
        <div role="alert" className="mx-5 mb-2 rounded-[10px] border border-vermilion/30 bg-vermilion-wash px-3 py-1.5 text-[12px] text-vermilion-ink">
          Filters unavailable: {metadataError}
        </div>
      )}
      <FilterBar page={page} />
    </header>
  );
}

function MetaPill({ label, value, title }: { label: string; value: string; title?: string }) {
  return (
    <span title={title} className="inline-flex items-center gap-1.5 rounded-full border border-line bg-white/80 px-2.5 py-[3px] shadow-[0_1px_2px_rgba(23,26,25,0.05)]">
      <span className="font-mono text-[9.5px] uppercase tracking-wider text-slate-ink">{label}</span>
      <span className="num text-[11.5px] text-ink">{value}</span>
    </span>
  );
}

/** Decorative contour lines behind the page title, tinted with the page accent. */
function HeaderOrnament({ color }: { color: string }) {
  return (
    <svg className="pointer-events-none absolute -right-10 -top-6 h-[140px] w-[620px] max-md:hidden" viewBox="0 0 620 140" aria-hidden>
      <defs>
        <linearGradient id="orn" x1="0" x2="1">
          <stop offset="0" stopColor={color} stopOpacity="0" />
          <stop offset="1" stopColor={color} stopOpacity="0.35" />
        </linearGradient>
      </defs>
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <path
          key={i}
          d={`M0 ${70 + i * 9} C 140 ${20 + i * 14}, 260 ${120 - i * 6}, 400 ${60 + i * 8} S 560 ${30 + i * 12}, 640 ${50 + i * 10}`}
          fill="none"
          stroke="url(#orn)"
          strokeWidth={1.2}
        />
      ))}
      <circle cx="560" cy="42" r="26" fill={color} opacity="0.07" />
      <circle cx="600" cy="90" r="12" fill={color} opacity="0.1" />
    </svg>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const page = PAGES.find((p) => (p.path === "/" ? pathname === "/" : pathname.startsWith(p.path))) ?? PAGES[0];
  return (
    <div className="min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-24 focus:top-2 focus:z-50 focus:bg-white focus:px-3 focus:py-2">
        Skip to content
      </a>
      <NavRail />
      <div className="pl-[78px] max-md:pb-16 max-md:pl-0">
        <Header page={page} />
        <main id="main" key={page.path} className="page-enter mx-auto max-w-[1600px] px-5 py-5">
          {children}
        </main>
        <footer className="mx-auto flex max-w-[1600px] items-center gap-2 px-5 pb-6 text-[11.5px] text-slate-ink">
          <span className="h-px flex-1 bg-gradient-to-r from-transparent via-line-dark to-transparent" aria-hidden />
          <span>ShopSphere is a fictional company. Every order, return, customer and product is synthetic; all results are illustrative.</span>
          <span className="h-px flex-1 bg-gradient-to-r from-transparent via-line-dark to-transparent" aria-hidden />
        </footer>
      </div>
    </div>
  );
}
