import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Settings from "../Settings";

vi.mock("../../api/settings", () => ({
  fetchSetting: vi.fn(),
  updateSetting: vi.fn(),
  fetchSettingHistory: vi.fn(),
  fetchEnvVars: vi.fn(),
  updateEnvVars: vi.fn(),
}));

vi.mock("../../api/repositories", () => ({
  fetchRepositories: vi.fn(),
  syncRepositories: vi.fn(),
  toggleRepository: vi.fn(),
}));

import {
  fetchEnvVars,
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
  vi.mocked(fetchEnvVars).mockResolvedValue({
    items: [],
    updated_at: null,
  });
}

describe("Settings", () => {
  beforeEach(() => {
    vi.mocked(fetchEnvVars).mockResolvedValue({
      items: [],
      updated_at: null,
    });
  });

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
      expect(screen.getAllByRole("switch").length).toBeGreaterThanOrEqual(1);
    });
    // Find the repo toggle switch (inside the Repositories section)
    const switches = screen.getAllByRole("switch");
    const repoSwitch = switches.find((s) => {
      const row = s.closest("tr");
      return row !== null;
    });
    expect(repoSwitch).toBeDefined();
    await userEvent.click(repoSwitch!);
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
    // Click the Add button in the Skills section (after env vars + Add)
    const addButtons = screen.getAllByText("+ Add");
    // Find the one inside the Skills section
    const skillsAdd = addButtons.find((btn) => {
      const section = btn.closest(".bg-abyss");
      return section?.textContent?.includes("Skills");
    });
    expect(skillsAdd).toBeDefined();
    await userEvent.click(skillsAdd!);
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

  it("renders auto work toggle", async () => {
    mockDefaults();
    render(<Settings />);
    await waitFor(() => {
      expect(screen.getByText("Auto Work")).toBeInTheDocument();
      expect(
        screen.getByText(
          /Automatically trigger the work stage when a plan completes/,
        ),
      ).toBeInTheDocument();
    });
  });

  it("toggles auto work on click", async () => {
    mockDefaults();
    vi.mocked(updateSetting).mockResolvedValue({
      key: "auto_work",
      value: "true",
      updated_at: "2026-03-02T12:00:00Z",
    });
    render(<Settings />);
    await waitFor(() => {
      expect(screen.getByText("Auto Work")).toBeInTheDocument();
    });
    // Find the auto work toggle switch
    const switches = screen.getAllByRole("switch");
    // The auto work switch — find by checking parent context
    const autoWorkSwitch = switches.find((s) => {
      const parent = s.closest(".bg-abyss");
      return parent?.textContent?.includes("Auto Work");
    });
    expect(autoWorkSwitch).toBeDefined();
    await userEvent.click(autoWorkSwitch!);
    await waitFor(() => {
      expect(updateSetting).toHaveBeenCalledWith("auto_work", "true");
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
