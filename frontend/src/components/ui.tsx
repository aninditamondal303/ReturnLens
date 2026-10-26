/** Small presentational primitives shared across pages. */
import { useId, useState, type ReactNode } from "react";
import { TriangleAlert, ArrowDownRight, ArrowUpRight, Info, Minus, RotateCcw, SearchX } from "lucide-react";
import type { Num } from "../types/api";
import { pct, pts, signedPct } from "../utils/format";

/* ------------------------------------------------------------------ Panel */
export function Panel({
  label,
  title,
  subtitle,
  actions,
  children,
  className = "",
  bodyClass = "p-4",
  dark = false,
}: {
  label?: string;
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClass?: string;
  dark?: boolean;
}) {
  return (
    <section className={`${dark ? "panel-dark" : "panel"} flex flex-col min-w-0 ${className}`}>
      {(label || title || actions) && (
        <header
          className={`flex items-start justify-between gap-3 px-4 pt-3 pb-2.5 border-b ${dark ? "border-ink-3" : "border-line"}`}
        >
          <div className="min-w-0">
            {label && <div className={`section-label ${dark ? "!text-slate" : ""}`}>{label}</div>}
            {title && <h2 className="mt-1 text-[15.5px] font-bold leading-snug tracking-[-0.01em]">{title}</h2>}
            {subtitle && (
              <p className={`mt-0.5 text-[12.5px] leading-snug ${dark ? "text-slate" : "text-slate-ink"}`}>{subtitle}</p>
            )}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={`min-w-0 flex-1 ${bodyClass}`}>{children}</div>
    </section>
  );
}

/* ------------------------------------------------------------------ InfoTip */
export function InfoTip({ text, label = "Definition", dark = false }: { text: ReactNode; label?: string; dark?: boolean }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span className="relative inline-flex">
      <button
        type="button"
        aria-label={label}
        aria-describedby={open ? id : undefined}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className={`inline-flex h-4 w-4 items-center justify-center rounded-full ${dark ? "text-slate hover:text-paper" : "text-slate hover:text-ink"}`}
      >
        <Info size={12} strokeWidth={2} />
      </button>
      {open && (
        <span
          role="tooltip"
          id={id}
          className="absolute left-1/2 top-5 z-30 w-64 -translate-x-1/2 rounded-[10px] border border-ink-3 bg-ink px-3 py-2 shadow-xl text-left text-[12px] font-normal normal-case leading-snug tracking-normal text-paper"
        >
          {text}
        </span>
      )}
    </span>
  );
}

/* ------------------------------------------------------------------ Badges */
const KIND_STYLE: Record<string, string> = {
  actual: "border-line-dark text-slate-ink",
  derived: "border-line-dark text-slate-ink",
  estimated: "border-brass text-brass-ink",
};
export function KindBadge({ kind, dark = false }: { kind: string; dark?: boolean }) {
  return (
    <span
      title={
        kind === "estimated"
          ? "Depends on modelling assumptions"
          : kind === "derived"
            ? "Calculated from recorded values"
            : "Sum of recorded transactions"
      }
      className={`inline-flex h-[18px] items-center rounded-full border px-1.5 font-mono text-[9.5px] uppercase tracking-wide ${
        dark ? (kind === "estimated" ? "border-brass text-brass" : "border-ink-3 text-slate") : KIND_STYLE[kind] ?? KIND_STYLE.actual
      }`}
    >
      {kind}
    </span>
  );
}

export function RiskBadge({ band }: { band: string | null | undefined }) {
  const b = band ?? "—";
  const style =
    b === "High"
      ? "bg-gradient-to-r from-vermilion to-[#E07A4F] text-white shadow-[0_3px_8px_-3px_rgba(217,79,54,0.8)]"
      : b === "Medium" || b === "Elevated"
        ? "bg-brass-wash text-brass-ink ring-1 ring-brass/40"
        : b === "Low" || b === "Normal"
          ? "bg-teal-wash text-teal ring-1 ring-teal/25"
          : "bg-paper-2 text-slate-ink";
  const marker = b === "High" ? "▲" : b === "Medium" || b === "Elevated" ? "◆" : "●";
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-[1px] text-[11px] font-semibold ${style}`}>
      <span aria-hidden className="text-[8px]">
        {marker}
      </span>
      {b}
    </span>
  );
}

const STATUS_STYLE: Record<string, string> = {
  Returned: "text-vermilion-ink",
  "Return in progress": "text-brass-ink",
  "Return rejected": "text-slate-ink",
  "Window open": "text-brass-ink",
  "Not returned": "text-teal",
  Cancelled: "text-slate-ink",
};
export function StatusText({ status }: { status: string }) {
  return <span className={`text-[12px] font-medium ${STATUS_STYLE[status] ?? "text-ink"}`}>{status}</span>;
}

/* ------------------------------------------------------------------ Delta */
export function Delta({
  change,
  type,
  good,
  dark = false,
}: {
  change: Num;
  type: "points" | "relative";
  good: "up" | "down";
  dark?: boolean;
}) {
  if (change === null || change === undefined) return null;
  const flat = Math.abs(change) < 0.0005;
  const up = change > 0;
  const favourable = flat ? null : up === (good === "up");
  const color = favourable === null ? (dark ? "text-slate" : "text-slate-ink") : favourable ? (dark ? "text-[#5fb8ab]" : "text-teal") : dark ? "text-[#f08a73]" : "text-vermilion-ink";
  const Icon = flat ? Minus : up ? ArrowUpRight : ArrowDownRight;
  return (
    <span className={`inline-flex items-center gap-0.5 font-mono text-[11.5px] ${color}`}>
      <Icon size={12} aria-hidden />
      {type === "points" ? pts(change) : signedPct(change)}
      <span className="sr-only">{favourable === null ? "no change" : favourable ? "(favourable)" : "(unfavourable)"}</span>
    </span>
  );
}

/* ------------------------------------------------------------------ States */
export function Skeleton({ className = "h-4 w-full" }: { className?: string }) {
  return <div className={`skeleton rounded-[6px] ${className}`} aria-hidden />;
}

export function PanelSkeleton({ height = 260, label }: { height?: number; label?: string }) {
  return (
    <div className="panel p-4" aria-busy="true" aria-label={label ? `Loading ${label}` : "Loading"}>
      <Skeleton className="h-3 w-40" />
      <Skeleton className="mt-2 h-4 w-64" />
      <Skeleton className="mt-4 w-full" />
      <div style={{ height: height - 80 }} className="mt-3 flex items-end gap-2">
        {[40, 65, 50, 80, 55, 70, 45, 60].map((h, i) => (
          <div key={i} className="skeleton flex-1 rounded-t-[6px]" style={{ height: `${h}%` }} />
        ))}
      </div>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: Error | string; onRetry?: () => void }) {
  const msg = typeof error === "string" ? error : error.message;
  return (
    <div role="alert" className="panel flex items-start gap-3 border-vermilion/40 p-4">
      <TriangleAlert className="mt-0.5 shrink-0 text-vermilion" size={18} aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="text-[13.5px] font-semibold">The analytics service did not return data</div>
        <p className="mt-0.5 text-[12.5px] text-slate-ink">{msg}</p>
        <p className="mt-1 text-[12px] text-slate-ink">No figures are shown until real data loads — nothing on this page is estimated from cached or demo values.</p>
      </div>
      {onRetry && (
        <button type="button" className="btn shrink-0" onClick={onRetry}>
          <RotateCcw size={13} /> Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title = "No records match these filters", hint, onReset }: { title?: string; hint?: string; onReset?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-4 py-10 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-paper-2 to-white ring-1 ring-line"><SearchX size={22} className="text-slate" aria-hidden /></span>
      <div className="text-[13.5px] font-semibold">{title}</div>
      {hint && <p className="max-w-sm text-[12.5px] text-slate-ink">{hint}</p>}
      {onReset && (
        <button type="button" className="btn mt-1" onClick={onReset}>
          Reset filters
        </button>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ Stat (inline metric) */
export function Stat({
  label,
  value,
  sub,
  tone,
  tip,
  kind,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: "loss" | "gain" | "neutral";
  tip?: ReactNode;
  kind?: string;
}) {
  const color = tone === "loss" ? "text-vermilion-ink" : tone === "gain" ? "text-teal" : "text-ink";
  return (
    <div className="min-w-0">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-[12px] font-medium leading-tight text-slate-ink">{label}</span>
        {tip && <InfoTip text={tip} label={`${label} definition`} />}
        {kind && <KindBadge kind={kind} />}
      </div>
      <div className={`num mt-0.5 text-[21px] font-semibold leading-tight tracking-[-0.01em] ${color}`}>{value}</div>
      {sub && <div className="mt-0.5 text-[11.5px] text-slate-ink">{sub}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ Rate bar (inline) */
export function RateBar({ value, max, target }: { value: Num | undefined; max: number; target?: number }) {
  const v = value ?? 0;
  const w = max > 0 ? Math.min(100, (v / max) * 100) : 0;
  const over = target !== undefined && v > target;
  return (
    <div className="flex items-center gap-2">
      <div className="relative h-1.5 w-12 rounded-full bg-paper-2" aria-hidden>
        <div className={`absolute inset-y-0 left-0 rounded-full ${over ? "bg-gradient-to-r from-[#E07A4F] to-vermilion" : "bg-gradient-to-r from-[#4FA394] to-teal"}`} style={{ width: `${w}%` }} />
        {target !== undefined && max > 0 && (
          <div className="absolute -top-0.5 h-2.5 w-px bg-ink" style={{ left: `${Math.min(100, (target / max) * 100)}%` }} />
        )}
      </div>
      <span className="num text-[12px]">{pct(value)}</span>
    </div>
  );
}

/* ------------------------------------------------------------------ Notice */
export function Notice({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "warn" }) {
  return (
    <div
      className={`flex items-start gap-2 rounded-[10px] border px-3 py-2 text-[12px] leading-snug ${
        tone === "warn" ? "border-brass/50 bg-brass-wash text-ink" : "border-teal/20 bg-teal-wash/60 text-slate-ink"
      }`}
    >
      <Info size={13} className="mt-[1px] shrink-0" aria-hidden />
      <div>{children}</div>
    </div>
  );
}
