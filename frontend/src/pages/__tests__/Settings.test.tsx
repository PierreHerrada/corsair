import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Settings from "../Settings";

vi.mock("../../api/settings", () => ({
  fetchSetting: vi.fn(),
  updateSetting: vi.fn(),
  fetchSettingHistory: vi.fn(),
}));

vi.mock("../../api/repositories", () => ({
  fetchRepositories: vi.fn(),
  syncRepositories: vi.fn(),
  toggleRepository: vi.fn(),
}));

import {
  fetchSetting,
  fetchSettingHistory,
  updateSetting,
} from "../../api/settings";
import {
  fetchRepositories,
  syncRepositories,
  toggleRepository,
} from "../../api/repositories";

const emptySettingResponse = (key: string) => ({
  key,
  value: "",
  updated_at: null,
});

function mockDefaults() {
  vi.mocked(fetchSetting).mockImplementation(async (key: string) =>
    emptySettingResponse(key),
  );
  vi.mocked(fetchRepositories).mockResolvedValue([]);
  vi.mocked(fetchSettingHistory).mockResolvedValue({
    total: 0,
    offset: 0,
    limit: 50,
    entries: [],
  });
}

describe("Settings", () => {
  it("shows loading state initially", () => {
    vi.mocked(fetchSetting).mockReturnValue(new Promise(() => {}));
    vi.mocked(fetchRepositories).mockResolvedValue([]);
    render(<Settings />);
    expect(screen.getByText("Loading settings...")).toBeInTheDocument();
  });

  it("renders settings page after loading", async () => {
    mockDefaults();
    render(<Settings />);
    await waitFor(() => {
      expect(screen.getByText("Settings")).toBeInTheDocument();
      expect(screen.getByText("Base Prompt")).toBeInTheDocument();
    });
  });

  it("displays fetched value in textarea", async () => {
    vi.mocked(fetchSetting).mockImplementation(async (key: string) => {
      if (key === "base_prompt")
        return {
          key: "base_prompt",
          value: "My custom prompt",
          updated_at: "2026-03-02T00:00:00Z",
        };
      return emptySettingResponse(key);
    });
    vi.mocked(fetchRepositories).mockResolvedValue([]);
    vi.mocked(fetchSettingHistory).mockResolvedValue({
      total: 0,
      offset: 0,
      limit: 50,
      entries: [],
    });
    render(<Settings />);
    await waitFor(() => {
      const textareas = screen.getAllByRole("textbox");
      expect(textareas[0]).toHaveValue("My custom prompt");
    });
  });

  it("saves setting on button click", async () => {
    mockDefaults();
    vi.mocked(updateSetting).mockResolvedValueOnce({
      key: "base_prompt",
      value: "",
      updated_at: "2026-03-02T12:00:00Z",
    });
    render(<Settings />);
    await waitFor(() => {
      expect(screen.getAllByText("Save").length).toBeGreaterThan(0);
    });
    await userEvent.click(screen.getAllByText("Save")[0]);
    await waitFor(() => {
      expect(updateSetting).toHaveBeenCalledWith("base_prompt", "");
    });
  });

  it("shows error when fetch fails", async () => {
    vi.mocked(fetchSetting).mockRejectedValueOnce(
      new Error("Failed to fetch setting"),
    );
    // Subsequent calls for skills/subagents/lessons should still work
    vi.mocked(fetchSetting).mockImplementation(async (key: string) =>
      emptySettingResponse(key),
    );
    vi.mocked(fetchRepositories).mockResolvedValue([]);
    vi.mocked(fetchSettingHistory).mockResolvedValue({
      total: 0,
      offset: 0,
      limit: 50,
      entries: [],
    });
    render(<Settings />);
    await waitFor(() => {
      expect(
        screen.getByText("Failed to fetch setting"),
      ).toBeInTheDocument();
    });
  });

  it("shows last saved timestamp", async () => {
    vi.mocked(fetchSetting).mockImplementation(async (key: string) => {
      if (key === "base_prompt")
        return {
          key: "base_prompt",
          value: "prompt",
          updated_at: "2026-03-02T10:30:00Z",
        };
      return emptySettingResponse(key);
    });
    vi.mocked(fetchRepositories).mockResolvedValue([]);
    vi.mocked(fetchSettingHistory).mockResolvedValue({
      total: 0,
      offset: 0,
      limit: 50,
      entries: [],
    });
    render(<Settings />);
    await waitFor(() => {
      expect(screen.getAllByText(/Last saved:/).length).toBeGreaterThan(0);
    });
  });

  it("renders repos table with data", async () => {
    mockDefaults();
    vi.mocked(fetchRepositories).mockResolvedValueOnce([
      {
        id: "repo-1",
        full_name: "org/repo-1",
        name: "repo-1",
        description: "First repo",
        private: false,
        enabled: true,
        default_branch: "main",
        github_url: "https://github.com/org/repo-1",
        last_synced_at: null,
        created_at: "2026-03-02T00:00:00Z",
        updated_at: "2026-03-02T00:00:00Z",
      },
    ]);
    render(<Settings />);
    await waitFor(() => {
      expect(screen.getByText("org/repo-1")).toBeInTheDocument();
      expect(screen.getByText("First repo")).toBeInTheDocument();
      expect(screen.getByText("Public")).toBeInTheDocument();
    });
  });

  it("shows empty state when no repos", async () => {
    mockDefaults();
    render(<Settings />);
    await waitFor(() => {
      expect(
        screen.getByText(/No repositories found/),
      ).toBeInTheDocument();
    });
  });

  it("calls sync on button click", async () => {
    mockDefaults();
    vi.mocked(syncRepositories).mockResolvedValueOnce({
      created: 2,
      updated: 0,
      total: 2,
    });
    // After sync, reload returns repos
    vi.mocked(fetchRepositories)
      .mockResolvedValueOnce([]) // initial load
      .mockResolvedValueOnce([
        {
          id: "repo-1",
          full_name: "org/repo-1",
          name: "repo-1",
          description: "",
          private: false,
          enabled: false,
          default_branch: "main",
          github_url: "https://github.com/org/repo-1",
          last_synced_at: "2026-03-02T00:00:00Z",
          created_at: "2026-03-02T00:00:00Z",
          updated_at: "2026-03-02T00:00:00Z",
        },
      ]);
    render(<Settings />);
    await waitFor(() => {
      expect(screen.getByText("Sync from GitHub")).toBeInTheDocument();
    });
    await userEvent.click(screen.getByText("Sync from GitHub"));
    await waitFor(() => {
      expect(syncRepositories).toHaveBeenCalled();
    });
  });

  it("calls toggle on switch click", async () => {
    mockDefaults();
    vi.mocked(fetchRepositories).mockResolvedValueOnce([
      {
        id: "repo-1",
        full_name: "org/repo-1",
        name: "repo-1",
        description: "",
        private: false,
        enabled: false,
        default_branch: "main",
        github_url: "https://github.com/org/repo-1",
        last_synced_at: null,
        created_at: "2026-03-02T00:00:00Z",
        updated_at: "2026-03-02T00:00:00Z",
      },
    ]);
    vi.mocked(toggleRepository).mockResolvedValueOnce({
      id: "repo-1",
      full_name: "org/repo-1",
      name: "repo-1",
      description: "",
      private: false,
      enabled: true,
      default_branch: "main",
      github_url: "https://github.com/org/repo-1",
      last_synced_at: null,
      created_at: "2026-03-02T00:00:00Z",
      updated_at: "2026-03-02T00:00:00Z",
    });
    render(<Settings />);
    await waitFor(() => {
      expect(screen.getByRole("switch")).toBeInTheDocument();
    });
    await userEvent.click(screen.getByRole("switch"));
    await waitFor(() => {
      expect(toggleRepository).toHaveBeenCalledWith("repo-1", true);
    });
  });

  it("renders skills card", async () => {
    mockDefaults();
    render(<Settings />);
    await waitFor(() => {
      expect(screen.getByText("Skills")).toBeInTheDocument();
      expect(
        screen.getByText(/\.claude\/skills\/\{name\}\.md/),
      ).toBeInTheDocument();
    });
  });

  it("renders subagents card", async () => {
    mockDefaults();
    render(<Settings />);
    await waitFor(() => {
      expect(screen.getByText("Subagents")).toBeInTheDocument();
      expect(
        screen.getByText(/\.claude\/agents\/\{name\}\.md/),
      ).toBeInTheDocument();
    });
  });

  it("renders lessons card", async () => {
    mockDefaults();
    render(<Settings />);
    await waitFor(() => {
      expect(screen.getByText("Lessons")).toBeInTheDocument();
      expect(screen.getByText(/LESSONS\.md/)).toBeInTheDocument();
    });
  });

  it("adds and removes skill items", async () => {
    mockDefaults();
    render(<Settings />);
    await waitFor(() => {
      expect(screen.getByText("Skills")).toBeInTheDocument();
    });
    // Click the Add button in the Skills section
    const addButtons = screen.getAllByText("+ Add");
    await userEvent.click(addButtons[0]);
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Name (used as filename)")).toBeInTheDocument();
    });
    // Remove it
    await userEvent.click(screen.getAllByText("Remove")[0]);
    await waitFor(() => {
      expect(screen.queryByPlaceholderText("Name (used as filename)")).not.toBeInTheDocument();
    });
  });

  it("renders max active agents section", async () => {
    mockDefaults();
    render(<Settings />);
    await waitFor(() => {
      expect(screen.getByText("Max Active Agents")).toBeInTheDocument();
      expect(
        screen.getByText("Set to 0 or leave empty for unlimited"),
      ).toBeInTheDocument();
    });
  });

  it("displays fetched max active agents value", async () => {
    vi.mocked(fetchSetting).mockImplementation(async (key: string) => {
      if (key === "max_active_agents")
        return {
          key: "max_active_agents",
          value: "3",
          updated_at: "2026-03-02T00:00:00Z",
        };
      return emptySettingResponse(key);
    });
    vi.mocked(fetchRepositories).mockResolvedValue([]);
    vi.mocked(fetchSettingHistory).mockResolvedValue({
      total: 0,
      offset: 0,
      limit: 50,
      entries: [],
    });
    render(<Settings />);
    await waitFor(() => {
      const input = screen.getByDisplayValue("3");
      expect(input).toBeInTheDocument();
      expect(input).toHaveAttribute("type", "number");
    });
  });

  it("saves max active agents on button click", async () => {
    vi.mocked(fetchSetting).mockImplementation(async (key: string) => {
      if (key === "max_active_agents")
        return {
          key: "max_active_agents",
          value: "5",
          updated_at: null,
        };
      return emptySettingResponse(key);
    });
    vi.mocked(fetchRepositories).mockResolvedValue([]);
    vi.mocked(fetchSettingHistory).mockResolvedValue({
      total: 0,
      offset: 0,
      limit: 50,
      entries: [],
    });
    vi.mocked(updateSetting).mockResolvedValue({
      key: "max_active_agents",
      value: "5",
      updated_at: "2026-03-02T12:00:00Z",
    });
    render(<Settings />);
    await waitFor(() => {
      expect(screen.getByText("Max Active Agents")).toBeInTheDocument();
    });
    // Find all Save buttons — the one for Max Active Agents section
    const saveButtons = screen.getAllByText("Save");
    // Click the Save button in the Max Active Agents section (second Save after base prompt)
    await userEvent.click(saveButtons[1]);
    await waitFor(() => {
      expect(updateSetting).toHaveBeenCalledWith("max_active_agents", "5");
    });
  });

  it("shows lessons history panel", async () => {
    mockDefaults();
    render(<Settings />);
    await waitFor(() => {
      expect(screen.getByText("Show change history")).toBeInTheDocument();
    });
    await userEvent.click(screen.getByText("Show change history"));
    await waitFor(() => {
      expect(screen.getByText("No history yet.")).toBeInTheDocument();
    });
  });
});
