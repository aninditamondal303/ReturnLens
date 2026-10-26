/** Consistent INR, percentage and number formatting (Indian digit grouping). */
import type { Num } from "../types/api";

const inrFull = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const inrPaise = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });
const intFmt = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const oneDp = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1, minimumFractionDigits: 1 });

export const DASH = "—";

const isNum = (v: Num | undefined): v is number => typeof v === "number" && Number.isFinite(v);

/** ₹5,09,49,554 */
export function inr(v: Num | undefined, paise = false): string {
  if (!isNum(v)) return DASH;
  return (paise ? inrPaise : inrFull).format(v);
}

/** Compact Indian units: ₹5.09 Cr, ₹33.7 L, ₹48.2 K, ₹950 */
export function inrCompact(v: Num | undefined): string {
  if (!isNum(v)) return DASH;
  const a = Math.abs(v);
  const sign = v < 0 ? "−" : "";
  if (a >= 1e7) return `${sign}₹${(a / 1e7).toFixed(2)} Cr`;
  if (a >= 1e5) return `${sign}₹${(a / 1e5).toFixed(1)} L`;
  if (a >= 1e3) return `${sign}₹${(a / 1e3).toFixed(1)} K`;
  return `${sign}₹${a.toFixed(0)}`;
}

/** 0.1234 -> "12.3%" */
export function pct(v: Num | undefined, digits = 1): string {
  if (!isNum(v)) return DASH;
  return `${(v * 100).toFixed(digits)}%`;
}

/** Change in percentage points: 0.012 -> "+1.2 pts" */
export function pts(v: Num | undefined): string {
  if (!isNum(v)) return DASH;
  const s = (v * 100).toFixed(1);
  return `${v > 0 ? "+" : v < 0 ? "−" : "±"}${s.replace("-", "")} pts`;
}

/** Relative change: 0.052 -> "+5.2%" */
export function signedPct(v: Num | undefined): string {
  if (!isNum(v)) return DASH;
  return `${v > 0 ? "+" : v < 0 ? "−" : "±"}${Math.abs(v * 100).toFixed(1)}%`;
}

export function int(v: Num | undefined): string {
  return isNum(v) ? intFmt.format(v) : DASH;
}

export function dec1(v: Num | undefined): string {
  return isNum(v) ? oneDp.format(v) : DASH;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-07" -> "Jul 26" (short) or "Jul 2026" */
export function monthLabel(m: string, long = false): string {
  const [y, mm] = m.split("-");
  const name = MONTHS[Number(mm) - 1] ?? mm;
  return long ? `${name} ${y}` : `${name} ${y.slice(2)}`;
}

/** "2026-07-04" -> "4 Jul 2026" */
export function dateLabel(d: string | null | undefined): string {
  if (!d) return DASH;
  const [y, m, day] = d.slice(0, 10).split("-");
  return `${Number(day)} ${MONTHS[Number(m) - 1]} ${y}`;
}

export function timeLabel(iso: string | null | undefined): string {
  if (!iso) return DASH;
  const d = new Date(iso);
  return `${dateLabel(iso.slice(0, 10))}, ${d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}`;
}

/** Format by metric unit declared by the API. */
export function byUnit(v: Num | undefined, unit: string, compact = true): string {
  if (unit === "percent") return pct(v);
  if (unit === "INR") return compact ? inrCompact(v) : inr(v);
  if (unit === "units") return int(v);
  return dec1(v);
}

/** First/last calendar day of a yyyy-mm month. */
export function monthStart(m: string): string {
  return `${m}-01`;
}
export function monthEnd(m: string): string {
  const [y, mm] = m.split("-").map(Number);
  const last = new Date(Date.UTC(y, mm, 0)).getUTCDate();
  return `${m}-${String(last).padStart(2, "0")}`;
}
