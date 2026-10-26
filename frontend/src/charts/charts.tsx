/** General-purpose analytical charts used across pages (all data from the API). */
import type { ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import type { MonthRow, Num, RateRow } from "../types/api";
import { inr, inrCompact, int, monthLabel, pct } from "../utils/format";
import { AXIS, C, GRID, TooltipBox, rowOf } from "./theme";
import { WrappedTick } from "./Waterfall";

/* ------------------------------------------------------------ Sales trend */
export function SalesTrend({ rows, height = 260 }: { rows: MonthRow[]; height?: number }) {
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 4 }}>
          <defs>
            <linearGradient id="gGmv" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#9CC7C0" />
              <stop offset="1" stopColor="#DCE9E6" />
            </linearGradient>
            <linearGradient id="gRet" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#E07A4F" />
              <stop offset="1" stopColor="#F6CDBF" />
            </linearGradient>
            <linearGradient id="gScen" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#4FA394" />
              <stop offset="1" stopColor="#287C72" />
            </linearGradient>
            <linearGradient id="gBase" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#A9ADA8" />
              <stop offset="1" stopColor="#777D79" />
            </linearGradient>
          </defs>
          <CartesianGrid {...GRID} />
          <XAxis dataKey="month" tickFormatter={(m: string) => monthLabel(m)} {...AXIS} />
          <YAxis tickFormatter={(v: number) => inrCompact(v)} width={64} {...AXIS} />
          <Tooltip
            content={(p) => {
              const r = rowOf<MonthRow>(p);
              if (!r) return null;
              return (
                <TooltipBox
                  title={monthLabel(r.month, true)}
                  rows={[
                    { label: "GMV", value: inrCompact(r.gmv), color: C.slateLight },
                    { label: "Net revenue after refunds", value: inrCompact(r.net_revenue), color: C.ink },
                    { label: "Refunds", value: inrCompact(r.refund), color: C.vermilion },
                    { label: "Gap to GMV", value: pct(r.gmv ? 1 - (r.net_revenue ?? 0) / r.gmv : null) },
                  ]}
                />
              );
            }}
          />
          <Legend iconType="square" iconSize={9} verticalAlign="top" align="right" height={24} />
          <Bar dataKey="gmv" name="Gross merchandise value" fill="url(#gGmv)" radius={[5, 5, 0, 0]} isAnimationActive={false} />
          <Line dataKey="net_revenue" name="Net revenue after discounts & refunds" stroke={C.ink} strokeWidth={2} dot={{ r: 2.5 }} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ------------------------------------------------------------ Return-rate trend */
