import { useCallback, useEffect, useState } from "react";
import { fetchLogs } from "../api/logs";
import type { InternalLogEntry } from "../types";

const PAGE_SIZE = 100;

export function useLogs() {
  const [logs, setLogs] = useState<InternalLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<string>("");
  const [level, setLevel] = useState<string>("");

  const load = useCallback(
    async (newOffset: number, src?: string, lvl?: string) => {
      try {
        setLoading(true);
        const s = src ?? source;
        const l = lvl ?? level;
        const data = await fetchLogs(
          PAGE_SIZE,
          newOffset,
          s || undefined,
          l || undefined,
        );
        setLogs(data.logs);
        setTotal(data.total);
        setOffset(newOffset);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    },
    [source, level],
  );

  useEffect(() => {
    load(0);
  }, [load]);

  const filterBySource = useCallback(
    (s: string) => {
      setSource(s);
      load(0, s, level);
    },
    [load, level],
  );

  const filterByLevel = useCallback(
    (l: string) => {
      setLevel(l);
      load(0, source, l);
    },
    [load, source],
  );

  const nextPage = useCallback(() => {
    const next = offset + PAGE_SIZE;
    if (next < total) load(next);
  }, [offset, total, load]);

  const prevPage = useCallback(() => {
    const prev = Math.max(0, offset - PAGE_SIZE);
    if (prev !== offset) load(prev);
  }, [offset, load]);

  return {
    logs,
    total,
    offset,
    loading,
    error,
    source,
    level,
    pageSize: PAGE_SIZE,
    filterBySource,
    filterByLevel,
    nextPage,
    prevPage,
    refresh: () => load(offset),
  };
}
