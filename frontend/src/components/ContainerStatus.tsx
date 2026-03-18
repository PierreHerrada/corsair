import type { RunStatus } from "../types";

const STATUS_STYLES: Record<string, string> = {
  launching: "bg-gold/20 text-gold",
  running: "bg-teal/20 text-teal",
  done: "bg-teal/20 text-teal",
  failed: "bg-coral/20 text-coral",
  cancelled: "bg-mist/20 text-mist",
};

interface ContainerStatusProps {
  status: RunStatus;
  ecsTaskArn: string | null;
  errorMessage: string | null;
  onCancel?: () => void;
}

export default function ContainerStatus({
  status,
  ecsTaskArn,
  errorMessage,
  onCancel,
}: ContainerStatusProps) {
  const isActive = status === "launching" || status === "running";
  const truncatedArn = ecsTaskArn
    ? "..." + ecsTaskArn.slice(-20)
    : null;

  return (
    <div className="flex items-center gap-2 text-xs mb-2">
      <span
        className={`px-2 py-0.5 rounded-full ${STATUS_STYLES[status] || "bg-mist/20 text-mist"}`}
      >
        {status}
      </span>
      {truncatedArn && (
        <span className="text-mist/40 font-mono" title={ecsTaskArn || ""}>
          {truncatedArn}
        </span>
      )}
      {errorMessage && (
        <span className="text-coral/60 truncate max-w-xs" title={errorMessage}>
          {errorMessage}
        </span>
      )}
      {isActive && onCancel && (
        <button
          onClick={onCancel}
          className="px-2 py-0.5 rounded bg-coral/20 text-coral hover:bg-coral/30"
        >
          Cancel
        </button>
      )}
    </div>
  );
}
