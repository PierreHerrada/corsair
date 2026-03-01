import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../api/datadog", () => ({
  fetchAnalyses: vi.fn(),
  fetchAnalysis: vi.fn(),
  triggerAnalysis: vi.fn(),
}));

import { fetchAnalyses, fetchAnalysis, triggerAnalysis } from "../../api/datadog";
import { useDatadog } from "../useDatadog";

describe("useDatadog", () => {
  it("loads analyses on mount", async () => {
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
          log_count: 5,
          raw_logs: [],
          raw_trace: [],
          summary: "Test summary",
          error_message: null,
          created_at: "2025-01-01T00:00:00Z",
        },
      ],
    });

    const { result } = renderHook(() => useDatadog());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.analyses).toHaveLength(1);
    expect(result.current.total).toBe(1);
    expect(result.current.analyses[0].id).toBe("a1");
  });

  it("handles fetch error", async () => {
    vi.mocked(fetchAnalyses).mockRejectedValueOnce(new Error("Network error"));

    const { result } = renderHook(() => useDatadog());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBe("Network error");
  });

  it("triggers analysis and refreshes", async () => {
    vi.mocked(fetchAnalyses).mockResolvedValue({
      total: 0,
      offset: 0,
      limit: 20,
      analyses: [],
    });
    vi.mocked(triggerAnalysis).mockResolvedValueOnce({
      id: "new",
      source: "manual",
      trigger: "query",
      status: "pending",
      query: "service:web",
      trace_id: null,
      log_count: 0,
      raw_logs: [],
      raw_trace: [],
      summary: "",
      error_message: null,
      created_at: "2025-01-01T00:00:00Z",
    });

    const { result } = renderHook(() => useDatadog());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.analyze({ query: "service:web" });
    });

    expect(triggerAnalysis).toHaveBeenCalledWith({ query: "service:web" });
    // Called on mount + refresh after analyze (may be more due to React batching)
    expect(vi.mocked(fetchAnalyses).mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("selects an analysis", async () => {
    vi.mocked(fetchAnalyses).mockResolvedValueOnce({
      total: 0,
      offset: 0,
      limit: 20,
      analyses: [],
    });
    vi.mocked(fetchAnalysis).mockResolvedValueOnce({
      id: "a1",
      source: "manual",
      trigger: "test",
      status: "done",
      query: "service:web",
      trace_id: null,
      log_count: 5,
      raw_logs: [{ attributes: { message: "error" } }],
      raw_trace: [],
      summary: "Test summary",
      error_message: null,
      created_at: "2025-01-01T00:00:00Z",
    });

    const { result } = renderHook(() => useDatadog());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.selectAnalysis("a1");
    });

    expect(result.current.selectedAnalysis).not.toBeNull();
    expect(result.current.selectedAnalysis?.id).toBe("a1");

    act(() => {
      result.current.clearSelection();
    });

    expect(result.current.selectedAnalysis).toBeNull();
  });
});
