import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Settings from "../Settings";

vi.mock("../../api/settings", () => ({
  fetchSetting: vi.fn(),
  updateSetting: vi.fn(),
}));

import { fetchSetting, updateSetting } from "../../api/settings";

describe("Settings", () => {
  it("shows loading state initially", () => {
    vi.mocked(fetchSetting).mockReturnValue(new Promise(() => {}));
    render(<Settings />);
    expect(screen.getByText("Loading settings...")).toBeInTheDocument();
  });

  it("renders settings page after loading", async () => {
    vi.mocked(fetchSetting).mockResolvedValueOnce({
      key: "base_prompt",
      value: "Test prompt",
      updated_at: null,
    });
    render(<Settings />);
    await waitFor(() => {
      expect(screen.getByText("Settings")).toBeInTheDocument();
      expect(screen.getByText("Base Prompt")).toBeInTheDocument();
    });
  });

  it("displays fetched value in textarea", async () => {
    vi.mocked(fetchSetting).mockResolvedValueOnce({
      key: "base_prompt",
      value: "My custom prompt",
      updated_at: "2026-03-02T00:00:00Z",
    });
    render(<Settings />);
    await waitFor(() => {
      const textarea = screen.getByRole("textbox");
      expect(textarea).toHaveValue("My custom prompt");
    });
  });

  it("saves setting on button click", async () => {
    vi.mocked(fetchSetting).mockResolvedValueOnce({
      key: "base_prompt",
      value: "",
      updated_at: null,
    });
    vi.mocked(updateSetting).mockResolvedValueOnce({
      key: "base_prompt",
      value: "",
      updated_at: "2026-03-02T12:00:00Z",
    });
    render(<Settings />);
    await waitFor(() => {
      expect(screen.getByText("Save")).toBeInTheDocument();
    });
    await userEvent.click(screen.getByText("Save"));
    await waitFor(() => {
      expect(updateSetting).toHaveBeenCalledWith("base_prompt", "");
    });
  });

  it("shows error when fetch fails", async () => {
    vi.mocked(fetchSetting).mockRejectedValueOnce(
      new Error("Failed to fetch setting"),
    );
    render(<Settings />);
    await waitFor(() => {
      expect(
        screen.getByText("Failed to fetch setting"),
      ).toBeInTheDocument();
    });
  });

  it("shows last saved timestamp", async () => {
    vi.mocked(fetchSetting).mockResolvedValueOnce({
      key: "base_prompt",
      value: "prompt",
      updated_at: "2026-03-02T10:30:00Z",
    });
    render(<Settings />);
    await waitFor(() => {
      expect(screen.getByText(/Last saved:/)).toBeInTheDocument();
    });
  });
});
