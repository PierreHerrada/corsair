import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { AgentLog } from "../../types";
import AgentLogViewer from "../AgentLogViewer";

function makeLog(overrides: Partial<AgentLog> = {}): AgentLog {
  return {
    id: "l1",
    run_id: "r1",
    type: "text",
    content: { message: "Hello world" },
    created_at: "2025-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("AgentLogViewer", () => {
  it("shows 'No logs yet...' when empty", () => {
    render(<AgentLogViewer logs={[]} connected={false} />);
    expect(screen.getByText("No logs yet...")).toBeInTheDocument();
  });

  it("shows Live status when connected", () => {
    render(<AgentLogViewer logs={[]} connected={true} />);
    expect(screen.getByText("Live")).toBeInTheDocument();
  });

  it("shows Stored status when not connected", () => {
    render(<AgentLogViewer logs={[]} connected={false} />);
    expect(screen.getByText("Stored")).toBeInTheDocument();
  });

  it("renders log entries with message content", () => {
    const logs = [
      makeLog({ id: "l1", content: { message: "Starting plan" } }),
      makeLog({ id: "l2", type: "tool_use", content: { message: "Using tool X" } }),
    ];
    render(<AgentLogViewer logs={logs} connected={true} />);
    expect(screen.getByText("Starting plan")).toBeInTheDocument();
    expect(screen.getByText("Using tool X")).toBeInTheDocument();
  });

  it("renders log type prefixes", () => {
    const logs = [
      makeLog({ id: "l1", type: "tool_use", content: { message: "Read file" } }),
      makeLog({ id: "l2", type: "error", content: { message: "Oops" } }),
    ];
    render(<AgentLogViewer logs={logs} connected={true} />);
    expect(screen.getByText("TOOL")).toBeInTheDocument();
    expect(screen.getByText("ERROR")).toBeInTheDocument();
  });

  it("shows JSON for non-message content", () => {
    const logs = [
      makeLog({ id: "l1", content: { key: "value" } }),
    ];
    render(<AgentLogViewer logs={logs} connected={true} />);
    expect(screen.getByText('{"key":"value"}')).toBeInTheDocument();
  });

  it("renders the Agent Logs header with count", () => {
    render(<AgentLogViewer logs={[]} connected={false} />);
    expect(screen.getByText("Agent Logs (0)")).toBeInTheDocument();
  });
});
