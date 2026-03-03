import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { Task } from "../../types";
import TaskCard from "../TaskCard";

vi.mock("../../api/tasks", () => ({
  triggerStage: vi.fn(),
}));

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: "t1",
    title: "Fix login bug",
    description: "Users cannot log in",
    acceptance: "Login works",
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

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("TaskCard", () => {
  it("renders task title and status", () => {
    renderWithRouter(<TaskCard task={makeTask()} onRefresh={vi.fn()} />);
    expect(screen.getByText("Fix login bug")).toBeInTheDocument();
    expect(screen.getByText("backlog")).toBeInTheDocument();
  });

  it("renders description when present", () => {
    renderWithRouter(<TaskCard task={makeTask()} onRefresh={vi.fn()} />);
    expect(screen.getByText("Users cannot log in")).toBeInTheDocument();
  });

  it("does not render description when empty", () => {
    renderWithRouter(
      <TaskCard task={makeTask({ description: "" })} onRefresh={vi.fn()} />,
    );
    expect(screen.queryByText("Users cannot log in")).not.toBeInTheDocument();
  });

  it("renders Jira link when jira_key is set", () => {
    renderWithRouter(
      <TaskCard
        task={makeTask({
          jira_key: "PROJ-42",
          jira_url: "https://jira.example.com/PROJ-42",
        })}
        onRefresh={vi.fn()}
      />,
    );
    const link = screen.getByText("PROJ-42");
    expect(link).toBeInTheDocument();
    expect(link.closest("a")).toHaveAttribute(
      "href",
      "https://jira.example.com/PROJ-42",
    );
  });

  it("does not render Jira link when jira_key is null", () => {
    renderWithRouter(<TaskCard task={makeTask()} onRefresh={vi.fn()} />);
    expect(screen.queryByText("PROJ-42")).not.toBeInTheDocument();
  });

  it("renders PR badge when pr_url is set", () => {
    renderWithRouter(
      <TaskCard
        task={makeTask({ pr_url: "https://github.com/pr/1", pr_number: 1 })}
        onRefresh={vi.fn()}
      />,
    );
    expect(screen.getByText("PR #1")).toBeInTheDocument();
  });

  it("shows latest run info when present", () => {
    renderWithRouter(
      <TaskCard
        task={makeTask({
          latest_run: {
            id: "r1",
            task_id: "t1",
            stage: "plan",
            status: "done",
            tokens_in: 100,
            tokens_out: 50,
            cost_usd: 0.0045,
            started_at: "2025-01-01T00:00:00Z",
            finished_at: "2025-01-01T00:01:00Z",
            workspace_path: null,
            file_tree: null,
          },
        })}
        onRefresh={vi.fn()}
      />,
    );
    expect(screen.getByText(/Last run: plan/)).toBeInTheDocument();
    expect(screen.getByText(/\$0\.0045/)).toBeInTheDocument();
  });
});
