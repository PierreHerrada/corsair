import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Dashboard from "../Dashboard";

vi.mock("../../api/dashboard", () => ({
  fetchStats: vi.fn(),
  fetchCosts: vi.fn(),
}));

import { fetchCosts, fetchStats } from "../../api/dashboard";

describe("Dashboard", () => {
  it("shows loading state initially", () => {
    vi.mocked(fetchStats).mockReturnValue(new Promise(() => {}));
    vi.mocked(fetchCosts).mockReturnValue(new Promise(() => {}));
    render(<Dashboard />);
    expect(screen.getByText("Loading dashboard...")).toBeInTheDocument();
  });

  it("renders dashboard data after loading", async () => {
    vi.mocked(fetchStats).mockResolvedValueOnce({
      total_cost_usd: 5.5,
      active_runs: 2,
      tasks_by_status: {
        backlog: 3,
        planned: 1,
        working: 2,
        reviewing: 0,
        done: 5,
        failed: 0,
      },
      cost_by_stage: { plan: 1.5, work: 3.0, review: 1.0 },
    });
    vi.mocked(fetchCosts).mockResolvedValueOnce([]);
    render(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText("Dashboard")).toBeInTheDocument();
      expect(screen.getByText("$5.50")).toBeInTheDocument();
      expect(screen.getByText("2")).toBeInTheDocument();
    });
  });

  it("shows error when fetch fails", async () => {
    vi.mocked(fetchStats).mockRejectedValueOnce(new Error("Server error"));
    vi.mocked(fetchCosts).mockRejectedValueOnce(new Error("Server error"));
    render(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText("Server error")).toBeInTheDocument();
    });
  });
});
