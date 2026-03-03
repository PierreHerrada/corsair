import { useState } from "react";
import type { SettingHistoryEntry } from "../types";

interface LessonsEditorProps {
  value: string;
  setValue: (v: string) => void;
  save: (v: string) => void;
  saving: boolean;
  lastSaved: string | null;
  error: string | null;
  history: SettingHistoryEntry[];
  historyLoading: boolean;
  loadHistory: () => void;
}

export default function LessonsEditor({
  value,
  setValue,
  save,
  saving,
  lastSaved,
  error,
  history,
  historyLoading,
  loadHistory,
}: LessonsEditorProps) {
  const [showHistory, setShowHistory] = useState(false);

  const handleToggleHistory = () => {
    if (!showHistory && history.length === 0) {
      loadHistory();
    }
    setShowHistory(!showHistory);
  };

  return (
    <div className="bg-abyss border border-foam/8 rounded-lg p-4 mt-6">
      <label className="block text-white text-sm font-medium mb-2">
        Lessons
      </label>
      <p className="text-mist text-xs mb-3">
        Living <code className="text-foam/80">LESSONS.md</code> file. Written to
        the workspace before each run. The agent can update it during runs —
        changes are synced back automatically.
      </p>

      {error && <div className="text-coral text-sm mb-3">{error}</div>}

      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        rows={10}
        className="w-full bg-deep border border-foam/20 rounded-lg px-4 py-3 text-white text-sm font-mono resize-y focus:outline-none focus:border-foam/50"
        placeholder="# Lessons&#10;&#10;Record errors, root causes, and solutions here..."
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

      {/* History panel */}
      <div className="mt-4 border-t border-foam/8 pt-3">
        <button
          onClick={handleToggleHistory}
          className="text-xs text-foam hover:text-foam/80 cursor-pointer flex items-center gap-1"
        >
          <span
            className="transition-transform inline-block"
            style={{
              transform: showHistory ? "rotate(90deg)" : "rotate(0deg)",
            }}
          >
            &#9654;
          </span>
          {showHistory ? "Hide" : "Show"} change history
        </button>

        {showHistory && (
          <div className="mt-2 max-h-60 overflow-y-auto">
            {historyLoading ? (
              <div className="text-mist text-xs py-2">Loading history...</div>
            ) : history.length === 0 ? (
              <div className="text-mist text-xs py-2">No history yet.</div>
            ) : (
              <div className="space-y-2">
                {history.map((entry) => (
                  <div
                    key={entry.id}
                    className="border border-foam/10 rounded p-2 bg-deep text-xs"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className={`px-1.5 py-0.5 rounded text-xs ${
                          entry.change_source === "agent"
                            ? "bg-teal-500/20 text-teal-400"
                            : "bg-foam/20 text-mist"
                        }`}
                      >
                        {entry.change_source}
                      </span>
                      <span className="text-mist">
                        {new Date(entry.created_at).toLocaleString()}
                      </span>
                    </div>
                    <div className="text-mist truncate">
                      {entry.new_value.slice(0, 120)}
                      {entry.new_value.length > 120 ? "..." : ""}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
