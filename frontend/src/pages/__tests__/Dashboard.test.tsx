import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import Dashboard from "../Dashboard";

vi.mock("../../api/dashboard", () => ({
  fetchStats: vi.fn(),
  fetchCosts: vi.fn(),
}));

vi.mock("../../api/tasks", () => ({
  fetchTasks: vi.fn(),
  stopTask: vi.fn(),
}));

import { fetchCosts, fetchStats } from "../../api/dashboard";
import { fetchTasks } from "../../api/tasks";

function renderDashboard() {
  return render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>,
  );
}

const defaultStats = {
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
  cost_by_stage: { plan: 1.5, work: 3.0, review: 1.0, investigate: 0 },
};

afterEach(() => { vi.restoreAllMocks(); });

describe("Dashboard", () => {
  it("shows loading state initially", () => {
    vi.mocked(fetchStats).mockReturnValue(new Promise(() => {}));
    vi.mocked(fetchCosts).mockReturnValue(new Promise(() => {}));
    vi.mocked(fetchTasks).mockResolvedValue([]);
    renderDashboard();
    expect(screen.getByText("Loading dashboard...")).toBeInTheDocument();
  });

  it("renders dashboard data after loading", async () => {
    vi.mocked(fetchStats).mockResolvedValue(defaultStats);
    vi.mocked(fetchCosts).mockResolvedValue([]);
    vi.mocked(fetchTasks).mockResolvedValue([]);
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText("Dashboard")).toBeInTheDocument();
      expect(screen.getByText("$5.50")).toBeInTheDocument();
      expect(screen.getByText("2")).toBeInTheDocument();
    });
  });

  it("shows error when fetch fails", async () => {
    vi.mocked(fetchStats).mockRejectedValue(new Error("Server error"));
    vi.mocked(fetchCosts).mockRejectedValue(new Error("Server error"));
    vi.mocked(fetchTasks).mockResolvedValue([]);
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText("Server error")).toBeInTheDocument();
    });
  });

  it("renders active agents section when tasks are running", async () => {
    vi.mocked(fetchStats).mockResolvedValue(defaultStats);
    vi.mocked(fetchCosts).mockResolvedValue([]);
    vi.mocked(fetchTasks).mockResolvedValue([
      {
        id: "t1",
        title: "Running task",
        description: "",
        acceptance: "",
        status: "working",
        jira_key: "PROJ-1",
        jira_url: null,
        slack_thread_ts: "",
        pr_url: null,
        pr_number: null,
        repo: null,
        analysis: "",
        created_at: "2025-01-01T00:00:00Z",
        latest_run: {
          id: "r1",
          task_id: "t1",
          stage: "work",
          status: "running",
          tokens_in: 100,
          tokens_out: 50,
          cost_usd: 0.005,
          started_at: new Date(Date.now() - 60_000).toISOString(),
          finished_at: null,
          workspace_path: null,
          file_tree: null,
        },
      },
    ]);
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText("Active Agents")).toBeInTheDocument();
      expect(screen.getByText("Running task")).toBeInTheDocument();
      expect(screen.getByText("PROJ-1")).toBeInTheDocument();
      // Use getAllByText and check the first occurrence (in the active agent row)
      const workElements = screen.getAllByText("work");
      expect(workElements.length).toBeGreaterThan(0);
      expect(screen.getByText("Stop")).toBeInTheDocument();
    });
  });

  it("hides active agents section when no tasks are running", async () => {
    vi.mocked(fetchStats).mockResolvedValue(defaultStats);
    vi.mocked(fetchCosts).mockResolvedValue([]);
    vi.mocked(fetchTasks).mockResolvedValue([
      {
        id: "t1",
        title: "Done task",
        description: "",
        acceptance: "",
        status: "done",
        jira_key: null,
        jira_url: null,
        slack_thread_ts: "",
        pr_url: null,
        pr_number: null,
        repo: null,
        analysis: "",
        created_at: "2025-01-01T00:00:00Z",
        latest_run: {
          id: "r1",
          task_id: "t1",
          stage: "work",
          status: "done",
          tokens_in: 100,
          tokens_out: 50,
          cost_usd: 0.005,
          started_at: "2025-01-01T00:00:00Z",
          finished_at: "2025-01-01T00:01:00Z",
          workspace_path: null,
          file_tree: null,
        },
      },
    ]);
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText("Dashboard")).toBeInTheDocument();
    });
    expect(screen.queryByText("Active Agents")).not.toBeInTheDocument();
  });
});
