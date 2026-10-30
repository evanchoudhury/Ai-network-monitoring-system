import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../lib/api";

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  errorStatus: number | null;
  refetch: () => void;
}

/**
 * Generic data-fetching hook with explicit loading/error states and optional
 * polling. Deliberately small (no external data lib) to keep the bundle lean.
 */
export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
  options: { pollMs?: number } = {}
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const mounted = useRef(true);
  // Keep the latest fetcher without forcing it into the dependency array.
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const run = useCallback(async () => {
    try {
      const result = await fetcherRef.current();
      if (mounted.current) {
        setData(result);
        setError(null);
        setErrorStatus(null);
      }
    } catch (e) {
      if (mounted.current) {
        setError(e instanceof Error ? e.message : "Unknown error");
        setErrorStatus(e instanceof ApiError ? e.status : null);
      }
    } finally {
      if (mounted.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    mounted.current = true;
    setLoading(true);
    run();
    let timer: ReturnType<typeof setInterval> | undefined;
    if (options.pollMs) {
      timer = setInterval(run, options.pollMs);
    }
    return () => {
      mounted.current = false;
      if (timer) clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, error, errorStatus, refetch: run };
}
