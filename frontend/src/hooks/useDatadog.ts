import { useCallback, useEffect, useState } from "react";
import { fetchAnalyses, fetchAnalysis, triggerAnalysis } from "../api/datadog";
import type { DatadogAnalysis } from "../types";

const PAGE_SIZE = 20;

export function useDatadog() {
  const [analyses, setAnalyses] = useState<DatadogAnalysis[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAnalysis, setSelectedAnalysis] =
    useState<DatadogAnalysis | null>(null);

  const load = useCallback(async (newOffset: number) => {
    try {
      setLoading(true);
      const data = await fetchAnalyses(PAGE_SIZE, newOffset);
      setAnalyses(data.analyses);
      setTotal(data.total);
      setOffset(newOffset);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(0);
  }, [load]);

  const nextPage = useCallback(() => {
    const next = offset + PAGE_SIZE;
    if (next < total) load(next);
  }, [offset, total, load]);

  const prevPage = useCallback(() => {
    const prev = Math.max(0, offset - PAGE_SIZE);
    if (prev !== offset) load(prev);
  }, [offset, load]);

  const analyze = useCallback(
    async (params: { url?: string; query?: string; trace_id?: string }) => {
      try {
        setError(null);
        await triggerAnalysis(params);
        await load(0);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unknown error");
      }
    },
    [load],
  );

  const selectAnalysis = useCallback(async (id: string) => {
    try {
      const detail = await fetchAnalysis(id);
      setSelectedAnalysis(detail);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    }
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedAnalysis(null);
  }, []);

  return {
    analyses,
    total,
    loading,
    error,
    offset,
    pageSize: PAGE_SIZE,
    nextPage,
    prevPage,
    refresh: () => load(offset),
    analyze,
    selectedAnalysis,
    selectAnalysis,
    clearSelection,
  };
}
