import { useEffect, useRef } from "react";
import type { AgentLog, LogType } from "../types";

const LOG_COLORS: Record<LogType, string> = {
  text: "text-white",
  tool_use: "text-sky",
  tool_result: "text-mist",
  error: "text-coral",
};

const LOG_PREFIXES: Record<LogType, string> = {
  text: "",
  tool_use: "TOOL ",
  tool_result: "RESULT ",
  error: "ERROR ",
};

interface AgentLogViewerProps {
  logs: AgentLog[];
  connected: boolean;
}

export default function AgentLogViewer({ logs, connected }: AgentLogViewerProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className="bg-abyss border border-foam/8 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 bg-navy border-b border-foam/8">
        <span className="text-sm text-mist">
          Agent Logs ({logs.length})
        </span>
        <span
          className={`text-xs px-2 py-0.5 rounded-full ${
            connected ? "bg-teal/20 text-teal" : "bg-coral/20 text-coral"
          }`}
        >
          {connected ? "Live" : "Stored"}
        </span>
      </div>
      <div className="p-4 max-h-[70vh] overflow-y-auto font-mono text-xs leading-relaxed">
        {logs.length === 0 ? (
          <span className="text-mist/50">No logs yet...</span>
        ) : (
          logs.map((log) => (
            <div key={log.id} className={`mb-1 ${LOG_COLORS[log.type]}`}>
              <span className="text-mist/40 mr-2">
                {LOG_PREFIXES[log.type]}
              </span>
              {renderLogContent(log)}
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

function renderLogContent(log: AgentLog): string {
  const content = log.content;
  if (typeof content === "object" && "message" in content) {
    return String(content.message);
  }
  return JSON.stringify(content);
}
