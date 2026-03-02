import { useLogs } from "../hooks/useLogs";

const LEVEL_COLORS: Record<string, string> = {
  ERROR: "bg-coral/20 text-coral",
  WARNING: "bg-amber-500/20 text-amber-400",
  INFO: "bg-foam/20 text-foam",
  DEBUG: "bg-mist/20 text-mist",
};

export default function Logs() {
  const {
    logs,
    total,
    offset,
    loading,
    error,
    source,
    level,
    pageSize,
    filterBySource,
    filterByLevel,
    nextPage,
    prevPage,
    refresh,
  } = useLogs();

  if (loading && logs.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="text-mist">Loading logs...</span>
      </div>
    );
  }

  if (error && logs.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="text-coral">{error}</span>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">Internal Logs</h1>
        <div className="flex items-center gap-3">
          <span className="text-mist text-sm">{total} logs</span>
          <button
            onClick={refresh}
            className="px-4 py-2 bg-foam/10 border border-foam/20 rounded-lg text-foam text-sm hover:bg-foam/20"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <select
          value={source}
          onChange={(e) => filterBySource(e.target.value)}
          className="bg-abyss border border-foam/20 rounded-lg px-3 py-2 text-sm text-white"
        >
          <option value="">All sources</option>
          <option value="jira">Jira</option>
          <option value="slack">Slack</option>
          <option value="github">GitHub</option>
          <option value="datadog">Datadog</option>
          <option value="main">Main</option>
        </select>

        <select
          value={level}
          onChange={(e) => filterByLevel(e.target.value)}
          className="bg-abyss border border-foam/20 rounded-lg px-3 py-2 text-sm text-white"
        >
          <option value="">All levels</option>
          <option value="ERROR">Error</option>
          <option value="WARNING">Warning</option>
          <option value="INFO">Info</option>
          <option value="DEBUG">Debug</option>
        </select>
      </div>

      {logs.length === 0 ? (
        <div className="flex items-center justify-center h-64">
          <span className="text-mist">
            No logs yet. Logs from Jira sync and Slack bot will appear here.
          </span>
        </div>
      ) : (
        <div className="bg-abyss border border-foam/8 rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-foam/8 text-mist text-xs">
                  <th className="px-4 py-3 text-left font-medium w-44">
                    Time
                  </th>
                  <th className="px-4 py-3 text-left font-medium w-24">
                    Source
                  </th>
                  <th className="px-4 py-3 text-left font-medium w-24">
                    Level
                  </th>
                  <th className="px-4 py-3 text-left font-medium">Message</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr
                    key={log.id}
                    className="border-b border-foam/5 hover:bg-foam/5"
                  >
                    <td className="px-4 py-2 text-mist/60 text-xs whitespace-nowrap font-mono">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2">
                      <span className="text-xs px-2 py-0.5 rounded bg-foam/10 text-foam">
                        {log.source}
                      </span>
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={`text-xs px-2 py-0.5 rounded ${LEVEL_COLORS[log.level] || "bg-mist/20 text-mist"}`}
                      >
                        {log.level}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-white font-mono text-xs break-all whitespace-pre-wrap">
                      {log.message}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {total > pageSize && (
        <div className="flex items-center justify-between mt-4">
          <button
            onClick={prevPage}
            disabled={offset === 0}
            className="px-4 py-2 bg-foam/10 border border-foam/20 rounded-lg text-foam text-sm hover:bg-foam/20 disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-mist text-sm">
            {offset + 1}–{Math.min(offset + pageSize, total)} of {total}
          </span>
          <button
            onClick={nextPage}
            disabled={offset + pageSize >= total}
            className="px-4 py-2 bg-foam/10 border border-foam/20 rounded-lg text-foam text-sm hover:bg-foam/20 disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
