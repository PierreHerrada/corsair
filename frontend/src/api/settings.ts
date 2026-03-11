import type { EnvVarsResponse, SettingHistoryResponse, SettingResponse } from "../types";
import { apiFetch } from "./client";

const BASE = "/api/v1";

export async function fetchSetting(key: string): Promise<SettingResponse> {
  const resp = await apiFetch(`${BASE}/settings/${key}`);
  if (!resp.ok) throw new Error("Failed to fetch setting");
  return resp.json();
}

export async function updateSetting(
  key: string,
  value: string,
): Promise<SettingResponse> {
  const resp = await apiFetch(`${BASE}/settings/${key}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value }),
  });
  if (!resp.ok) throw new Error("Failed to update setting");
  return resp.json();
}

export async function fetchSettingHistory(
  key: string,
  limit = 50,
  offset = 0,
): Promise<SettingHistoryResponse> {
  const resp = await apiFetch(
    `${BASE}/settings/${key}/history?limit=${limit}&offset=${offset}`,
  );
  if (!resp.ok) throw new Error("Failed to fetch setting history");
  return resp.json();
}

export async function fetchEnvVars(): Promise<EnvVarsResponse> {
  const resp = await apiFetch(`${BASE}/settings/env-vars`);
  if (!resp.ok) throw new Error("Failed to fetch env vars");
  return resp.json();
}

export async function updateEnvVars(
  items: { name: string; value: string }[],
): Promise<EnvVarsResponse> {
  const resp = await apiFetch(`${BASE}/settings/env-vars`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items }),
  });
  if (!resp.ok) throw new Error("Failed to update env vars");
  return resp.json();
}
