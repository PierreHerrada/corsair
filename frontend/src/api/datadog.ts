import type { DatadogAnalysesResponse, DatadogAnalysis } from "../types";
import { apiFetch } from "./client";

const BASE = "/api/v1/datadog";

export async function fetchAnalyses(
  limit: number = 20,
  offset: number = 0,
): Promise<DatadogAnalysesResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  const resp = await apiFetch(`${BASE}/analyses?${params}`);
  if (!resp.ok) throw new Error("Failed to fetch analyses");
  return resp.json();
}

export async function fetchAnalysis(id: string): Promise<DatadogAnalysis> {
  const resp = await apiFetch(`${BASE}/analyses/${id}`);
  if (!resp.ok) throw new Error("Failed to fetch analysis");
  return resp.json();
}

export async function triggerAnalysis(params: {
  url?: string;
  query?: string;
  trace_id?: string;
}): Promise<DatadogAnalysis> {
  const resp = await apiFetch(`${BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!resp.ok) throw new Error("Failed to trigger analysis");
  return resp.json();
}
