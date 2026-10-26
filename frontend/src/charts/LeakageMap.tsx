/**
 * The Leakage Map — categories by unit return rate (x), contribution margin after
 * return costs (y) and return profit leakage (bubble area). Click a bubble to
 * select the category. All values come from /api/overview.
 */
import {
  CartesianGrid,
  Customized,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import type { CategoryRow } from "../types/api";
import { inrCompact, pct } from "../utils/format";
import { AXIS, C, GRID, TooltipBox, rowOf } from "./theme";

interface ShapeProps {
  cx?: number;
  cy?: number;
  size?: number;
  payload?: CategoryRow;
}

export function LeakageMap({
  rows,
  target,
  selected,
  onSelect,
  height = 340,
}: {
  rows: CategoryRow[];
  target: number;
  selected?: string | null;
  onSelect?: (category: string | null) => void;
  height?: number;
}) {
  const data = rows.filter((r) => r.unit_return_rate !== null && r.contribution_margin !== null);
  const maxX = Math.max(target * 1.4, ...data.map((d) => d.unit_return_rate ?? 0)) * 1.08;
  const ys = data.map((d) => d.contribution_margin ?? 0);
  const minY = Math.min(0, ...ys) - 0.05;
  const maxY = Math.max(...ys, 0.1) + 0.06;

  const Bubble = (props: ShapeProps) => {
    const { cx = 0, cy = 0, size = 100, payload } = props;
    if (!payload) return null;
    const r = Math.max(6, Math.sqrt(size / Math.PI));
    const negative = (payload.contribution_after ?? 0) < 0;
    const above = (payload.unit_return_rate ?? 0) > target;
    const isSel = selected === payload.category;
    const dim = selected && !isSel;
    const fill = negative ? C.vermilion : above ? C.vermilionLight : C.tealLight;
    return (
      <g
        style={{ cursor: onSelect ? "pointer" : "default", opacity: dim ? 0.35 : 1 }}
        role="button"
        tabIndex={0}
        aria-label={`${payload.category}: return rate ${pct(payload.unit_return_rate)}, contribution margin ${pct(payload.contribution_margin)}, leakage ${inrCompact(payload.return_leakage)}`}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && onSelect) {
            e.preventDefault();
            onSelect(isSel ? null : payload.category);
          }
        }}
      >
        <circle cx={cx} cy={cy} r={r} fill={fill} fillOpacity={negative ? 0.85 : 0.55} stroke={isSel ? C.ink : negative ? C.vermilion : above ? C.vermilion : C.teal} strokeWidth={isSel ? 2 : 1} />
      </g>
    );
  };

  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 22, right: 24, bottom: 26, left: 8 }}>
          <CartesianGrid {...GRID} vertical />
          <XAxis
            type="number"
            dataKey="unit_return_rate"
            domain={[0, maxX]}
            tickFormatter={(v: number) => pct(v, 0)}
            {...AXIS}
            label={{ value: "Unit return rate →", position: "insideBottomRight", offset: -14, fontSize: 11, fill: C.slate }}
          />
          <YAxis
            type="number"
            dataKey="contribution_margin"
            domain={[minY, maxY]}
            tickFormatter={(v: number) => pct(v, 0)}
            width={58}
            {...AXIS}
            label={{ value: "Contribution margin after return costs", angle: -90, position: "insideLeft", offset: 0, dy: 110, fontSize: 11, fill: C.slate }}
          />
          <ZAxis type="number" dataKey="return_leakage" range={[140, 2600]} />
          <ReferenceLine x={target} stroke={C.brass} strokeDasharray="4 3" label={{ value: `Example target ${pct(target, 0)}`, position: "top", fontSize: 10.5, fill: C.brass }} />
          <ReferenceLine y={0} stroke={C.ink} strokeWidth={1} />
          <Tooltip
            cursor={false}
            content={(p) => {
              const r = rowOf<CategoryRow>(p);
              if (!r) return null;
              return (
                <TooltipBox
                  title={r.category}
                  rows={[
                    { label: "Unit return rate", value: pct(r.unit_return_rate) },
                    { label: "Contribution margin", value: pct(r.contribution_margin) },
                    { label: "Return profit leakage", value: inrCompact(r.return_leakage) },
                    { label: "Incremental return costs", value: inrCompact(r.incremental_costs) },
                    { label: "Refunds", value: inrCompact(r.refund) },
                    { label: "Est. contribution", value: inrCompact(r.contribution_after) },
                  ]}
                />
              );
            }}
          />
          <Scatter
            data={data}
            shape={(props: unknown) => <Bubble {...(props as ShapeProps)} />}
            onClick={(d: { payload?: CategoryRow }) => {
              if (onSelect && d?.payload) onSelect(selected === d.payload.category ? null : d.payload.category);
            }}
            isAnimationActive={false}
          />
          <Customized component={(p: unknown) => <BubbleLabels chart={p as ChartState} selected={selected ?? null} />} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ------------------------------------------------------------------ collision-aware labels */
interface ChartState {
  offset?: { left: number; top: number; width: number; height: number };
  formattedGraphicalItems?: { props?: { points?: { cx: number; cy: number; size: number; payload: CategoryRow }[] } }[];
}

type Box = { x0: number; y0: number; x1: number; y1: number };
const overlaps = (a: Box, b: Box) => a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;
const LABEL_H = 13;
const textWidth = (t: string) => t.length * 6.1 + 4; // 11px DM Sans, conservative

