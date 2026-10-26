import { useCallback, useEffect, useRef, useState } from "react";

export interface ApiState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  /** true while refetching with previous data still on screen */
  refreshing: boolean;
  reload: () => void;
}

/**
 * Fetch data whenever `key` changes. Cancels stale requests so results from an
 * older filter selection can never overwrite newer ones. Keeps the previous data
 * visible while refreshing (no flicker), but never invents data on failure.
 */
export function useApi<T>(fetcher: (signal: AbortSignal) => Promise<T>, key: string, enabled = true): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState<boolean>(enabled);
  const [version, setVersion] = useState(0);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    const ctrl = new AbortController();
    setLoading(true);
    setError(null);
    fetcherRef
      .current(ctrl.signal)
      .then((d) => {
        if (!ctrl.signal.aborted) setData(d);
      })
      .catch((e: Error) => {
        if (e.name === "AbortError" || ctrl.signal.aborted) return;
        setError(e);
        setData(null);
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, [key, version, enabled]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return { data, error, loading: loading && data === null, refreshing: loading && data !== null, reload };
}

/** Debounce a fast-changing value (search boxes, sliders). */
export function useDebounced<T>(value: T, ms = 250): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}
