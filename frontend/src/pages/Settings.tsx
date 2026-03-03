import { useState } from "react";
import LessonsEditor from "../components/LessonsEditor";
import NamedItemsEditor from "../components/NamedItemsEditor";
import { useRepositories } from "../hooks/useRepositories";
import {
  useBasePrompt,
  useLessons,
  useMaxActiveAgents,
  useSkills,
  useSubagents,
} from "../hooks/useSettings";

const EXAMPLE_TEMPLATE = `# Project — Agent Instructions

## Overview
<!-- What this repo is, in 1-2 sentences -->
A [web app / API / library] built with [tech stack].

## Tech Stack
- Language: [TypeScript / Python / Go / …]
- Framework: [React, FastAPI, Express, …]
- Database: [PostgreSQL, MongoDB, …]
- Tests: [pytest, vitest, jest, …]

## Commands
\`\`\`bash
# Run tests
[npm test / pytest tests/ / go test ./...]

# Lint
[npm run lint / ruff check . / golangci-lint run]

# Build
[npm run build / docker build . / make build]
\`\`\`

## Architecture
<!-- Key directories and what lives where -->
- src/api/       — API route handlers
- src/models/    — Database models / schemas
- src/services/  — Business logic
- src/utils/     — Shared helpers
- tests/         — Test files mirror src/ structure

## Coding Conventions
- Use [snake_case / camelCase] for [variables / functions]
- Prefer [async/await over callbacks]
- Keep functions under ~50 lines; extract helpers when needed
- Every public function needs a docstring / JSDoc comment

## Testing Rules
- Coverage must stay ≥ 80 %
- Never call real external APIs in tests — always mock
- One test file per source file, matching the directory structure

## Critical Rules
- Never hardcode secrets, tokens, or URLs
- Never commit .env files or credentials
- Always validate user input at API boundaries
- Do not modify CI/CD pipelines without explicit approval
- Do not add new dependencies without justification

## Stage-Specific Guidance

### Plan stage
- Read the full ticket (title + description + acceptance criteria)
- Identify every file that needs to change before writing PLAN.md
- Include a test plan section in PLAN.md

### Work stage
- Follow PLAN.md step by step — do not deviate
- Run the test suite after each logical change
- Commit with descriptive messages referencing the ticket

### Review stage
- Review your own diff for bugs, security issues, and style violations
- Fix anything you find before opening the PR
- PR title format: TICKET-123 — Short description
`;

