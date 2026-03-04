import { useCallback, useEffect, useRef, useState } from "react";
import { fetchCosts, fetchStats } from "../api/dashboard";
import type { CostBreakdown, DashboardStats } from "../types";

const POLL_INTERVAL_MS = 15_000;

export function useDashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [costs, setCosts] = useState<CostBreakdown[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const initialLoad = useRef(true);

  const refresh = useCallback(async () => {
    try {
      if (initialLoad.current) {
        setLoading(true);
      }
      const [statsData, costsData] = await Promise.all([
        fetchStats(),
        fetchCosts(),
      ]);
      setStats(statsData);
      setCosts(costsData);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      if (initialLoad.current) {
        initialLoad.current = false;
        setLoading(false);
      }
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    refresh();
  }, [refresh]);

  // Background polling
  useEffect(() => {
    const interval = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  return { stats, costs, loading, error, refresh };
}
