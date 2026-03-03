import { useCallback, useEffect, useState } from "react";
import {
  fetchSetting,
  fetchSettingHistory,
  updateSetting,
} from "../api/settings";
import type {
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

export function useSkills() {
  return useNamedItems<SkillItem>("skills");
}

export function useSubagents() {
  return useNamedItems<SubagentItem>("subagents");
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