export default function Settings() {
  const { value, setValue, loading, saving, error, lastSaved, save } =
    useBasePrompt();
  const [showExample, setShowExample] = useState(false);
  const [copied, setCopied] = useState(false);
  const {
    repos,
    loading: reposLoading,
    syncing,
    error: reposError,
    sync,
    toggle,
  } = useRepositories();
  const skills = useSkills();
  const subagents = useSubagents();
  const lessons = useLessons();
  const maxAgents = useMaxActiveAgents();

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="text-mist">Loading settings...</span>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl">
      <h1 className="text-xl font-semibold text-white mb-6">Settings</h1>

      {error && (
        <div className="text-coral text-sm mb-4">{error}</div>
      )}

      <div className="bg-abyss border border-foam/8 rounded-lg p-4">
        <label className="block text-white text-sm font-medium mb-2">
          Base Prompt
        </label>
        <p className="text-mist text-xs mb-3">
          This text is prepended to every agent call (plan, work, review) and
          written as <code className="text-foam/80">CLAUDE.md</code> in the
          workspace. Use it for project-specific instructions, coding
          conventions, or guardrails.
        </p>

        {/* Collapsible example template */}
        <div className="mb-3">
          <button
            onClick={() => setShowExample(!showExample)}
            className="text-xs text-foam hover:text-foam/80 cursor-pointer flex items-center gap-1"
          >
            <span className="transition-transform inline-block" style={{ transform: showExample ? "rotate(90deg)" : "rotate(0deg)" }}>
              &#9654;
            </span>
            {showExample ? "Hide" : "Show"} example template
          </button>
          {showExample && (
            <div className="mt-2 relative">
              <button
                onClick={() => {
                  navigator.clipboard.writeText(EXAMPLE_TEMPLATE);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2000);
                }}
                className="absolute top-2 right-2 px-2 py-1 text-xs bg-foam/10 border border-foam/20 rounded text-foam hover:bg-foam/20 cursor-pointer"
              >
                {copied ? "Copied!" : "Copy"}
              </button>
              <pre className="bg-deep border border-foam/20 rounded-lg px-4 py-3 text-mist text-xs font-mono overflow-x-auto max-h-80 overflow-y-auto whitespace-pre-wrap">
                {EXAMPLE_TEMPLATE}
              </pre>
            </div>
          )}
        </div>

        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          rows={12}
          className="w-full bg-deep border border-foam/20 rounded-lg px-4 py-3 text-white text-sm font-mono resize-y focus:outline-none focus:border-foam/50"
          placeholder="Enter base prompt text that will be prepended to all agent calls..."
        />
        <div className="flex items-center justify-between mt-3">
          <div className="text-mist text-xs">
            {lastSaved
              ? `Last saved: ${new Date(lastSaved).toLocaleString()}`
              : "Not saved yet"}
          </div>
          <button
            onClick={() => save(value)}
            disabled={saving}
            className="px-4 py-2 bg-foam/10 border border-foam/20 rounded-lg text-foam text-sm hover:bg-foam/20 disabled:opacity-50 cursor-pointer"
          >
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>

      {/* Repositories */}
      <div className="bg-abyss border border-foam/8 rounded-lg p-4 mt-6">
        <div className="flex items-center justify-between mb-2">
          <label className="block text-white text-sm font-medium">
            Repositories
          </label>
          <button
            onClick={sync}
            disabled={syncing}
            className="px-4 py-2 bg-foam/10 border border-foam/20 rounded-lg text-foam text-sm hover:bg-foam/20 disabled:opacity-50 cursor-pointer"
          >
            {syncing ? "Syncing..." : "Sync from GitHub"}
          </button>
        </div>
        <p className="text-mist text-xs mb-3">
          Control which repositories the agent can operate on. Sync from GitHub
          to discover repos, then enable the ones you want.
        </p>

        {reposError && (
          <div className="text-coral text-sm mb-3">{reposError}</div>
        )}

        {reposLoading ? (
          <div className="text-mist text-sm py-4">Loading repositories...</div>
        ) : repos.length === 0 ? (
          <div className="text-mist text-sm py-4">
            No repositories found. Click &quot;Sync from GitHub&quot; to get
            started.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-mist text-xs border-b border-foam/8">
                  <th className="text-left py-2 pr-4">Enabled</th>
                  <th className="text-left py-2 pr-4">Repository</th>
                  <th className="text-left py-2 pr-4">Description</th>
                  <th className="text-left py-2 pr-4">Visibility</th>
                  <th className="text-left py-2">Branch</th>
                </tr>
              </thead>
              <tbody>
                {repos.map((repo) => (
                  <tr
                    key={repo.id}
                    className="border-b border-foam/5 last:border-0"
                  >
                    <td className="py-2 pr-4">
                      <button
                        onClick={() => toggle(repo.id, !repo.enabled)}
                        className={`w-10 h-5 rounded-full relative transition-colors cursor-pointer ${
                          repo.enabled ? "bg-foam/60" : "bg-foam/20"
                        }`}
                        role="switch"
                        aria-checked={repo.enabled}
                      >
                        <span
                          className={`block w-3.5 h-3.5 bg-white rounded-full absolute top-0.5 transition-transform ${
                            repo.enabled
                              ? "translate-x-5"
                              : "translate-x-0.5"
                          }`}
                        />
                      </button>
                    </td>
                    <td className="py-2 pr-4">
                      <a
                        href={repo.github_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-foam hover:underline"
                      >
                        {repo.full_name}
                      </a>
                    </td>
                    <td className="py-2 pr-4 text-mist truncate max-w-xs">
                      {repo.description || "—"}
                    </td>
                    <td className="py-2 pr-4">
                      <span
                        className={`px-2 py-0.5 rounded text-xs ${
                          repo.private
                            ? "bg-coral/20 text-coral"
                            : "bg-foam/20 text-foam"
                        }`}
                      >
                        {repo.private ? "Private" : "Public"}
                      </span>
                    </td>
                    <td className="py-2 text-mist">{repo.default_branch}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Max Active Agents */}
      <div className="bg-abyss border border-foam/8 rounded-lg p-4 mt-6">
        <label className="block text-white text-sm font-medium mb-2">
          Max Active Agents
        </label>
        <p className="text-mist text-xs mb-3">
          Set to 0 or leave empty for unlimited
        </p>

        {maxAgents.error && (
          <div className="text-coral text-sm mb-3">{maxAgents.error}</div>
        )}

        <input
          type="number"
          min="0"
          value={maxAgents.value}
          onChange={(e) => maxAgents.setValue(e.target.value)}
          className="w-32 bg-deep border border-foam/20 rounded-lg px-4 py-2 text-white text-sm focus:outline-none focus:border-foam/50"
          placeholder="0"
        />
        <div className="flex items-center justify-between mt-3">
          <div className="text-mist text-xs">
            {maxAgents.lastSaved
              ? `Last saved: ${new Date(maxAgents.lastSaved).toLocaleString()}`
              : "Not saved yet"}
          </div>
          <button
            onClick={() => maxAgents.save(maxAgents.value)}
            disabled={maxAgents.saving}
            className="px-4 py-2 bg-foam/10 border border-foam/20 rounded-lg text-foam text-sm hover:bg-foam/20 disabled:opacity-50 cursor-pointer"
          >
            {maxAgents.saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>

      {/* Skills */}
      <NamedItemsEditor
        title="Skills"
        description="Each item becomes a .claude/skills/{name}.md file in the workspace. Use skills to teach the agent reusable capabilities."
        items={skills.items}
        onAdd={skills.addItem}
        onUpdate={skills.updateItem}
        onRemove={skills.removeItem}
        onSave={skills.save}
        saving={skills.saving}
        lastSaved={skills.lastSaved}
        error={skills.error}
      />

      {/* Subagents */}
      <NamedItemsEditor
        title="Subagents"
        description="Each item becomes a .claude/agents/{name}.md file in the workspace. Define specialized subagents the main agent can delegate to."
        items={subagents.items}
        onAdd={subagents.addItem}
        onUpdate={subagents.updateItem}
        onRemove={subagents.removeItem}
        onSave={subagents.save}
        saving={subagents.saving}
        lastSaved={subagents.lastSaved}
        error={subagents.error}
      />

      {/* Lessons */}
      <LessonsEditor
        value={lessons.value}
        setValue={lessons.setValue}
        save={lessons.save}
        saving={lessons.saving}
        lastSaved={lessons.lastSaved}
        error={lessons.error}
        history={lessons.history}
        historyLoading={lessons.historyLoading}
        loadHistory={lessons.loadHistory}
      />
    </div>
  );
}
