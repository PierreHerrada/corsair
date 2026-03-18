import { useEffect, useState } from "react";
import { fetchAgentTypes } from "../api/agentTypes";
import type { AgentType } from "../types";

interface AgentTypeSelectorProps {
  value: string | null;
  onChange: (agentTypeId: string | null) => void;
}

export default function AgentTypeSelector({
  value,
  onChange,
}: AgentTypeSelectorProps) {
  const [types, setTypes] = useState<AgentType[]>([]);

  useEffect(() => {
    fetchAgentTypes()
      .then(setTypes)
      .catch(() => {});
  }, []);

  if (types.length === 0) return null;

  return (
    <select
      value={value || ""}
      onChange={(e) => onChange(e.target.value || null)}
      className="text-xs bg-navy border border-foam/20 rounded px-2 py-1 text-mist"
    >
      <option value="">Default Agent</option>
      {types.map((t) => (
        <option key={t.id} value={t.id}>
          {t.display_name}
          {t.enable_dind ? " (+ Docker)" : ""}
        </option>
      ))}
    </select>
  );
}
