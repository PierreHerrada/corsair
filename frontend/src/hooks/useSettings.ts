import { useCallback, useEffect, useState } from "react";
import { fetchJiraStatusDefaults } from "../api/agent";
import {
  fetchEnvVars,
  fetchSetting,
  fetchSettingHistory,
  updateEnvVars,
  updateSetting,
} from "../api/settings";
import type {
  EnvVarItem,
  SettingHistoryEntry,
  SkillItem,
  SubagentItem,
} from "../types";

export function useBasePrompt() {
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSaved, setLastSaved] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchSetting("base_prompt");
      setValue(data.value);
      setLastSaved(data.updated_at);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const save = useCallback(async (newValue: string) => {
    try {
      setSaving(true);
      const data = await updateSetting("base_prompt", newValue);
      setValue(data.value);
      setLastSaved(data.updated_at);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSaving(false);
    }
  }, []);

  return { value, setValue, loading, saving, error, lastSaved, save };
}

function useNamedItems<T extends { name: string; content: string }>(
  settingKey: string,
) {
  const [items, setItems] = useState<T[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSaved, setLastSaved] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchSetting(settingKey);
      if (data.value) {
        try {
          setItems(JSON.parse(data.value));
        } catch {
          setItems([]);
        }
      } else {
        setItems([]);
      }
      setLastSaved(data.updated_at);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [settingKey]);

  useEffect(() => {
    load();
  }, [load]);

  const save = useCallback(async () => {
    try {
      setSaving(true);
      const data = await updateSetting(settingKey, JSON.stringify(items));
      setLastSaved(data.updated_at);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSaving(false);
    }
  }, [settingKey, items]);

  const addItem = useCallback(() => {
    setItems((prev) => [...prev, { name: "", content: "" } as T]);
  }, []);

  const updateItem = useCallback(
    (index: number, field: keyof T, value: string) => {
      setItems((prev) => {
        const next = [...prev];
        next[index] = { ...next[index], [field]: value };
        return next;
      });
    },
    [],
  );

  const removeItem = useCallback((index: number) => {
    setItems((prev) => prev.filter((_, i) => i !== index));
  }, []);

  return {
    items,
    loading,
    saving,
    error,
    lastSaved,
    save,
    addItem,
    updateItem,
    removeItem,
  };
}

export function useMaxActiveAgents() {
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSaved, setLastSaved] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchSetting("max_active_agents");
      setValue(data.value);
      setLastSaved(data.updated_at);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const save = useCallback(async (newValue: string) => {
    try {
      setSaving(true);
      const data = await updateSetting("max_active_agents", newValue);
      setValue(data.value);
      setLastSaved(data.updated_at);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSaving(false);
    }
  }, []);

  return { value, setValue, loading, saving, error, lastSaved, save };
}

export function useAutoWork() {
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchSetting("auto_work");
      setEnabled(data.value === "true");
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const toggle = useCallback(async () => {
    const newValue = !enabled;
    try {
      setSaving(true);
      await updateSetting("auto_work", newValue ? "true" : "false");
      setEnabled(newValue);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSaving(false);
    }
  }, [enabled]);

  return { enabled, loading, saving, error, toggle };
}

export function useJiraSyncInterval() {
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSaved, setLastSaved] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchSetting("jira_sync_interval");
      setValue(data.value || "60");
      setLastSaved(data.updated_at);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const save = useCallback(async (newValue: string) => {
    try {
      setSaving(true);
      const data = await updateSetting("jira_sync_interval", newValue);
      setValue(data.value);
      setLastSaved(data.updated_at);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSaving(false);
    }
  }, []);

  return { value, setValue, loading, saving, error, lastSaved, save };
}

