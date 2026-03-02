import { Link } from "react-router-dom";
import type { Task, TaskStatus } from "../types";
import PRBadge from "./PRBadge";
import StageControls from "./StageControls";

const STATUS_STYLES: Record<TaskStatus, string> = {
  backlog: "bg-foam/20 text-foam",
  planned: "bg-mist/20 text-mist",
  working: "bg-gold/20 text-gold",
  reviewing: "bg-sky/20 text-sky",
  done: "bg-teal/20 text-teal",
  failed: "bg-coral/20 text-coral",
};

interface TaskCardProps {
  task: Task;
  onRefresh: () => void;
}

export default function TaskCard({ task, onRefresh }: TaskCardProps) {
  return (
    <div className="bg-abyss border border-foam/8 rounded-lg p-4 mb-3">
      <div className="flex items-start justify-between mb-2">
        <Link
          to={`/tasks/${task.id}`}
          className="text-sm font-medium text-white leading-tight hover:text-sky transition-colors"
        >
          {task.title}
        </Link>
        <span
          className={`text-xs px-2 py-0.5 rounded-full ${STATUS_STYLES[task.status]}`}
        >
          {task.status}
        </span>
      </div>

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

      {task.description && (
        <p className="text-xs text-mist mt-1 line-clamp-2">{task.description}</p>
      )}

      {task.pr_url && <PRBadge url={task.pr_url} number={task.pr_number} />}

      <div className="mt-3">
        <StageControls task={task} onRefresh={onRefresh} />
      </div>

      {task.latest_run && (
        <div className="mt-2 text-xs text-mist">
          Last run: {task.latest_run.stage} — ${task.latest_run.cost_usd.toFixed(4)}
        </div>
      )}
    </div>
  );
}
