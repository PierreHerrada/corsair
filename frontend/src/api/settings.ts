import type { SettingResponse } from "../types";
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