export function useEnvVars() {
  const [items, setItems] = useState<EnvVarItem[]>([]);
  const [pendingValues, setPendingValues] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSaved, setLastSaved] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchEnvVars();
      setItems(data.items);
      setPendingValues({});
      setLastSaved(data.updated_at);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const addItem = useCallback(() => {
    setItems((prev) => [...prev, { name: "", masked_value: "" }]);
  }, []);

  const updateName = useCallback((index: number, name: string) => {
    setItems((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], name };
      return next;
    });
  }, []);

  const updateValue = useCallback((index: number, value: string) => {
    setPendingValues((prev) => ({ ...prev, [index]: value }));
  }, []);

  const removeItem = useCallback((index: number) => {
    setItems((prev) => prev.filter((_, i) => i !== index));
    setPendingValues((prev) => {
      const next: Record<number, string> = {};
      for (const [k, v] of Object.entries(prev)) {
        const ki = Number(k);
        if (ki < index) next[ki] = v;
        else if (ki > index) next[ki - 1] = v;
      }
      return next;
    });
  }, []);

  const save = useCallback(async () => {
    try {
      setSaving(true);
      const payload = items.map((item, i) => ({
        name: item.name,
        value: pendingValues[i] !== undefined ? pendingValues[i] : item.masked_value,
      }));
      const data = await updateEnvVars(payload);
      setItems(data.items);
      setPendingValues({});
      setLastSaved(data.updated_at);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSaving(false);
    }
  }, [items, pendingValues]);

  return {
    items,
    pendingValues,
    loading,
    saving,
    error,
    lastSaved,
    addItem,
    updateName,
    updateValue,
    removeItem,
    save,
  };
}

export function useSkills() {
  return useNamedItems<SkillItem>("skills");
}

export function useSubagents() {
  return useNamedItems<SubagentItem>("subagents");
}

export const TASK_STATUSES = [
  "backlog",
  "planned",
  "working",
  "reviewing",
  "done",
  "failed",
] as const;

export function useJiraStatusMapping() {
  const [entries, setEntries] = useState<[string, string][]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSaved, setLastSaved] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchSetting("jira_status_mapping");
      if (data.value) {
        try {
          const parsed = JSON.parse(data.value);
          if (typeof parsed === "object" && parsed !== null) {
            setEntries(Object.entries(parsed));
          }
        } catch {
          setEntries([]);
        }
      } else {
        // No mapping saved yet — load backend defaults
        try {
          const defaults = await fetchJiraStatusDefaults();
          setEntries(Object.entries(defaults));
        } catch {
          setEntries([]);
        }
      }
      setLastSaved(data.updated_at);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const save = useCallback(async () => {
    try {
      setSaving(true);
      const record = Object.fromEntries(entries);
      const data = await updateSetting(
        "jira_status_mapping",
        JSON.stringify(record),
      );
      setLastSaved(data.updated_at);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSaving(false);
    }
  }, [entries]);

  const resetToDefaults = useCallback(async () => {
    try {
      const defaults = await fetchJiraStatusDefaults();
      setEntries(Object.entries(defaults));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch defaults");
    }
  }, []);

  return { entries, setEntries, save, resetToDefaults, loading, saving, error, lastSaved };
}

export function useLessons() {
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSaved, setLastSaved] = useState<string | null>(null);
  const [history, setHistory] = useState<SettingHistoryEntry[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchSetting("lessons");
      setValue(data.value);
      setLastSaved(data.updated_at);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const save = useCallback(
    async (newValue: string) => {
      try {
        setSaving(true);
        const data = await updateSetting("lessons", newValue);
        setValue(data.value);
        setLastSaved(data.updated_at);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unknown error");
      } finally {
        setSaving(false);
      }
    },
    [],
  );

  const loadHistory = useCallback(async () => {
    try {
      setHistoryLoading(true);
      const data = await fetchSettingHistory("lessons");
      setHistory(data.entries);
    } catch {
      // Silently fail — history is non-critical
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  return {
    value,
    setValue,
    loading,
    saving,
    error,
    lastSaved,
    save,
    history,
    historyLoading,
    loadHistory,
  };
}
