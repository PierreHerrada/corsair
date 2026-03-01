import type { CostBreakdown, DashboardStats } from "../types";
import { apiFetch } from "./client";

const BASE = "/api/v1";

export async function fetchStats(): Promise<DashboardStats> {
  const resp = await apiFetch(`${BASE}/dashboard/stats`);
  if (!resp.ok) throw new Error("Failed to fetch stats");
  return resp.json();
}

export async function fetchCosts(): Promise<CostBreakdown[]> {
  const resp = await apiFetch(`${BASE}/dashboard/costs`);
  if (!resp.ok) throw new Error("Failed to fetch costs");
  return resp.json();
}
