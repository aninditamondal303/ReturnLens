/**
 * Compact financial table: sticky header, right-aligned numbers, keyboard-sortable
 * headers, optional row selection. Sorting can be server-side (onSort) or local.
 */
import { useMemo, useState, type ReactNode } from "react";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, ChevronsUpDown } from "lucide-react";
import { int } from "../utils/format";
import { InfoTip } from "./ui";

export interface Column<T> {
  key: string;
  header: string;
  render?: (row: T) => ReactNode;
  align?: "left" | "right" | "center";
  sortable?: boolean;
  tip?: string;
  width?: string;
  className?: string;
}

export type SortState = { by: string; dir: "asc" | "desc" };

export function DataTable<T>({
  rows,
  columns,
  rowKey,
  sort,
  onSort,
  localSort = false,
  onRowClick,
  selectedKey,
  rowClass,
  maxHeight = 520,
  caption,
  dense = false,
}: {
  rows: T[];
  columns: Column<T>[];
  rowKey: (row: T) => string;
  sort?: SortState;
  onSort?: (s: SortState) => void;
  localSort?: boolean;
  onRowClick?: (row: T) => void;
  selectedKey?: string | null;
  rowClass?: (row: T) => string;
  maxHeight?: number | string;
  caption: string;
  dense?: boolean;
}) {
  const [local, setLocal] = useState<SortState | undefined>(sort);
  const active = localSort ? local : sort;

  const sorted = useMemo(() => {
    if (!localSort || !local) return rows;
    const { by, dir } = local;
    return [...rows].sort((a, b) => {
      const va = (a as unknown as Record<string, unknown>)[by];
      const vb = (b as unknown as Record<string, unknown>)[by];
      if (va === vb) return 0;
      if (va === null || va === undefined) return 1;
      if (vb === null || vb === undefined) return -1;
      const cmp = typeof va === "number" && typeof vb === "number" ? va - vb : String(va).localeCompare(String(vb));
      return dir === "asc" ? cmp : -cmp;
    });
  }, [rows, local, localSort]);

  const toggle = (key: string) => {
    const next: SortState = active?.by === key ? { by: key, dir: active.dir === "desc" ? "asc" : "desc" } : { by: key, dir: "desc" };
    if (localSort) setLocal(next);
    onSort?.(next);
  };

  const pad = dense ? "px-2.5 py-1.5" : "px-3 py-2";
  return (
    <div className="overflow-auto" style={{ maxHeight }}>
      <table className="w-full border-collapse text-[12.5px]">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            {columns.map((c) => {
              const isSorted = active?.by === c.key;
              const align = c.align === "right" ? "text-right" : c.align === "center" ? "text-center" : "text-left";
              return (
                <th
                  key={c.key}
                  scope="col"
                  style={{ width: c.width }}
                  aria-sort={isSorted ? (active!.dir === "asc" ? "ascending" : "descending") : undefined}
                  className={`table-head whitespace-nowrap border-b border-line px-3 py-2 ${align}`}
                >
                  <span className={`inline-flex items-center gap-1 ${c.align === "right" ? "flex-row-reverse" : ""}`}>
                    {c.sortable ? (
                      <button
                        type="button"
                        onClick={() => toggle(c.key)}
                        className={`inline-flex items-center gap-1 uppercase hover:text-ink ${isSorted ? "text-ink" : ""}`}
                      >
                        {c.header}
                        {isSorted ? (
                          active!.dir === "asc" ? <ArrowUp size={11} /> : <ArrowDown size={11} />
                        ) : (
                          <ChevronsUpDown size={11} className="opacity-50" />
                        )}
                      </button>
                    ) : (
                      c.header
                    )}
                    {c.tip && <InfoTip text={c.tip} label={`${c.header} definition`} />}
                  </span>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => {
            const key = rowKey(row);
            const selected = selectedKey === key;
            return (
              <tr
                key={key}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                onKeyDown={
                  onRowClick
                    ? (e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onRowClick(row);
                        }
                      }
                    : undefined
                }
                tabIndex={onRowClick ? 0 : undefined}
                aria-selected={onRowClick ? selected : undefined}
                className={`border-b border-line/70 transition-colors duration-100 ${
                  onRowClick ? "cursor-pointer hover:bg-paper focus:bg-paper focus:outline-none" : "hover:bg-paper/60"
                } ${selected ? "!bg-brass-wash" : ""} ${rowClass?.(row) ?? ""}`}
              >
                {columns.map((c) => {
                  const align = c.align === "right" ? "text-right num" : c.align === "center" ? "text-center" : "text-left";
                  const value = c.render ? c.render(row) : String((row as unknown as Record<string, unknown>)[c.key] ?? "—");
                  return (
                    <td key={c.key} className={`whitespace-nowrap ${pad} ${align} ${c.className ?? ""}`}>
                      {value}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function Pagination({
  page,
  totalPages,
  totalRows,
  pageSize,
  onPage,
  label = "rows",
}: {
  page: number;
  totalPages: number;
  totalRows: number;
  pageSize: number;
  onPage: (p: number) => void;
  label?: string;
}) {
  const from = totalRows === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(totalRows, page * pageSize);
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-3 border-t border-line px-3 py-2 text-[12px] text-slate-ink">
      <span className="num">
        {int(from)}–{int(to)} of {int(totalRows)} {label}
      </span>
      <div className="flex items-center gap-1">
        <button type="button" className="btn h-7 px-2" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page">
          <ChevronLeft size={14} />
        </button>
        <span className="num px-2">
          {page} / {totalPages}
        </span>
        <button
          type="button"
          className="btn h-7 px-2"
          disabled={page >= totalPages}
          onClick={() => onPage(page + 1)}
          aria-label="Next page"
        >
          <ChevronRight size={14} />
        </button>
      </div>
    </nav>
  );
}
