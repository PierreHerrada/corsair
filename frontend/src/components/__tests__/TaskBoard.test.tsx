import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Task } from "../../types";
import TaskBoard from "../TaskBoard";

vi.mock("../../api/tasks", () => ({
  triggerStage: vi.fn(),
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
    created_at: "2025-01-01T00:00:00Z",
    latest_run: null,
    ...overrides,
  };
}

describe("TaskBoard", () => {
  it("renders all 6 columns", () => {
    render(<TaskBoard tasks={[]} onRefresh={vi.fn()} />);
    expect(screen.getByText("Backlog")).toBeInTheDocument();
    expect(screen.getByText("Planned")).toBeInTheDocument();
    expect(screen.getByText("Working")).toBeInTheDocument();
    expect(screen.getByText("Reviewing")).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("shows 'No tasks' for empty columns", () => {
    render(<TaskBoard tasks={[]} onRefresh={vi.fn()} />);
    const emptyMessages = screen.getAllByText("No tasks");
    expect(emptyMessages).toHaveLength(6);
  });

  it("places tasks in correct columns", () => {
    const tasks = [
      makeTask({ id: "1", title: "Backlog task", status: "backlog" }),
      makeTask({ id: "2", title: "Done task", status: "done" }),
      makeTask({ id: "3", title: "Working task", status: "working" }),
    ];
    render(<TaskBoard tasks={tasks} onRefresh={vi.fn()} />);
    expect(screen.getByText("Backlog task")).toBeInTheDocument();
    expect(screen.getByText("Done task")).toBeInTheDocument();
    expect(screen.getByText("Working task")).toBeInTheDocument();
  });

  it("shows correct task count per column", () => {
    const tasks = [
      makeTask({ id: "1", status: "backlog" }),
      makeTask({ id: "2", status: "backlog" }),
      makeTask({ id: "3", status: "done" }),
    ];
    render(<TaskBoard tasks={tasks} onRefresh={vi.fn()} />);
    // Backlog column should show "2", done shows "1", rest show "0"
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });
});
