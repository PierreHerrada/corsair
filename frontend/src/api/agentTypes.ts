import type { AgentType } from "../types";
import { apiFetch } from "./client";

const BASE = "/api/v1/agent-types";

export async function fetchAgentTypes(): Promise<AgentType[]> {
  const resp = await apiFetch(BASE);
  if (!resp.ok) throw new Error("Failed to fetch agent types");
  return resp.json();
}

export async function fetchAgentType(id: string): Promise<AgentType> {
  const resp = await apiFetch(`${BASE}/${id}`);
  if (!resp.ok) throw new Error("Failed to fetch agent type");
  return resp.json();
}

export async function createAgentType(
  data: Partial<AgentType>,
): Promise<AgentType> {
  const resp = await apiFetch(BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!resp.ok) throw new Error("Failed to create agent type");
  return resp.json();
}

export async function updateAgentType(
  id: string,
  data: Partial<AgentType>,
): Promise<AgentType> {
  const resp = await apiFetch(`${BASE}/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!resp.ok) throw new Error("Failed to update agent type");
  return resp.json();
}

export async function deleteAgentType(id: string): Promise<void> {
  const resp = await apiFetch(`${BASE}/${id}`, { method: "DELETE" });
  if (!resp.ok) throw new Error("Failed to delete agent type");
}
