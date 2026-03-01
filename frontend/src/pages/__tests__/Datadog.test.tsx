import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Datadog from "../Datadog";

vi.mock("../../api/datadog", () => ({
  fetchAnalyses: vi.fn(),
  fetchAnalysis: vi.fn(),
  triggerAnalysis: vi.fn(),
}));

import { fetchAnalyses, fetchAnalysis, triggerAnalysis } from "../../api/datadog";

describe("Datadog", () => {
  it("shows loading state initially", () => {
    vi.mocked(fetchAnalyses).mockReturnValue(new Promise(() => {}));
    render(<Datadog />);
    expect(screen.getByText("Loading analyses...")).toBeInTheDocument();
  });

  it("shows empty state when no analyses", async () => {
    vi.mocked(fetchAnalyses).mockResolvedValueOnce({
      total: 0,
      offset: 0,
      limit: 20,
      analyses: [],
    });
    render(<Datadog />);
    await waitFor(() => {
      expect(screen.getByText(/No analyses yet/)).toBeInTheDocument();
    });
  });

  it("renders analyses after loading", async () => {
    vi.mocked(fetchAnalyses).mockResolvedValueOnce({
      total: 1,
      offset: 0,
      limit: 20,
      analyses: [
        {
          id: "a1",
          source: "manual",
          trigger: "service:web status:error",
          status: "done",
          query: "service:web",
          trace_id: null,
          log_count: 5,
          raw_logs: [],
          raw_trace: [],
          summary: "Test summary",
          error_message: null,
          created_at: "2025-01-01T00:00:00Z",
        },
      ],
    });
    render(<Datadog />);
    await waitFor(() => {
      expect(screen.getByText("Datadog Analysis")).toBeInTheDocument();
      expect(screen.getByText("service:web status:error")).toBeInTheDocument();
      expect(screen.getByText("done")).toBeInTheDocument();
      expect(screen.getByText("manual")).toBeInTheDocument();
      expect(screen.getByText("5 logs")).toBeInTheDocument();
    });
  });

  it("shows error when fetch fails", async () => {
    vi.mocked(fetchAnalyses).mockRejectedValueOnce(new Error("Network error"));
    render(<Datadog />);
    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });

  it("triggers analysis on button click", async () => {
    vi.mocked(fetchAnalyses).mockResolvedValue({
      total: 0,
      offset: 0,
      limit: 20,
      analyses: [],
    });
    vi.mocked(triggerAnalysis).mockResolvedValueOnce({
      id: "new",
      source: "manual",
      trigger: "service:api",
      status: "pending",
      query: "service:api",
      trace_id: null,
      log_count: 0,
      raw_logs: [],
      raw_trace: [],
      summary: "",
      error_message: null,
      created_at: "2025-01-01T00:00:00Z",
    });

    render(<Datadog />);
    await waitFor(() => {
      expect(screen.getByText(/No analyses yet/)).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/Paste a Datadog URL/);
    fireEvent.change(input, { target: { value: "service:api" } });
    fireEvent.click(screen.getByText("Analyze"));

    await waitFor(() => {
      expect(triggerAnalysis).toHaveBeenCalledWith({ query: "service:api" });
    });
  });

  it("shows detail when analysis is selected", async () => {
    vi.mocked(fetchAnalyses).mockResolvedValueOnce({
      total: 1,
      offset: 0,
      limit: 20,
      analyses: [
        {
          id: "a1",
          source: "manual",
          trigger: "test",
          status: "done",
          query: "service:web",
          trace_id: null,
          log_count: 1,
          raw_logs: [],
          raw_trace: [],
          summary: "Test summary",
          error_message: null,
          created_at: "2025-01-01T00:00:00Z",
        },
      ],
    });
    vi.mocked(fetchAnalysis).mockResolvedValueOnce({
      id: "a1",
      source: "manual",
      trigger: "test",
      status: "done",
      query: "service:web",
      trace_id: null,
      log_count: 1,
      raw_logs: [],
      raw_trace: [],
      summary: "Detailed analysis summary here",
      error_message: null,
      created_at: "2025-01-01T00:00:00Z",
    });

    render(<Datadog />);

    await waitFor(() => {
      expect(screen.getByText("test")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("test"));

    await waitFor(() => {
      expect(screen.getByText("Analysis Detail")).toBeInTheDocument();
      expect(screen.getByText("Detailed analysis summary here")).toBeInTheDocument();
    });
  });
});
