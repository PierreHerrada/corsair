import type { InternalLogsResponse } from "../types";
import { apiFetch } from "./client";

const BASE = "/api/v1";

export async function fetchLogs(
  limit: number = 100,
  offset: number = 0,
  source?: string,
  level?: string,
): Promise<InternalLogsResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (source) params.set("source", source);
  if (level) params.set("level", level);
  const resp = await apiFetch(`${BASE}/logs?${params}`);
  if (!resp.ok) throw new Error("Failed to fetch logs");
  return resp.json();
}
