import type { IntegrationHealth, IntegrationStatus } from "../types";
import { apiFetch } from "./client";

const BASE = "/api/v1";

export async function fetchIntegrations(): Promise<IntegrationStatus[]> {
  const resp = await apiFetch(`${BASE}/integrations`);
  if (!resp.ok) throw new Error("Failed to fetch integrations");
  return resp.json();
}

export async function fetchIntegrationHealth(): Promise<IntegrationHealth[]> {
  const resp = await apiFetch(`${BASE}/integrations/health`);
  if (!resp.ok) throw new Error("Failed to fetch integration health");
  return resp.json();
}
