export type TaskStatus =
  | "backlog"
  | "planned"
  | "working"
  | "reviewing"
  | "done"
  | "failed";
export type RunStage = "plan" | "work" | "review";
export type RunStatus = "running" | "done" | "failed";
export type LogType = "text" | "tool_use" | "tool_result" | "error";

export interface Task {
  id: string;
  title: string;
  description: string;
  acceptance: string;
  status: TaskStatus;
  jira_key: string | null;
  jira_url: string | null;
  slack_thread_ts: string;
  pr_url: string | null;
  pr_number: number | null;
  repo: string | null;
  created_at: string;
  latest_run: AgentRun | null;
}

export interface AgentRun {
  id: string;
  task_id: string;
  stage: RunStage;
  status: RunStatus;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  started_at: string;
  finished_at: string | null;
}

export interface AgentLog {
  id: string;
  run_id: string;
  type: LogType;
  content: Record<string, unknown>;
  created_at: string;
}

export interface DashboardStats {
  total_cost_usd: number;
  active_runs: number;
  tasks_by_status: Record<TaskStatus, number>;
  cost_by_stage: Record<RunStage, number>;
}

export interface CostBreakdown {
  task_id: string;
  task_title: string;
  total_cost_usd: number;
  cost_by_stage: Record<RunStage, number>;
}

export interface IntegrationStatus {
  name: string;
  description: string;
  active: boolean;
  missing_env_vars: string[];
}

export interface IntegrationHealth {
  name: string;
  description: string;
  configured: boolean;
  healthy: boolean | null;
  error: string | null;
}

export interface ChatMessage {
  id: string;
  channel_id: string;
  channel_name: string;
  user_id: string;
  user_name: string;
  message: string;
  slack_ts: string;
  thread_ts: string | null;
  task_id: string | null;
  created_at: string;
}

export interface ChatMessagesResponse {
  total: number;
  offset: number;
  limit: number;
  messages: ChatMessage[];
}

export type AnalysisSource = "webhook" | "manual";
export type AnalysisStatus = "pending" | "analyzing" | "done" | "failed";

export interface DatadogAnalysis {
  id: string;
  source: AnalysisSource;
  trigger: string;
  status: AnalysisStatus;
  query: string;
  trace_id: string | null;
  log_count: number;
  raw_logs: Record<string, unknown>[];
  raw_trace: Record<string, unknown>[];
  summary: string;
  error_message: string | null;
  created_at: string;
}

export interface InternalLogEntry {
  id: string;
  source: string;
  level: string;
  logger_name: string;
  message: string;
  created_at: string;
}

export interface InternalLogsResponse {
  total: number;
  offset: number;
  limit: number;
  logs: InternalLogEntry[];
}

export interface DatadogAnalysesResponse {
  total: number;
  offset: number;
  limit: number;
  analyses: DatadogAnalysis[];
}
