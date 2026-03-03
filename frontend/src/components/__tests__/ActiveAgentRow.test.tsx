import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { Task } from "../../types";
import ActiveAgentRow from "../ActiveAgentRow";

vi.mock("../../api/tasks", () => ({
  stopTask: vi.fn(),
}));

import { stopTask } from "../../api/tasks";

function makeRunningTask(overrides: Partial<Task> = {}): Task {
  return {
    id: "t1",
    title: "Implement auth",
    description: "",
    acceptance: "",
    status: "working",
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
      status: "running",
      tokens_in: 500,
      tokens_out: 200,
      cost_usd: 0.0123,
      started_at: new Date(Date.now() - 120_000).toISOString(),
      finished_at: null,
      workspace_path: null,
      file_tree: null,
    },
    ...overrides,
  };
}

function renderRow(task: Task, onStopped = vi.fn()) {
  return render(
    <MemoryRouter>
      <table>
        <tbody>
          <ActiveAgentRow task={task} onStopped={onStopped} />
        </tbody>
      </table>
    </MemoryRouter>,
  );
}

describe("ActiveAgentRow", () => {
  it("renders task title as a link", () => {
    renderRow(makeRunningTask());
    const link = screen.getByText("Implement auth");
    expect(link.closest("a")).toHaveAttribute("href", "/tasks/t1");
  });

  it("shows jira key when present", () => {
    renderRow(makeRunningTask({ jira_key: "PROJ-99" }));
    expect(screen.getByText("PROJ-99")).toBeInTheDocument();
  });

  it("shows stage badge", () => {
    renderRow(makeRunningTask());
    expect(screen.getByText("work")).toBeInTheDocument();
  });

  it("shows cost", () => {
    renderRow(makeRunningTask());
    expect(screen.getByText("$0.0123")).toBeInTheDocument();
  });

  it("calls stopTask and onStopped when stop button clicked", async () => {
    vi.mocked(stopTask).mockResolvedValueOnce({
      id: "r1",
      task_id: "t1",
      stage: "work",
      status: "done",
      tokens_in: 500,
      tokens_out: 200,
      cost_usd: 0.0123,
      started_at: "2025-01-01T00:00:00Z",
      finished_at: "2025-01-01T00:02:00Z",
      workspace_path: null,
      file_tree: null,
    });
    const onStopped = vi.fn();
    renderRow(makeRunningTask(), onStopped);
    await userEvent.click(screen.getByText("Stop"));
    expect(stopTask).toHaveBeenCalledWith("t1");
    expect(onStopped).toHaveBeenCalled();
  });

  it("disables button while stopping", async () => {
    vi.mocked(stopTask).mockReturnValue(new Promise(() => {}));
    renderRow(makeRunningTask());
    await userEvent.click(screen.getByText("Stop"));
    expect(screen.getByText("Stopping...")).toBeInTheDocument();
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
