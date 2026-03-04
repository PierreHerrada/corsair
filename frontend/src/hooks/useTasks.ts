import { useCallback, useEffect, useRef, useState } from "react";
import { fetchTasks } from "../api/tasks";
import type { Task } from "../types";

const POLL_INTERVAL_MS = 15_000;

export function useTasks() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const initialLoad = useRef(true);

  const refresh = useCallback(async () => {
    try {
      // Only show loading spinner on the very first fetch
      if (initialLoad.current) {
        setLoading(true);
      }
      const data = await fetchTasks();
      setTasks(data);
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

  return { tasks, loading, error, refresh };
}
