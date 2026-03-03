import { useState } from "react";
import { Link } from "react-router-dom";
import { stopTask } from "../api/tasks";
import type { Task } from "../types";

function elapsed(startedAt: string): string {
  const seconds = Math.floor(
    (Date.now() - new Date(startedAt).getTime()) / 1000,
  );
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  if (minutes < 60) return `${minutes}m ${remaining}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

interface ActiveAgentRowProps {
  task: Task;
  onStopped: () => void;
}

export default function ActiveAgentRow({ task, onStopped }: ActiveAgentRowProps) {
  const [stopping, setStopping] = useState(false);
  const run = task.latest_run!;

  async function handleStop() {
    setStopping(true);
    try {
      await stopTask(task.id);
      onStopped();
    } catch {
      setStopping(false);
    }
  }

  return (
    <tr className="border-t border-horizon/20">
      <td className="py-2">
        <Link
          to={`/tasks/${task.id}`}
          className="text-white hover:text-sky transition-colors"
        >
          {task.title}
        </Link>
        {task.jira_key && (
          <span className="ml-2 text-xs text-sky">{task.jira_key}</span>
        )}
      </td>
      <td className="py-2 text-center">
        <span className="text-xs px-2 py-0.5 rounded-full bg-gold/20 text-gold capitalize">
          {run.stage}
        </span>
      </td>
      <td className="py-2 text-right text-mist text-sm">
        {elapsed(run.started_at)}
      </td>
      <td className="py-2 text-right text-mist text-sm">
        ${run.cost_usd.toFixed(4)}
      </td>
      <td className="py-2 text-right">
        <button
          onClick={handleStop}
          disabled={stopping}
          className="text-xs px-2 py-1 rounded bg-coral/20 text-coral hover:bg-coral/30 transition-colors disabled:opacity-50"
        >
          {stopping ? "Stopping..." : "Stop"}
        </button>
      </td>
    </tr>
  );
}
