"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { loadDemo } from "./api";
import type { DemoBundle } from "./types";

export interface Async<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): Async<T> {
  const [state, setState] = useState<{ data: T | null; error: string | null; loading: boolean }>({ data: null, error: null, loading: true });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    fn().then(
      (data) => alive && setState({ data, error: null, loading: false }),
      (e) => alive && setState({ data: null, error: e instanceof Error ? e.message : String(e), loading: false }),
    );
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { ...state, reload: useCallback(() => setTick((t) => t + 1), []) };
}

/** Polls fn every `ms` until `stop(data)` is true. */
export function usePolling<T>(fn: () => Promise<T>, stop: (d: T) => boolean, ms: number, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const stopRef = useRef(stop);
  stopRef.current = stop;
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const run = async () => {
      try {
        const d = await fn();
        if (!alive) return;
        setData(d);
        setError(null);
        setLoading(false);
        if (!stopRef.current(d)) timer = setTimeout(run, ms);
      } catch (e) {
        if (!alive) return;
        setError(e instanceof Error ? e.message : String(e));
        setLoading(false);
        timer = setTimeout(run, ms * 2); // keep trying; the backend may be restarting
      }
    };
    setLoading(true);
    run();
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, error, loading };
}

export function useDemo(): Async<DemoBundle> {
  return useAsync(loadDemo, []);
}
