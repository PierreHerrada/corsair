import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Board from "../Board";

vi.mock("../../api/tasks", () => ({
  fetchTasks: vi.fn(),
  triggerStage: vi.fn(),
}));

import { fetchTasks } from "../../api/tasks";

describe("Board", () => {
  it("shows loading state initially", () => {
    vi.mocked(fetchTasks).mockReturnValue(new Promise(() => {}));
    render(<Board />);
    expect(screen.getByText("Loading tasks...")).toBeInTheDocument();
  });

  it("renders task board after loading", async () => {
    vi.mocked(fetchTasks).mockResolvedValueOnce([
      {
        id: "t1",
        title: "Test task",
        description: "",
        acceptance: "",
        status: "backlog",
        jira_key: null,
        jira_url: null,
        slack_thread_ts: "",
        pr_url: null,
        pr_number: null,
        repo: null,
        created_at: "2025-01-01T00:00:00Z",
        latest_run: null,
      },
    ]);
    render(<Board />);
    await waitFor(() => {
      expect(screen.getByText("Task Board")).toBeInTheDocument();
      expect(screen.getByText("Test task")).toBeInTheDocument();
    });
  });

  it("shows error when fetch fails", async () => {
    vi.mocked(fetchTasks).mockRejectedValueOnce(new Error("Network error"));
    render(<Board />);
    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });

  it("renders the Refresh button", async () => {
    vi.mocked(fetchTasks).mockResolvedValueOnce([]);
    render(<Board />);
    await waitFor(() => {
      expect(screen.getByText("Refresh")).toBeInTheDocument();
    });
  });
});
