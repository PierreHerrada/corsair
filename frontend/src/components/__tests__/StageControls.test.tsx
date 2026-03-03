import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { stopTask, triggerStage } from "../../api/tasks";
import type { Task } from "../../types";
import StageControls from "../StageControls";

vi.mock("../../api/tasks", () => ({
  triggerStage: vi.fn(),
  stopTask: vi.fn(),
  retryTask: vi.fn(),
}));

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: "t1",
    title: "Task 1",
    description: "",
    acceptance: "",
    status: "backlog",
    jira_key: null,
    jira_url: null,
    slack_thread_ts: "",
    pr_url: null,
    pr_number: null,
    repo: null,
    analysis: "",
    created_at: "2025-01-01T00:00:00Z",
    latest_run: null,
    ...overrides,
  };
}

describe("StageControls", () => {
  it('shows "Run Plan" for backlog tasks', () => {
    render(
      <StageControls task={makeTask({ status: "backlog" })} onRefresh={vi.fn()} />
    );
    expect(screen.getByText("Run Plan")).toBeInTheDocument();
  });

  it('shows "Run Work" for planned tasks', () => {
    render(
      <StageControls task={makeTask({ status: "planned" })} onRefresh={vi.fn()} />
    );
    expect(screen.getByText("Run Work")).toBeInTheDocument();
  });

  it('shows "Run Review" for working tasks', () => {
    render(
      <StageControls task={makeTask({ status: "working" })} onRefresh={vi.fn()} />
    );
    expect(screen.getByText("Run Review")).toBeInTheDocument();
  });

  it("shows no buttons for done tasks", () => {
    render(
      <StageControls task={makeTask({ status: "done" })} onRefresh={vi.fn()} />
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("shows Retry button for failed tasks", () => {
    render(
      <StageControls task={makeTask({ status: "failed" })} onRefresh={vi.fn()} />
    );
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("calls triggerStage and onRefresh when clicked", async () => {
    const onRefresh = vi.fn();
    vi.mocked(triggerStage).mockResolvedValueOnce({
      id: "r1",
      task_id: "t1",
      stage: "plan",
      status: "running",
      tokens_in: 0,
      tokens_out: 0,
      cost_usd: 0,
      started_at: "2025-01-01T00:00:00Z",
      finished_at: null,
      workspace_path: null,
      file_tree: null,
    });

    render(
      <StageControls task={makeTask({ status: "backlog" })} onRefresh={onRefresh} />
    );

    fireEvent.click(screen.getByText("Run Plan"));

    await waitFor(() => {
      expect(triggerStage).toHaveBeenCalledWith("t1", "plan");
      expect(onRefresh).toHaveBeenCalled();
    });
  });

  it("shows Stop button when a run is active", () => {
    render(
      <StageControls
        task={makeTask({
          status: "backlog",
          latest_run: {
            id: "r1",
            task_id: "t1",
            stage: "plan",
            status: "running",
            tokens_in: 0,
            tokens_out: 0,
            cost_usd: 0,
            started_at: "2025-01-01T00:00:00Z",
            finished_at: null,
            workspace_path: null,
            file_tree: null,
          },
        })}
        onRefresh={vi.fn()}
      />
    );
    expect(screen.getByText("Stop")).toBeInTheDocument();
  });

  it("does not show Stop button when no run is active", () => {
    render(
      <StageControls task={makeTask({ status: "backlog" })} onRefresh={vi.fn()} />
    );
    expect(screen.queryByText("Stop")).not.toBeInTheDocument();
  });

  it("calls stopTask and onRefresh when Stop is clicked", async () => {
    const onRefresh = vi.fn();
    vi.mocked(stopTask).mockResolvedValueOnce({
      id: "r1",
      task_id: "t1",
      stage: "plan",
      status: "running",
      tokens_in: 0,
      tokens_out: 0,
      cost_usd: 0,
      started_at: "2025-01-01T00:00:00Z",
      finished_at: null,
      workspace_path: null,
      file_tree: null,
    });

    render(
      <StageControls
        task={makeTask({
          status: "backlog",
          latest_run: {
            id: "r1",
            task_id: "t1",
            stage: "plan",
            status: "running",
            tokens_in: 0,
            tokens_out: 0,
            cost_usd: 0,
            started_at: "2025-01-01T00:00:00Z",
            finished_at: null,
            workspace_path: null,
            file_tree: null,
          },
        })}
        onRefresh={onRefresh}
      />
    );

    fireEvent.click(screen.getByText("Stop"));

    await waitFor(() => {
      expect(stopTask).toHaveBeenCalledWith("t1");
      expect(onRefresh).toHaveBeenCalled();
    });
  });

  it("disables button when a run is active", () => {
    render(
      <StageControls
        task={makeTask({
          status: "backlog",
          latest_run: {
            id: "r1",
            task_id: "t1",
            stage: "plan",
            status: "running",
            tokens_in: 0,
            tokens_out: 0,
            cost_usd: 0,
            started_at: "2025-01-01T00:00:00Z",
            finished_at: null,
            workspace_path: null,
            file_tree: null,
          },
        })}
        onRefresh={vi.fn()}
      />
    );
    expect(screen.getByText("Run Plan")).toBeDisabled();
  });
});