/**
 * Places each category name next to its bubble without overlapping other labels or bubbles:
 * largest bubbles first, trying above, below, right and left; falls back to above.
 */
function BubbleLabels({ chart, selected }: { chart: ChartState; selected: string | null }) {
  const pts = chart.formattedGraphicalItems?.[0]?.props?.points ?? [];
  const area = chart.offset;
  if (!pts.length || !area) return null;
  const bubbles = pts.map((p) => ({ ...p, r: Math.max(6, Math.sqrt((p.size || 100) / Math.PI)) }));
  const circleBoxes: Box[] = bubbles.map((b) => ({ x0: b.cx - b.r, y0: b.cy - b.r, x1: b.cx + b.r, y1: b.cy + b.r }));
  const placed: Box[] = [];
  const out: { x: number; y: number; anchor: "start" | "middle" | "end"; text: string; sel: boolean; dim: boolean;
    leader: [number, number, number, number] | null }[] = [];
  const order = [...bubbles.keys()].sort((a, b) => bubbles[b].r - bubbles[a].r);
  for (const i of order) {
    const b = bubbles[i];
    const text = b.payload.category;
    const w = textWidth(text);
    const candidates: { x: number; y: number; anchor: "start" | "middle" | "end"; box: Box; far?: boolean }[] = [];
    for (const d of [0, 14, 28]) {
      const r = b.r + d;
      const diag = b.r * 0.7 + d * 0.7;
      // above, below, right, left, then the four diagonals; each ring a little further out
      candidates.push(
        { x: b.cx, y: b.cy - r - 4, anchor: "middle", box: { x0: b.cx - w / 2, y0: b.cy - r - 4 - LABEL_H, x1: b.cx + w / 2, y1: b.cy - r - 4 } },
        { x: b.cx, y: b.cy + r + 12, anchor: "middle", box: { x0: b.cx - w / 2, y0: b.cy + r + 1, x1: b.cx + w / 2, y1: b.cy + r + 1 + LABEL_H } },
        { x: b.cx + r + 4, y: b.cy + 4, anchor: "start", box: { x0: b.cx + r + 4, y0: b.cy - 8, x1: b.cx + r + 4 + w, y1: b.cy + 5 } },
        { x: b.cx - r - 4, y: b.cy + 4, anchor: "end", box: { x0: b.cx - r - 4 - w, y0: b.cy - 8, x1: b.cx - r - 4, y1: b.cy + 5 } },
        { x: b.cx + diag + 2, y: b.cy - diag - 2, anchor: "start", box: { x0: b.cx + diag + 2, y0: b.cy - diag - 2 - LABEL_H, x1: b.cx + diag + 2 + w, y1: b.cy - diag - 2 } },
        { x: b.cx - diag - 2, y: b.cy - diag - 2, anchor: "end", box: { x0: b.cx - diag - 2 - w, y0: b.cy - diag - 2 - LABEL_H, x1: b.cx - diag - 2, y1: b.cy - diag - 2 } },
        { x: b.cx + diag + 2, y: b.cy + diag + 12, anchor: "start", box: { x0: b.cx + diag + 2, y0: b.cy + diag + 1, x1: b.cx + diag + 2 + w, y1: b.cy + diag + 1 + LABEL_H } },
        { x: b.cx - diag - 2, y: b.cy + diag + 12, anchor: "end", box: { x0: b.cx - diag - 2 - w, y0: b.cy + diag + 1, x1: b.cx - diag - 2, y1: b.cy + diag + 1 + LABEL_H } },
      );
      if (d > 0) candidates.slice(-8).forEach((c) => (c.far = true));
    }
    const inside = (bx: Box) => bx.x0 >= area.left && bx.x1 <= area.left + area.width && bx.y0 >= area.top - 18 && bx.y1 <= area.top + area.height;
    const free = (bx: Box) => !placed.some((o) => overlaps(o, bx)) && !circleBoxes.some((c, j) => j !== i && overlaps(c, bx));
    const pick = candidates.find((c) => inside(c.box) && free(c.box)) ?? candidates.find((c) => inside(c.box)) ?? candidates[0];
    placed.push(pick.box);
    // a label moved away from its bubble gets a thin connector so it is never ambiguous
    let leader: [number, number, number, number] | null = null;
    if (pick.far) {
      const tx = Math.min(Math.max(b.cx, pick.box.x0), pick.box.x1);
      const ty = Math.min(Math.max(b.cy, pick.box.y0), pick.box.y1);
      const dx = tx - b.cx, dy = ty - b.cy, len = Math.hypot(dx, dy) || 1;
      leader = [b.cx + (dx / len) * b.r, b.cy + (dy / len) * b.r, tx, ty];
    }
    out.push({ x: pick.x, y: pick.y, anchor: pick.anchor, text, sel: selected === text, dim: !!selected && selected !== text, leader });
  }
  return (
    <g aria-hidden="true" pointerEvents="none">
      {out.map((l) => l.leader && (
        <line key={`${l.text}-leader`} x1={l.leader[0]} y1={l.leader[1]} x2={l.leader[2]} y2={l.leader[3]}
          stroke={C.slate} strokeWidth={0.75} opacity={l.dim ? 0.4 : 0.9} />
      ))}
      {out.map((l) => (
        <text key={l.text} x={l.x} y={l.y} textAnchor={l.anchor} fontSize={11} fontFamily="var(--font-sans)"
          fill={C.ink} fontWeight={l.sel ? 600 : 500} opacity={l.dim ? 0.4 : 1}>
          {l.text}
        </text>
      ))}
    </g>
  );
}
