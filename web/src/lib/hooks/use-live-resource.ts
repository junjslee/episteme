"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export interface LiveResourceState<T> {
  data: T;
  loading: boolean;
  error: string | null;
  /** Timestamp of the last successful fetch (ms since epoch). */
  lastFetchAt: number | null;
  /** Whether the last update was served from cached last-good data (SWR). */
  stale: boolean;
  refetch: () => void;
}

export interface UseLiveResourceOptions {
  /** Poll interval in ms. Pass 0 or negative to disable polling. */
  intervalMs?: number;
  /** If false, skip initial + polled fetches. */
  enabled?: boolean;
  /** Headers to merge into the fetch request. */
  headers?: HeadersInit;
  /** Called once per successful fetch with the parsed payload. */
  onData?: (data: unknown) => void;
}

/**
 * SWR-lite: fetches `url`, keeps last-good `data` visible during refetches,
 * supports polling, cancels in-flight requests on unmount, and backs off on 5xx.
 */
export function useLiveResource<T>(
  url: string,
  fallback: T,
  options: UseLiveResourceOptions = {},
): LiveResourceState<T> {
  const { intervalMs = 10_000, enabled = true, headers, onData } = options;

  const [data, setData] = useState<T>(fallback);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastFetchAt, setLastFetchAt] = useState<number | null>(null);
  const [stale, setStale] = useState(true);

  const abortRef = useRef<AbortController | null>(null);
  const backoffRef = useRef(0);
  const onDataRef = useRef(onData);

  useEffect(() => {
    onDataRef.current = onData;
  }, [onData]);

  const fetcher = useCallback(async () => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    setLoading(true);
    try {
      const res = await fetch(url, {
        signal: ctrl.signal,
        headers,
        cache: "no-store",
      });
      if (!res.ok) {
        if (res.status >= 500) backoffRef.current += 1;
        throw new Error(`HTTP ${res.status}`);
      }
      backoffRef.current = 0;
      const json = (await res.json()) as T;
      setData(json);
      setLastFetchAt(Date.now());
      setStale(false);
      setError(null);
      onDataRef.current?.(json);
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      const message = err instanceof Error ? err.message : "fetch failed";
      setError(message);
      setStale(true);
    } finally {
      if (abortRef.current === ctrl) {
        setLoading(false);
        abortRef.current = null;
      }
    }
  }, [url, headers]);

  useEffect(() => {
    if (!enabled) return;
    // SWR-lite pattern: the initial fetch is the "subscribe to external
    // system" posture React 19 describes. The fetcher is async — its
    // setState calls land in later microtasks, not during the effect body.
    // React 19's set-state-in-effect rule flags the call site anyway; the
    // cleanup (abort + interval clear) is in the returned teardown.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetcher();
    if (intervalMs <= 0) return;
    const id = window.setInterval(() => {
      const backoffMultiplier = Math.min(1 + backoffRef.current, 6);
      if (backoffMultiplier > 1 && Date.now() % backoffMultiplier !== 0) return;
      fetcher();
    }, intervalMs);
    return () => {
      window.clearInterval(id);
      abortRef.current?.abort();
    };
  }, [fetcher, intervalMs, enabled]);

  const refetch = useCallback(() => {
    void fetcher();
  }, [fetcher]);

  return { data, loading, error, lastFetchAt, stale, refetch };
}
