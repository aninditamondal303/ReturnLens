/**
 * Ledger strip: the five headline KPIs on one carbon surface, separated by hairlines
 * rather than boxed into identical cards. Values, deltas and sparklines all come from the API.
 */
import { BarChart3, PiggyBank, ReceiptIndianRupee, ShoppingBag, Truck, Undo2, type LucideIcon } from "lucide-react";
import type { Kpi } from "../types/api";
import { Sparkline } from "../charts/charts";
import { byUnit, inr, int, pct } from "../utils/format";
import { Delta, InfoTip, KindBadge, Skeleton } from "./ui";

function fullValue(k: Kpi): string {
  if (k.unit === "INR") return inr(k.value);
  if (k.unit === "percent") return pct(k.value, 2);
  return int(k.value);
}

const ICONS: Record<string, [LucideIcon, string, string]> = {
  gmv: [ShoppingBag, "#4FA394", "#287C72"],
  unit_return_rate: [Undo2, "#E07A4F", "#D94F36"],
  refund: [ReceiptIndianRupee, "#C9A35E", "#B18A48"],
  incremental_costs: [Truck, "#E07A4F", "#C2402B"],
  contribution_after: [PiggyBank, "#7CC2B6", "#287C72"],
};

export function KpiLedger({ kpis, comparisonNote }: { kpis: Kpi[]; comparisonNote?: string | null }) {
  return (
    <section aria-label="Headline metrics" className="panel-dark grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5">
      {kpis.map((k, i) => {
        const negative = (k.value ?? 0) < 0 && k.unit === "INR";
        return (
          <div
            key={k.key}
            className={`flex min-w-0 flex-col gap-1.5 px-4 py-4 transition-colors duration-200 hover:bg-white/[0.03] ${i > 0 ? "lg:border-l" : ""} border-white/10 max-lg:border-b`}
          >
            <div className="flex items-center gap-2">
              <KpiIcon k={k.key} />
              <span className="text-[12px] font-medium leading-tight text-[#b9bfbb]">{k.label}</span>
              <InfoTip dark label={`${k.label} definition`} text={<><b className="font-semibold">{k.formula}</b><br />{k.definition}</>} />
            </div>
            <div className="flex items-end justify-between gap-2">
              <div
                className={`num whitespace-nowrap text-[25px] font-semibold leading-none tracking-[-0.02em] ${negative ? "text-[#f08a73]" : "text-white"}`}
                title={fullValue(k)}
              >
                {byUnit(k.value, k.unit)}
              </div>
              <Sparkline width={72} values={k.sparkline} color={k.key === "unit_return_rate" || k.key === "refund" || k.key === "incremental_costs" ? "#f08a73" : "#9CC7C0"} />
            </div>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11.5px] text-slate">
              {k.secondary_label && (
                <span>
                  {k.secondary_label.replace(" (after return costs)", "")}{" "}
                  <span className="num text-paper/90">{pct(k.secondary_value)}</span>
                </span>
              )}
            </div>
            <div className="mt-auto flex items-center justify-between gap-2 pt-1">
              {k.change !== null ? (
                <span className="flex items-center gap-1.5">
                  <Delta dark change={k.change} type={k.change_type} good={k.good_direction} />
                  <span className="text-[10.5px] text-slate">vs prior period</span>
                </span>
              ) : (
                <span className="text-[10.5px] text-slate" title={comparisonNote ?? undefined}>
                  No prior period in range
                </span>
              )}
              <KindBadge dark kind={k.kind} />
            </div>
          </div>
        );
      })}
    </section>
  );
}

export function KpiLedgerSkeleton() {
  return (
    <div className="panel-dark grid grid-cols-1 gap-px sm:grid-cols-2 lg:grid-cols-5" aria-busy="true" aria-label="Loading metrics">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex flex-col gap-2 px-4 py-4">
          <Skeleton className="h-3 w-28 !bg-ink-3" />
          <Skeleton className="h-6 w-32 !bg-ink-3" />
          <Skeleton className="h-3 w-20 !bg-ink-3" />
        </div>
      ))}
    </div>
  );
}

function KpiIcon({ k }: { k: string }) {
  const [Icon, a, b] = ICONS[k] ?? [BarChart3, "#9CC7C0", "#287C72"];
  return (
    <span
      className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[9px] text-white"
      style={{ background: `linear-gradient(135deg, ${a}, ${b})`, boxShadow: `0 6px 14px -6px ${b}` }}
      aria-hidden
    >
      <Icon size={15} strokeWidth={2} />
    </span>
  );
}
