import { useEffect, useState, useCallback } from "react";
import ActiveAgentRow from "../components/ActiveAgentRow";
import CostWidget from "../components/CostWidget";
import { fetchTasks } from "../api/tasks";
import { useDashboard } from "../hooks/useDashboard";
import type { Task, TaskStatus } from "../types";

const STATUS_COLORS: Record<TaskStatus, string> = {
  backlog: "text-foam",
  planned: "text-mist",
  working: "text-gold",
  reviewing: "text-sky",
  done: "text-teal",
  failed: "text-coral",
};

export default function Dashboard() {
  const { stats, costs, loading: statsLoading, error } = useDashboard();
  const [tasks, setTasks] = useState<Task[]>([]);

  const refreshTasks = useCallback(async () => {
    try {
      const data = await fetchTasks();
      setTasks(data);
    } catch {
      // task fetch errors are non-fatal; metrics still display
    }
  }, []);

  useEffect(() => {
    refreshTasks();
  }, [refreshTasks]);

  const activeAgents = tasks.filter(
    (t) => t.latest_run?.status === "running",
  );

  // Auto-refresh every 5s while agents are running
  useEffect(() => {
    if (activeAgents.length === 0) return;
    const interval = setInterval(refreshTasks, 5000);
    return () => clearInterval(interval);
  }, [activeAgents.length, refreshTasks]);

  if (statsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="text-mist">Loading dashboard...</span>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="text-coral">{error || "No data"}</span>
      </div>
    );
  }

  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold mb-6">Dashboard</h1>

      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="bg-abyss border border-foam/8 rounded-lg p-4">
          <div className="text-mist text-sm">Total Cost</div>
          <div className="text-2xl font-semibold text-foam">
            ${stats.total_cost_usd.toFixed(2)}
          </div>
        </div>
        <div className="bg-abyss border border-foam/8 rounded-lg p-4">
          <div className="text-mist text-sm">Active Runs</div>
          <div className="text-2xl font-semibold text-gold">
            {stats.active_runs}
          </div>
        </div>
        <div className="bg-abyss border border-foam/8 rounded-lg p-4">
          <div className="text-mist text-sm">Tasks by Status</div>
          <div className="flex flex-wrap gap-2 mt-1">
            {(Object.entries(stats.tasks_by_status) as [TaskStatus, number][]).map(
              ([status, count]) => (
                <span key={status} className={`text-sm ${STATUS_COLORS[status]}`}>
                  {status}: {count}
                </span>
              )
            )}
          </div>
        </div>
      </div>

      {activeAgents.length > 0 && (
        <div className="bg-abyss border border-foam/8 rounded-lg p-4 mb-8">
          <h2 className="text-sm font-medium text-mist mb-3">Active Agents</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-mist text-xs uppercase">
                <th className="text-left py-1">Task</th>
                <th className="text-center py-1">Stage</th>
                <th className="text-right py-1">Elapsed</th>
                <th className="text-right py-1">Cost</th>
                <th className="text-right py-1"></th>
              </tr>
            </thead>
            <tbody>
              {activeAgents.map((t) => (
                <ActiveAgentRow
                  key={t.id}
                  task={t}
                  onStopped={refreshTasks}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <CostWidget costs={costs} costByStage={stats.cost_by_stage} />
    </div>
  );
}
