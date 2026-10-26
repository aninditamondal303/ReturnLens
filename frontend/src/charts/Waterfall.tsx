/**
 * Financial waterfall (Return Cost Anatomy / Profit Leakage bridge).
 * Floating bars use [low, high] ranges, so the bridge stays correct even when
 * the running total crosses zero. Colour encodes the step's accounting nature.
 */
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { WaterfallStep } from "../types/api";
import { inr, inrCompact } from "../utils/format";
import { AXIS, C, GRID, TooltipBox, rowOf } from "./theme";

const KIND_COLOR: Record<WaterfallStep["kind"], string> = {
  total: C.ink,
  subtotal: C.slate,
  revenue_reduction: C.brass,
  cost: C.vermilion,
  recovery: C.teal,
};

export const KIND_LABEL: Record<WaterfallStep["kind"], string> = {
  total: "Total",
  subtotal: "Subtotal",
  revenue_reduction: "Revenue reduction",
  cost: "Cost",
  recovery: "Recovered value",
};

interface Row extends WaterfallStep {
  range: [number, number];
  short: string;
}

export function Waterfall({
  steps,
  height = 300,
  definitions,
}: {
  steps: WaterfallStep[];
  height?: number;
  definitions?: Record<string, string>;
}) {
  const data: Row[] = steps.map((s) => ({
    ...s,
    range: [Math.min(s.start, s.end), Math.max(s.start, s.end)],
    short: s.label.replace("Estimated ", "Est. ").replace("(net of returned stock)", "(net)"),
  }));
  const last = data[data.length - 1];
  return (
    <div className="w-full">
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 24, right: 8, bottom: 4, left: 8 }} barCategoryGap="18%">
            <CartesianGrid {...GRID} />
            <XAxis dataKey="short" interval={0} height={58} tick={<WrappedTick />} {...AXIS} />
            <YAxis tickFormatter={(v: number) => inrCompact(v)} width={64} {...AXIS} />
            <ReferenceLine y={0} stroke={C.ink} />
            <Tooltip
              cursor={{ fill: "rgba(23,26,25,0.04)" }}
              content={(p) => {
                const r = rowOf<Row>(p);
                if (!r) return null;
                return (
                  <TooltipBox
                    title={r.label}
                    rows={[
                      { label: KIND_LABEL[r.kind], value: inr(r.value), color: KIND_COLOR[r.kind] },
                      ...(r.kind === "total" || r.kind === "subtotal" ? [] : [{ label: "Running total", value: inr(r.end) }]),
                      ...(definitions?.[r.key] ? [{ label: "Meaning", value: <span className="block max-w-[220px] whitespace-normal font-sans">{definitions[r.key]}</span> }] : []),
                    ]}
                  />
                );
              }}
            />
            <Bar dataKey="range" radius={[4, 4, 4, 4]} isAnimationActive={false}>
              {data.map((d) => (
                <Cell key={d.key} fill={d.key === last?.key && d.value < 0 ? C.vermilion : KIND_COLOR[d.kind]} />
              ))}
              <LabelList dataKey="value" content={<BarValueLabel />} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11.5px] text-slate-ink" aria-label="Legend">
        {(["total", "revenue_reduction", "cost", "recovery", "subtotal"] as const)
          .filter((k) => steps.some((s) => s.kind === k))
          .map((k) => (
            <li key={k} className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5" style={{ background: KIND_COLOR[k] }} aria-hidden />
              {KIND_LABEL[k]}
            </li>
          ))}
      </ul>
    </div>
  );
}

export function WrappedTick(props: { x?: number; y?: number; payload?: { value: string }; maxChars?: number }) {
  const { x = 0, y = 0, payload, maxChars = 14 } = props;
  const words = (payload?.value ?? "").split(" ");
  const lines: string[] = [];
  let cur = "";
  for (const w of words) {
    if ((cur + " " + w).trim().length > maxChars) {
      if (cur) lines.push(cur);
      cur = w;
    } else cur = (cur + " " + w).trim();
  }
  if (cur) lines.push(cur);
  return (
    <g transform={`translate(${x},${y + 10})`}>
      {lines.slice(0, 4).map((l, i) => (
        <text key={i} x={0} y={i * 12} textAnchor="middle" fontSize={10.5} fill={C.slate} fontFamily="var(--font-sans)">
          {l}
        </text>
      ))}
    </g>
  );
}

/** Value label above each floating bar; never wraps (Recharts' default label wraps to the bar width). */
function BarValueLabel(props: { x?: number | string; y?: number | string; width?: number | string; value?: number | string }) {
  const x = Number(props.x ?? 0) + Number(props.width ?? 0) / 2;
  const y = Number(props.y ?? 0) - 6;
  return (
    <text x={x} y={y} textAnchor="middle" fontFamily="var(--font-mono)" fontSize={10.5} fill={C.ink} style={{ whiteSpace: "pre" }}>
      {inrCompact(Number(props.value))}
    </text>
  );
}
