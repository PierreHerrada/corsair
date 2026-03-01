import { useState } from "react";
import { useDatadog } from "../hooks/useDatadog";
import type { DatadogAnalysis, AnalysisStatus } from "../types";

const STATUS_COLORS: Record<AnalysisStatus, string> = {
  pending: "bg-gold/20 text-gold",
  analyzing: "bg-foam/20 text-foam",
  done: "bg-teal/20 text-teal",
  failed: "bg-coral/20 text-coral",
};

function StatusBadge({ status }: { status: AnalysisStatus }) {
  return (
    <span
      className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[status]}`}
    >
      {status}
    </span>
  );
}

function LogEntry({ log }: { log: Record<string, unknown> }) {
  const attrs = (log.attributes ?? {}) as Record<string, unknown>;
  const status = String(attrs.status ?? "info");
  const isError = status === "error";

  return (
    <div
      className={`p-2 rounded text-xs font-mono ${isError ? "bg-coral/10 border border-coral/30" : "bg-abyss border border-foam/8"}`}
    >
      <span className="text-mist/60">
        {String(attrs.timestamp ?? "")}
      </span>{" "}
      <span className="text-foam">{String(attrs.service ?? "")}</span>{" "}
      <span className={isError ? "text-coral" : "text-mist"}>
        [{status}]
      </span>{" "}
      <span className="text-white">{String(attrs.message ?? "")}</span>
    </div>
  );
}

function TraceSpan({ span }: { span: Record<string, unknown> }) {
  const attrs = (span.attributes ?? {}) as Record<string, unknown>;
  const isError = String(attrs.status ?? "") === "error";
  const durationNs = Number(attrs.duration ?? 0);
  const durationMs = durationNs / 1_000_000;

  return (
    <div
      className={`p-2 rounded text-xs font-mono ${isError ? "bg-coral/10 border border-coral/30" : "bg-abyss border border-foam/8"}`}
    >
      <span className="text-foam">
        {String(attrs.service ?? "unknown")}
      </span>{" "}
      <span className="text-mist">&rarr;</span>{" "}
      <span className="text-white">
        {String(attrs.resource_name ?? attrs.operation_name ?? "unknown")}
      </span>{" "}
      <span className="text-mist/60">({durationMs.toFixed(1)}ms)</span>
      {isError && <span className="text-coral ml-2">[ERROR]</span>}
    </div>
  );
}

function AnalysisDetail({
  analysis,
  onClose,
}: {
  analysis: DatadogAnalysis;
  onClose: () => void;
}) {
  return (
    <div className="bg-abyss border border-foam/8 rounded-lg p-6 mt-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold">Analysis Detail</h2>
          <StatusBadge status={analysis.status} />
        </div>
        <button
          onClick={onClose}
          className="text-mist hover:text-white text-sm cursor-pointer"
        >
          Close
        </button>
      </div>

      {analysis.summary && (
        <div className="mb-4">
          <h3 className="text-sm font-medium text-mist mb-2">Summary</h3>
          <pre className="text-sm text-white whitespace-pre-wrap bg-navy/50 rounded p-4">
            {analysis.summary}
          </pre>
        </div>
      )}

      {analysis.error_message && (
        <div className="mb-4">
          <h3 className="text-sm font-medium text-coral mb-2">Error</h3>
          <p className="text-sm text-coral">{analysis.error_message}</p>
        </div>
      )}

      {analysis.raw_logs && analysis.raw_logs.length > 0 && (
        <div className="mb-4">
          <h3 className="text-sm font-medium text-mist mb-2">
            Logs ({analysis.log_count})
          </h3>
          <div className="space-y-1 max-h-64 overflow-y-auto">
            {analysis.raw_logs.map((log, i) => (
              <LogEntry key={i} log={log} />
            ))}
          </div>
        </div>
      )}

      {analysis.trace_id &&
        analysis.raw_trace &&
        analysis.raw_trace.length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-mist mb-2">
              Trace ({analysis.trace_id})
            </h3>
            <div className="space-y-1 max-h-64 overflow-y-auto">
              {analysis.raw_trace.map((span, i) => (
                <TraceSpan key={i} span={span} />
              ))}
            </div>
          </div>
        )}
    </div>
  );
}

export default function Datadog() {
  const {
    analyses,
    total,
    loading,
    error,
    offset,
    pageSize,
    nextPage,
    prevPage,
    analyze,
    selectedAnalysis,
    selectAnalysis,
    clearSelection,
  } = useDatadog();

  const [input, setInput] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleAnalyze = async () => {
    if (!input.trim()) return;
    setSubmitting(true);
    const value = input.trim();
    // Determine if it's a URL, trace ID (hex), or log query
    const params: { url?: string; query?: string; trace_id?: string } = {};
    if (value.startsWith("http")) {
      params.url = value;
    } else if (/^[a-fA-F0-9]{16,}$/.test(value)) {
      params.trace_id = value;
    } else {
      params.query = value;
    }
    await analyze(params);
    setInput("");
    setSubmitting(false);
  };

  if (loading && analyses.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="text-mist">Loading analyses...</span>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Input Bar */}
      <div className="mb-6">
        <h1 className="text-xl font-semibold mb-4">Datadog Analysis</h1>
        <div className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
            placeholder="Paste a Datadog URL, trace ID, or log query..."
            className="flex-1 bg-abyss border border-foam/20 rounded-lg px-4 py-2 text-sm text-white placeholder-mist/40 focus:outline-none focus:border-teal"
          />
          <button
            onClick={handleAnalyze}
            disabled={submitting || !input.trim()}
            className="px-6 py-2 bg-teal/20 border border-teal/40 rounded-lg text-teal text-sm font-medium hover:bg-teal/30 disabled:opacity-50 cursor-pointer"
          >
            {submitting ? "Analyzing..." : "Analyze"}
          </button>
        </div>
        {error && (
          <p className="text-coral text-sm mt-2">{error}</p>
        )}
      </div>

      {/* Analysis List */}
      {analyses.length === 0 ? (
        <div className="flex items-center justify-center h-64">
          <span className="text-mist">
            No analyses yet. Paste a Datadog URL or query above to get started.
          </span>
        </div>
      ) : (
        <div className="space-y-2">
          {analyses.map((a) => (
            <div
              key={a.id}
              onClick={() => selectAnalysis(a.id)}
              className="bg-abyss border border-foam/8 rounded-lg p-4 cursor-pointer hover:border-foam/20 transition-colors"
            >
              <div className="flex items-center gap-3">
                <StatusBadge status={a.status} />
                <span className="text-xs text-mist/60 uppercase">
                  {a.source}
                </span>
                <span className="text-sm text-white flex-1 truncate">
                  {a.trigger}
                </span>
                <span className="text-xs text-mist">
                  {a.log_count} logs
                </span>
                <span className="text-xs text-mist/40">
                  {new Date(a.created_at).toLocaleString()}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
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
            {offset + 1}&ndash;{Math.min(offset + pageSize, total)} of {total}
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

      {/* Analysis Detail */}
      {selectedAnalysis && (
        <AnalysisDetail
          analysis={selectedAnalysis}
          onClose={clearSelection}
        />
      )}
    </div>
  );
}
