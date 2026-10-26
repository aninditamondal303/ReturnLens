/**
 * Global filter state (reporting period, category, region, channel) shared by all pages,
 * plus dataset metadata loaded once from /api/metadata.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, type Query } from "../services/api";
import type { Metadata } from "../types/api";
import { monthEnd, monthLabel, monthStart } from "../utils/format";

export interface FilterState {
  startMonth: string | null; // yyyy-mm, null = first available
  endMonth: string | null; // yyyy-mm, null = last available
  category: string;
  region: string;
  channel: string;
}

export const EMPTY_FILTERS: FilterState = { startMonth: null, endMonth: null, category: "", region: "", channel: "" };

interface Ctx {
  filters: FilterState;
  setFilters: (patch: Partial<FilterState>) => void;
  resetFilters: () => void;
  query: Query;
  queryKey: string;
  metadata: Metadata | null;
  metadataError: string | null;
  reloadMetadata: () => void;
  periodLabel: string;
  activeCount: number;
}

const FilterCtx = createContext<Ctx | null>(null);

export function FilterProvider({ children }: { children: ReactNode }) {
  const [filters, setState] = useState<FilterState>(EMPTY_FILTERS);
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [metadataError, setMetadataError] = useState<string | null>(null);
  const [metaVersion, setMetaVersion] = useState(0);

  useEffect(() => {
    const ctrl = new AbortController();
    setMetadataError(null);
    api
      .metadata({ signal: ctrl.signal })
      .then(setMetadata)
      .catch((e: Error) => {
        if (e.name !== "AbortError") setMetadataError(e.message);
      });
    return () => ctrl.abort();
  }, [metaVersion]);

  const setFilters = useCallback((patch: Partial<FilterState>) => setState((s) => ({ ...s, ...patch })), []);
  const resetFilters = useCallback(() => setState(EMPTY_FILTERS), []);
  const reloadMetadata = useCallback(() => setMetaVersion((v) => v + 1), []);

  const value = useMemo<Ctx>(() => {
    const months = metadata?.months ?? [];
    const first = months[0];
    const last = months[months.length - 1];
    const start = filters.startMonth ?? first;
    const end = filters.endMonth ?? last;
    const fullPeriod = !filters.startMonth && !filters.endMonth;
    const query: Query = {
      start_date: !fullPeriod && start ? monthStart(start) : undefined,
      end_date: !fullPeriod && end ? monthEnd(end) : undefined,
      category: filters.category || undefined,
      region: filters.region || undefined,
      channel: filters.channel || undefined,
    };
    const periodLabel =
      start && end ? (start === end ? monthLabel(start, true) : `${monthLabel(start, true)} – ${monthLabel(end, true)}`) : "";
    const activeCount =
      (fullPeriod ? 0 : 1) + (filters.category ? 1 : 0) + (filters.region ? 1 : 0) + (filters.channel ? 1 : 0);
    return {
      filters,
      setFilters,
      resetFilters,
      query,
      queryKey: JSON.stringify(query),
      metadata,
      metadataError,
      reloadMetadata,
      periodLabel,
      activeCount,
    };
  }, [filters, metadata, metadataError, setFilters, resetFilters, reloadMetadata]);

  return <FilterCtx.Provider value={value}>{children}</FilterCtx.Provider>;
}

export function useFilters(): Ctx {
  const ctx = useContext(FilterCtx);
  if (!ctx) throw new Error("useFilters must be used inside <FilterProvider>");
  return ctx;
}
