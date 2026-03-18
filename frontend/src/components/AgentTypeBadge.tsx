import type { AgentType } from "../types";

const CAPABILITY_COLORS: Record<string, string> = {
  github: "bg-gray-500/20 text-gray-300",
  database: "bg-blue-500/20 text-blue-300",
  aws: "bg-orange-500/20 text-orange-300",
  datadog: "bg-purple-500/20 text-purple-300",
  dind: "bg-green-500/20 text-green-300",
};

interface AgentTypeBadgeProps {
  agentType: AgentType;
}

export default function AgentTypeBadge({ agentType }: AgentTypeBadgeProps) {
  return (
    <div className="flex items-center gap-1 flex-wrap">
      <span className="text-[10px] text-mist/60">{agentType.display_name}</span>
      {agentType.capabilities.map((cap) => (
        <span
          key={cap}
          className={`text-[9px] px-1.5 py-0.5 rounded-full ${CAPABILITY_COLORS[cap] || "bg-foam/20 text-foam"}`}
        >
          {cap}
        </span>
      ))}
    </div>
  );
}
