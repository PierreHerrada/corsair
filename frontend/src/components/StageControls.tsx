import { useState } from "react";
import { retryTask, stopTask, triggerStage } from "../api/tasks";
import type { Task } from "../types";

interface StageControlsProps {
  task: Task;
  onRefresh: () => void;
}

export default function StageControls({ task, onRefresh }: StageControlsProps) {
  const [loading, setLoading] = useState<string | null>(null);

  const handleTrigger = async (stage: "plan" | "work" | "review") => {
    setLoading(stage);
    try {
      await triggerStage(task.id, stage);
      onRefresh();
    } catch {
      // Error handling could be improved
    } finally {
      setLoading(null);
    }
  };

  const handleStop = async () => {
    setLoading("stop");
    try {
      await stopTask(task.id);
      onRefresh();
    } catch {
      // Error handling could be improved
    } finally {
      setLoading(null);
    }
  };

  const handleRetry = async () => {
    setLoading("retry");
    try {
      await retryTask(task.id);
      onRefresh();
    } catch {
      // Error handling could be improved
    } finally {
      setLoading(null);
    }
  };

  const isRunning = task.latest_run?.status === "running";

  return (
    <div className="flex gap-2">
      {isRunning && (
        <button
          onClick={handleStop}
          disabled={loading !== null}
          className="text-xs px-3 py-1 rounded bg-coral/20 text-coral hover:bg-coral/30 disabled:opacity-50"
        >
          {loading === "stop" ? "Stopping..." : "Stop"}
        </button>
      )}
      {task.status === "failed" && (
        <button
          onClick={handleRetry}
          disabled={loading !== null}
          className="text-xs px-3 py-1 rounded bg-coral/20 text-coral hover:bg-coral/30 disabled:opacity-50"
        >
          {loading === "retry" ? "Retrying..." : "Retry"}
        </button>
      )}
      {task.status === "backlog" && (
        <button
          onClick={() => handleTrigger("plan")}
          disabled={isRunning || loading !== null}
          className="text-xs px-3 py-1 rounded bg-wave/20 text-wave hover:bg-wave/30 disabled:opacity-50"
        >
          {loading === "plan" ? "Starting..." : "Run Plan"}
        </button>
      )}
      {task.status === "planned" && (
        <button
          onClick={() => handleTrigger("work")}
          disabled={isRunning || loading !== null}
          className="text-xs px-3 py-1 rounded bg-gold/20 text-gold hover:bg-gold/30 disabled:opacity-50"
        >
          {loading === "work" ? "Starting..." : "Run Work"}
        </button>
      )}
      {task.status === "working" && (
        <button
          onClick={() => handleTrigger("review")}
          disabled={isRunning || loading !== null}
          className="text-xs px-3 py-1 rounded bg-teal/20 text-teal hover:bg-teal/30 disabled:opacity-50"
        >
          {loading === "review" ? "Starting..." : "Run Review"}
        </button>
      )}
    </div>
  );
}
