/** Chart palette and a shared tooltip consistent with the design system. */
import type { ReactNode } from "react";

export const C = {
  ink: "#171A19",
  paper: "#F5F3ED",
  vermilion: "#D94F36",
  teal: "#287C72",
  brass: "#B18A48",
  slate: "#777D79",
  line: "#DCDDD5",
  slateLight: "#B9BCB5",
  tealLight: "#9CC7C0",
  vermilionLight: "#EDA595",
};

export const AXIS = {
  stroke: C.line,
  tickLine: false,
  axisLine: { stroke: C.line },
} as const;

export const GRID = { stroke: C.line, strokeDasharray: "2 3", vertical: false } as const;

export function TooltipBox({ title, rows }: { title: ReactNode; rows: { label: string; value: ReactNode; color?: string }[] }) {
  return (
    <div className="min-w-[180px] rounded-[10px] border border-ink-3 bg-ink/95 px-3 py-2 text-[12px] text-paper shadow-xl backdrop-blur">
      <div className="mb-1 font-semibold">{title}</div>
      <dl className="grid grid-cols-[auto_auto] gap-x-4 gap-y-0.5">
        {rows.map((r) => (
          <div key={r.label} className="contents">
            <dt className="flex items-center gap-1.5 text-slate">
              {r.color && <span className="inline-block h-2 w-2 rounded-full" style={{ background: r.color }} aria-hidden />}
              {r.label}
            </dt>
            <dd className="text-right font-mono">{r.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/** Recharts passes {active, payload}; this narrows the payload to our row type. */
export function rowOf<T>(props: { active?: boolean; payload?: Array<{ payload?: unknown }> }): T | null {
  if (!props.active || !props.payload || props.payload.length === 0) return null;
  return (props.payload[0].payload as T) ?? null;
}
