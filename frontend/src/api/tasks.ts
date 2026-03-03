import type { AgentRun, Task, TaskStatus } from "../types";
import { apiFetch } from "./client";

const BASE = "/api/v1";

export async function fetchTasks(): Promise<Task[]> {
  const resp = await apiFetch(`${BASE}/tasks`);
  if (!resp.ok) throw new Error("Failed to fetch tasks");
  return resp.json();
}

export async function fetchTask(id: string): Promise<Task> {
  const resp = await apiFetch(`${BASE}/tasks/${id}`);
  if (!resp.ok) throw new Error("Failed to fetch task");
  return resp.json();
}

export async function updateTaskStatus(
  id: string,
  status: TaskStatus
): Promise<Task> {
  const resp = await apiFetch(`${BASE}/tasks/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!resp.ok) throw new Error("Failed to update task");
  return resp.json();
}

export async function updateTaskRepo(
  id: string,
  repo: string | null
): Promise<Task> {
  const resp = await apiFetch(`${BASE}/tasks/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo: repo ?? "" }),
  });
  if (!resp.ok) throw new Error("Failed to update task repo");
  return resp.json();
}

export async function triggerStage(
  id: string,
  stage: "plan" | "work" | "review"
): Promise<AgentRun> {
  const resp = await apiFetch(`${BASE}/tasks/${id}/${stage}`, {
    method: "POST",
  });
  if (!resp.ok) throw new Error(`Failed to trigger ${stage}`);
  return resp.json();
}

export async function stopTask(id: string): Promise<AgentRun> {
  const resp = await apiFetch(`${BASE}/tasks/${id}/stop`, {
    method: "POST",
  });
  if (!resp.ok) throw new Error("Failed to stop task");
  return resp.json();
}

export async function retryTask(id: string): Promise<Task> {
  const resp = await apiFetch(`${BASE}/tasks/${id}/retry`, {
    method: "POST",
  });
  if (!resp.ok) throw new Error("Failed to retry task");
  return resp.json();
}

export interface RunWithLogs extends AgentRun {
  logs: import("../types").AgentLog[];
}

export async function fetchTaskRuns(id: string): Promise<RunWithLogs[]> {
  const resp = await apiFetch(`${BASE}/tasks/${id}/runs`);
  if (!resp.ok) throw new Error("Failed to fetch task runs");
  return resp.json();
}