export function ReturnRateTrend({ rows, target, height = 260 }: { rows: MonthRow[]; target: number; height?: number }) {
  const max = Math.max(target, ...rows.map((r) => r.unit_return_rate ?? 0)) * 1.25;
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid {...GRID} />
          <XAxis dataKey="month" tickFormatter={(m: string) => monthLabel(m)} {...AXIS} />
          <YAxis domain={[0, max]} tickFormatter={(v: number) => pct(v, 0)} width={40} {...AXIS} />
          <ReferenceLine y={target} stroke={C.brass} strokeDasharray="4 3" label={{ value: `Example target ${pct(target, 0)} (illustrative)`, position: "insideTopLeft", fontSize: 10.5, fill: C.brass }} />
          <Tooltip
            content={(p) => {
              const r = rowOf<MonthRow>(p);
              if (!r) return null;
              return (
                <TooltipBox
                  title={monthLabel(r.month, true)}
                  rows={[
                    { label: "Unit return rate", value: pct(r.unit_return_rate), color: C.vermilion },
                    { label: "Order return rate", value: pct(r.order_return_rate), color: C.brass },
                    { label: "Returned / sold units", value: `${int(r.returned_units)} / ${int(r.units)}` },
                  ]}
                />
              );
            }}
          />
          <Legend iconType="plainline" iconSize={12} verticalAlign="top" align="right" height={24} />
          <Line dataKey="unit_return_rate" name="Unit return rate" stroke={C.vermilion} strokeWidth={2} dot={{ r: 2.5 }} isAnimationActive={false} />
          <Line dataKey="order_return_rate" name="Order return rate" stroke={C.brass} strokeWidth={1.5} strokeDasharray="5 3" dot={false} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ------------------------------------------------------------ Rate bars */
export function RateBars({
  rows,
  target,
  height,
  valueLabel = "Unit return rate",
}: {
  rows: RateRow[];
  target?: number;
  height?: number;
  valueLabel?: string;
}) {
  const h = height ?? Math.max(140, rows.length * 30 + 40);
  return (
    <div style={{ height: h }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 48, bottom: 4, left: 4 }}>
          <CartesianGrid {...GRID} vertical horizontal={false} />
          <XAxis type="number" tickFormatter={(v: number) => pct(v, 0)} {...AXIS} />
          <YAxis type="category" dataKey="label" width={118} tick={{ fontSize: 11, fill: C.ink, fontFamily: "var(--font-sans)" }} {...AXIS} />
          {target !== undefined && <ReferenceLine x={target} stroke={C.brass} strokeDasharray="4 3" />}
          <Tooltip
            cursor={{ fill: "rgba(23,26,25,0.04)" }}
            content={(p) => {
              const r = rowOf<RateRow>(p);
              if (!r) return null;
              return (
                <TooltipBox
                  title={r.label}
                  rows={[
                    { label: valueLabel, value: pct(r.unit_return_rate) },
                    { label: "Returned / sold units", value: `${int(r.returned_units)} / ${int(r.units)}` },
                    { label: "Order lines", value: int(r.lines) },
                  ]}
                />
              );
            }}
          />
          <Bar dataKey="unit_return_rate" radius={[0, 4, 4, 0]} isAnimationActive={false} label={{ position: "right", formatter: (v: unknown) => pct(Number(v)), fontSize: 10.5, fontFamily: "var(--font-mono)", fill: C.ink }}>
            {rows.map((r) => (
              <Cell key={r.label} fill={target !== undefined && (r.unit_return_rate ?? 0) > target ? C.vermilion : C.slate} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ------------------------------------------------------------ Ranked bars (generic) */
export function RankedBars<T extends object>({
  rows,
  labelKey,
  valueKey,
  format,
  colorFor,
  tooltipRows,
  height,
  labelWidth = 110,
}: {
  rows: T[];
  labelKey: keyof T & string;
  valueKey: keyof T & string;
  format: (v: number) => string;
  colorFor?: (row: T) => string;
  tooltipRows?: (row: T) => { label: string; value: ReactNode }[];
  height?: number;
  labelWidth?: number;
}) {
  const h = height ?? Math.max(140, rows.length * 28 + 30);
  return (
    <div style={{ height: h }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 64, bottom: 4, left: 4 }}>
          <CartesianGrid {...GRID} vertical horizontal={false} />
          <XAxis type="number" tickFormatter={(v: number) => format(v)} {...AXIS} />
          <YAxis type="category" dataKey={labelKey} width={labelWidth} tick={{ fontSize: 11, fill: C.ink, fontFamily: "var(--font-sans)" }} {...AXIS} />
          <Tooltip
            cursor={{ fill: "rgba(23,26,25,0.04)" }}
            content={(p) => {
              const r = rowOf<T>(p);
              if (!r) return null;
              const rec = r as unknown as Record<string, unknown>;
              return <TooltipBox title={String(rec[labelKey])} rows={tooltipRows ? tooltipRows(r) : [{ label: "Value", value: format(Number(rec[valueKey])) }]} />;
            }}
          />
          <Bar dataKey={valueKey} radius={[0, 4, 4, 0]} isAnimationActive={false} label={{ position: "right", formatter: (v: unknown) => format(Number(v)), fontSize: 10.5, fontFamily: "var(--font-mono)", fill: C.ink }}>
            {rows.map((r, i) => (
              <Cell key={i} fill={colorFor ? colorFor(r) : C.slate} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ------------------------------------------------------------ Risk score histogram */
export function ScoreHistogram({
  bins,
  height = 240,
}: {
  bins: { bin_start: number; bin_end: number; lines: number; returned_lines: number; band: string }[];
  height?: number;
}) {
  const color = (b: string) => (b === "High" ? C.vermilion : b === "Medium" ? C.brass : C.slateLight);
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={bins} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} barCategoryGap={1}>
          <CartesianGrid {...GRID} />
          <XAxis dataKey="bin_start" tickFormatter={(v: number) => String(v)} {...AXIS} />
          <YAxis tickFormatter={(v: number) => int(v)} width={48} {...AXIS} />
          <Tooltip
            cursor={{ fill: "rgba(23,26,25,0.04)" }}
            content={(p) => {
              const r = rowOf<(typeof bins)[number]>(p);
              if (!r) return null;
              return (
                <TooltipBox
                  title={`Score ${r.bin_start}–${r.bin_end - 1} · ${r.band}`}
                  rows={[
                    { label: "Order lines", value: int(r.lines) },
                    { label: "Later returned", value: int(r.returned_lines) },
                    { label: "Observed line return rate", value: pct(r.lines ? r.returned_lines / r.lines : null) },
                  ]}
                />
              );
            }}
          />
          <Bar dataKey="lines" radius={[3, 3, 0, 0]} isAnimationActive={false}>
            {bins.map((b) => (
              <Cell key={b.bin_start} fill={color(b.band)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ------------------------------------------------------------ Generic scatter */
export interface ScatterPoint {
  x: number;
  y: number;
  z?: number;
  color: string;
  title: string;
  rows: { label: string; value: ReactNode }[];
  id: string;
}

export function PointScatter({
  points,
  xLabel,
  yLabel,
  xFormat,
  yFormat,
  height = 300,
  xLog = false,
  onPointClick,
  referenceY,
}: {
  points: ScatterPoint[];
  xLabel: string;
  yLabel: string;
  xFormat: (v: number) => string;
  yFormat: (v: number) => string;
  height?: number;
  xLog?: boolean;
  onPointClick?: (id: string) => void;
  referenceY?: number;
}) {
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 10, right: 16, bottom: 22, left: 4 }}>
          <CartesianGrid {...GRID} vertical />
          <XAxis
            type="number"
            dataKey="x"
            scale={xLog ? "log" : "auto"}
            domain={xLog ? ["auto", "auto"] : [0, "auto"]}
            tickFormatter={(v: number) => xFormat(v)}
            {...AXIS}
            label={{ value: xLabel, position: "insideBottomRight", offset: -12, fontSize: 11, fill: C.slate }}
          />
          <YAxis type="number" dataKey="y" tickFormatter={(v: number) => yFormat(v)} width={56} {...AXIS} label={{ value: yLabel, angle: -90, position: "insideLeft", offset: 10, dy: 60, fontSize: 11, fill: C.slate }} />
          <ZAxis type="number" dataKey="z" range={[24, 260]} />
          {referenceY !== undefined && <ReferenceLine y={referenceY} stroke={C.ink} />}
          <Tooltip
            cursor={false}
            content={(p) => {
              const r = rowOf<ScatterPoint>(p);
              return r ? <TooltipBox title={r.title} rows={r.rows} /> : null;
            }}
          />
          <Scatter
            data={points}
            isAnimationActive={false}
            onClick={(d: { payload?: ScatterPoint }) => d?.payload && onPointClick?.(d.payload.id)}
            style={{ cursor: onPointClick ? "pointer" : "default" }}
          >
            {points.map((pt) => (
              <Cell key={pt.id} fill={pt.color} fillOpacity={0.7} stroke={pt.color} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ------------------------------------------------------------ Units vs return rate (product detail) */
export function UnitsAndRate({ rows, height = 200 }: { rows: MonthRow[]; height?: number }) {
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="gGmv" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#9CC7C0" />
              <stop offset="1" stopColor="#DCE9E6" />
            </linearGradient>
            <linearGradient id="gRet" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#E07A4F" />
              <stop offset="1" stopColor="#F6CDBF" />
            </linearGradient>
            <linearGradient id="gScen" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#4FA394" />
              <stop offset="1" stopColor="#287C72" />
            </linearGradient>
            <linearGradient id="gBase" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#A9ADA8" />
              <stop offset="1" stopColor="#777D79" />
            </linearGradient>
          </defs>
          <CartesianGrid {...GRID} />
          <XAxis dataKey="month" tickFormatter={(m: string) => monthLabel(m)} {...AXIS} />
          <YAxis yAxisId="u" tickFormatter={(v: number) => int(v)} width={34} {...AXIS} />
          <YAxis yAxisId="r" orientation="right" tickFormatter={(v: number) => pct(v, 0)} width={38} {...AXIS} />
          <Tooltip
            content={(p) => {
              const r = rowOf<MonthRow>(p);
              if (!r) return null;
              return (
                <TooltipBox
                  title={monthLabel(r.month, true)}
                  rows={[
                    { label: "Units sold", value: int(r.units), color: C.slateLight },
                    { label: "Units returned", value: int(r.returned_units), color: C.vermilionLight },
                    { label: "Return rate", value: pct(r.unit_return_rate), color: C.vermilion },
                    { label: "GMV", value: inr(r.gmv) },
                  ]}
                />
              );
            }}
          />
          <Bar yAxisId="u" dataKey="units" name="Units sold" fill="url(#gGmv)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
          <Bar yAxisId="u" dataKey="returned_units" name="Units returned" fill="url(#gRet)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
          <Line yAxisId="r" dataKey="unit_return_rate" name="Return rate" stroke={C.vermilion} strokeWidth={2} dot={{ r: 2 }} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ------------------------------------------------------------ Baseline vs scenario bars */
export function CompareBars({
  rows,
  height = 220,
}: {
  rows: { label: string; baseline: number; scenario: number }[];
  height?: number;
}) {
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 4 }} barGap={2}>
          <defs>
            <linearGradient id="gGmv" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#9CC7C0" />
              <stop offset="1" stopColor="#DCE9E6" />
            </linearGradient>
            <linearGradient id="gRet" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#E07A4F" />
              <stop offset="1" stopColor="#F6CDBF" />
            </linearGradient>
            <linearGradient id="gScen" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#4FA394" />
              <stop offset="1" stopColor="#287C72" />
            </linearGradient>
            <linearGradient id="gBase" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#A9ADA8" />
              <stop offset="1" stopColor="#777D79" />
            </linearGradient>
          </defs>
          <CartesianGrid {...GRID} />
          <XAxis dataKey="label" interval={0} height={36} {...AXIS} tick={<WrappedTick maxChars={18} />} />
          <YAxis tickFormatter={(v: number) => inrCompact(v)} width={64} {...AXIS} />
          <Tooltip
            cursor={{ fill: "rgba(23,26,25,0.04)" }}
            content={(p) => {
              const r = rowOf<{ label: string; baseline: number; scenario: number }>(p);
              if (!r) return null;
              return (
                <TooltipBox
                  title={r.label}
                  rows={[
                    { label: "Baseline", value: inr(r.baseline), color: C.slate },
                    { label: "Scenario (hypothetical)", value: inr(r.scenario), color: C.teal },
                    { label: "Estimated saving", value: inr(r.baseline - r.scenario) },
                  ]}
                />
              );
            }}
          />
          <Legend iconType="square" iconSize={9} verticalAlign="top" align="right" height={24} />
          <Bar dataKey="baseline" name="Baseline (historical)" fill="url(#gBase)" radius={[5, 5, 0, 0]} isAnimationActive={false} />
          <Bar dataKey="scenario" name="Scenario (hypothetical)" fill="url(#gScen)" radius={[5, 5, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Tiny inline SVG sparkline (no axes) for KPI displays. */
export function Sparkline({ values, color = C.paper, width = 96, height = 26 }: { values: Num[]; color?: string; width?: number; height?: number }) {
  const v = values.map((x) => (typeof x === "number" ? x : null));
  const nums = v.filter((x): x is number => x !== null);
  if (nums.length < 2) return <svg width={width} height={height} aria-hidden />;
  const min = Math.min(...nums);
  const max = Math.max(...nums);
  const span = max - min || 1;
  const step = width / (v.length - 1);
  let d = "";
  v.forEach((x, i) => {
    if (x === null) return;
    const px = i * step;
    const py = height - 2 - ((x - min) / span) * (height - 4);
    d += `${d ? "L" : "M"}${px.toFixed(1)},${py.toFixed(1)}`;
  });
  const lastIdx = v.length - 1 - [...v].reverse().findIndex((x) => x !== null);
  const lx = lastIdx * step;
  const ly = height - 2 - (((v[lastIdx] as number) - min) / span) * (height - 4);
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden className="overflow-visible">
      <path d={d} fill="none" stroke={color} strokeWidth={1.25} strokeOpacity={0.75} />
      <circle cx={lx} cy={ly} r={2} fill={color} />
    </svg>
  );
}
