import { useCallback, useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchTask, fetchTaskRuns, type RunWithLogs } from "../api/tasks";
import { useWebSocket } from "../hooks/useWebSocket";
import AgentLogViewer from "../components/AgentLogViewer";
import StageControls from "../components/StageControls";
import type { Task, AgentLog } from "../types";

const STATUS_STYLES: Record<string, string> = {
  backlog: "bg-foam/20 text-foam",
  planned: "bg-mist/20 text-mist",
  working: "bg-gold/20 text-gold",
  reviewing: "bg-sky/20 text-sky",
  done: "bg-teal/20 text-teal",
  failed: "bg-coral/20 text-coral",
};

const RUN_STATUS_STYLES: Record<string, string> = {
  running: "bg-gold/20 text-gold",
  done: "bg-teal/20 text-teal",
  failed: "bg-coral/20 text-coral",
};

export default function TaskDetail() {
  const { taskId } = useParams<{ taskId: string }>();
  const [task, setTask] = useState<Task | null>(null);
  const [runs, setRuns] = useState<RunWithLogs[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  // Find the active running run for live WebSocket streaming
  const activeRunId = runs.find((r) => r.status === "running")?.id ?? null;
  const liveRunId = selectedRunId ?? activeRunId;
  const { logs: wsLogs, connected } = useWebSocket(liveRunId);

  const refresh = useCallback(async () => {
    if (!taskId) return;
    try {
      setLoading(true);
      const [taskData, runsData] = await Promise.all([
        fetchTask(taskId),
        fetchTaskRuns(taskId),
      ]);
      setTask(taskData);
      setRuns(runsData);
    } catch {
      // handled by loading state
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Auto-refresh while a run is active
  useEffect(() => {
    if (!activeRunId) return;
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, [activeRunId, refresh]);

  if (loading && !task) {
    return (
      <div className="p-6 text-mist">Loading task...</div>
    );
  }

  if (!task) {
    return (
      <div className="p-6 text-coral">Task not found</div>
    );
  }

  // Determine which logs to show: live WS logs for the selected/active run, or stored logs from the run
  const selectedRun = runs.find((r) => r.id === liveRunId);
  let displayLogs: AgentLog[];
  if (liveRunId && connected && wsLogs.length > 0) {
    displayLogs = wsLogs;
  } else if (selectedRun) {
    displayLogs = selectedRun.logs ?? [];
  } else if (runs.length > 0) {
    displayLogs = runs[0].logs ?? [];
  } else {
    displayLogs = [];
  }

  const displayRunId = liveRunId ?? runs[0]?.id ?? null;

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Breadcrumb */}
      <div className="mb-4">
        <Link to="/" className="text-sky hover:underline text-sm">
          Board
        </Link>
        <span className="text-mist/50 mx-2">/</span>
        <span className="text-mist text-sm">{task.title}</span>
      </div>

      {/* Task header */}
      <div className="bg-abyss border border-foam/8 rounded-lg p-6 mb-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h1 className="text-xl font-semibold text-white mb-2">{task.title}</h1>
            <div className="flex items-center gap-3">
              <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_STYLES[task.status]}`}>
                {task.status}
              </span>
              {task.jira_key && (
                <a
                  href={task.jira_url || "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-sky hover:underline"
                >
                  {task.jira_key}
                </a>
              )}
              {task.pr_url && (
                <a
                  href={task.pr_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-teal hover:underline"
                >
                  PR #{task.pr_number}
                </a>
              )}
            </div>
          </div>
          <StageControls task={task} onRefresh={refresh} />
        </div>

        {task.description && (
          <div className="mb-3">
            <h3 className="text-xs text-mist/70 uppercase tracking-wide mb-1">Description</h3>
            <p className="text-sm text-mist whitespace-pre-wrap">{task.description}</p>
          </div>
        )}

        {task.acceptance && (
          <div>
            <h3 className="text-xs text-mist/70 uppercase tracking-wide mb-1">Acceptance Criteria</h3>
            <p className="text-sm text-mist whitespace-pre-wrap">{task.acceptance}</p>
          </div>
        )}
      </div>

      {/* Runs list */}
      {runs.length > 0 && (
        <div className="mb-4">
          <h2 className="text-sm font-medium text-mist mb-2">Runs</h2>
          <div className="flex gap-2 flex-wrap">
            {runs.map((run) => (
              <button
                key={run.id}
                onClick={() => setSelectedRunId(run.id)}
                className={`text-xs px-3 py-1.5 rounded border cursor-pointer transition-colors ${
                  displayRunId === run.id
                    ? "border-sky bg-sky/10 text-sky"
                    : "border-foam/8 bg-abyss text-mist hover:border-foam/20"
                }`}
              >
                <span className="capitalize">{run.stage}</span>
                <span className={`ml-2 px-1.5 py-0.5 rounded text-[10px] ${RUN_STATUS_STYLES[run.status]}`}>
                  {run.status}
                </span>
                <span className="ml-2 text-mist/50">
                  ${run.cost_usd.toFixed(4)}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Agent logs */}
      <div>
        <AgentLogViewer logs={displayLogs} connected={connected && liveRunId === activeRunId} />
      </div>
    </div>
  );
}
