import { useBasePrompt } from "../hooks/useSettings";

export default function Settings() {
  const { value, setValue, loading, saving, error, lastSaved, save } =
    useBasePrompt();

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="text-mist">Loading settings...</span>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-3xl">
      <h1 className="text-xl font-semibold text-white mb-6">Settings</h1>

      {error && (
        <div className="text-coral text-sm mb-4">{error}</div>
      )}

      <div className="bg-abyss border border-foam/8 rounded-lg p-4">
        <label className="block text-white text-sm font-medium mb-2">
          Base Prompt
        </label>
        <p className="text-mist text-xs mb-3">
          This text is prepended to every agent call (plan, work, review). Use
          it for project-specific instructions, coding conventions, or
          guardrails.
        </p>
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
    </div>
  );
}
