import { useEffect, useState } from "react";
import {
  createAgentType,
  deleteAgentType,
  fetchAgentTypes,
  updateAgentType,
} from "../api/agentTypes";
import type { AgentType } from "../types";

const EMPTY_FORM = {
  name: "",
  display_name: "",
  description: "",
  ecs_task_definition: "",
  docker_image: "",
  task_role_arn: "",
  capabilities: [] as string[],
  cpu: 1024,
  memory: 2048,
  max_duration_seconds: 3600,
  enable_dind: false,
  is_default: false,
};

export default function AgentTypes() {
  const [types, setTypes] = useState<AgentType[]>([]);
  const [editing, setEditing] = useState<AgentType | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);

  const refresh = () => {
    fetchAgentTypes().then(setTypes).catch(() => {});
  };

  useEffect(() => {
    refresh();
  }, []);

  const openCreate = () => {
    setForm(EMPTY_FORM);
    setEditing(null);
    setCreating(true);
  };

  const openEdit = (at: AgentType) => {
    setForm({
      name: at.name,
      display_name: at.display_name,
      description: at.description || "",
      ecs_task_definition: at.ecs_task_definition,
      docker_image: at.docker_image,
      task_role_arn: at.task_role_arn,
      capabilities: at.capabilities,
      cpu: at.cpu,
      memory: at.memory,
      max_duration_seconds: at.max_duration_seconds,
      enable_dind: at.enable_dind,
      is_default: at.is_default,
    });
    setEditing(at);
    setCreating(true);
  };

  const handleSave = async () => {
    try {
      if (editing) {
        await updateAgentType(editing.id, form);
      } else {
        await createAgentType(form);
      }
      setCreating(false);
      refresh();
    } catch {
      // Error display could be improved
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this agent type?")) return;
    try {
      await deleteAgentType(id);
      refresh();
    } catch {
      // Error display could be improved
    }
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">Agent Types</h1>
        <button
          onClick={openCreate}
          className="text-sm px-4 py-2 rounded bg-wave/20 text-wave hover:bg-wave/30"
        >
          New Agent Type
        </button>
      </div>

      <div className="bg-abyss border border-foam/8 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-mist text-xs uppercase border-b border-foam/8">
              <th className="text-left px-4 py-2">Name</th>
              <th className="text-left px-4 py-2">Task Definition</th>
              <th className="text-center px-4 py-2">CPU/Mem</th>
              <th className="text-center px-4 py-2">DinD</th>
              <th className="text-center px-4 py-2">Default</th>
              <th className="text-right px-4 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {types.map((at) => (
              <tr key={at.id} className="border-b border-foam/5">
                <td className="px-4 py-2">
                  <div className="font-medium text-white">{at.display_name}</div>
                  <div className="text-xs text-mist/60">{at.name}</div>
                </td>
                <td className="px-4 py-2 text-xs text-mist font-mono truncate max-w-xs">
                  {at.ecs_task_definition}
                </td>
                <td className="px-4 py-2 text-center text-xs text-mist">
                  {at.cpu / 1024} vCPU / {at.memory / 1024} GB
                </td>
                <td className="px-4 py-2 text-center text-xs">
                  {at.enable_dind ? (
                    <span className="text-green-400">Yes</span>
                  ) : (
                    <span className="text-mist/40">No</span>
                  )}
                </td>
                <td className="px-4 py-2 text-center text-xs">
                  {at.is_default ? (
                    <span className="text-gold">Default</span>
                  ) : (
                    <span className="text-mist/40">-</span>
                  )}
                </td>
                <td className="px-4 py-2 text-right">
                  <button
                    onClick={() => openEdit(at)}
                    className="text-xs text-sky hover:underline mr-2"
                  >
                    Edit
                  </button>
                  {!at.is_default && (
                    <button
                      onClick={() => handleDelete(at.id)}
                      className="text-xs text-coral hover:underline"
                    >
                      Delete
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {types.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-mist/50">
                  No agent types configured
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {creating && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-navy border border-foam/20 rounded-lg p-6 w-full max-w-lg max-h-[80vh] overflow-y-auto">
            <h2 className="text-lg font-semibold mb-4">
              {editing ? "Edit" : "Create"} Agent Type
            </h2>
            <div className="space-y-3">
              <input
                placeholder="Name (e.g. db-agent)"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full bg-abyss border border-foam/20 rounded px-3 py-2 text-sm"
              />
              <input
                placeholder="Display Name"
                value={form.display_name}
                onChange={(e) => setForm({ ...form, display_name: e.target.value })}
                className="w-full bg-abyss border border-foam/20 rounded px-3 py-2 text-sm"
              />
              <textarea
                placeholder="Description"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                className="w-full bg-abyss border border-foam/20 rounded px-3 py-2 text-sm"
                rows={2}
              />
              <input
                placeholder="ECS Task Definition ARN"
                value={form.ecs_task_definition}
                onChange={(e) => setForm({ ...form, ecs_task_definition: e.target.value })}
                className="w-full bg-abyss border border-foam/20 rounded px-3 py-2 text-sm"
              />
              <div className="grid grid-cols-2 gap-3">
                <input
                  type="number"
                  placeholder="CPU units"
                  value={form.cpu}
                  onChange={(e) => setForm({ ...form, cpu: Number(e.target.value) })}
                  className="bg-abyss border border-foam/20 rounded px-3 py-2 text-sm"
                />
                <input
                  type="number"
                  placeholder="Memory (MB)"
                  value={form.memory}
                  onChange={(e) => setForm({ ...form, memory: Number(e.target.value) })}
                  className="bg-abyss border border-foam/20 rounded px-3 py-2 text-sm"
                />
              </div>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form.enable_dind}
                    onChange={(e) => setForm({ ...form, enable_dind: e.target.checked })}
                  />
                  Enable DinD
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form.is_default}
                    onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
                  />
                  Default
                </label>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => setCreating(false)}
                className="text-sm px-4 py-2 rounded text-mist hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                className="text-sm px-4 py-2 rounded bg-wave/20 text-wave hover:bg-wave/30"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
