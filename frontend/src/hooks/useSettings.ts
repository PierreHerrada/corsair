import { useCallback, useEffect, useState } from "react";
import { fetchSetting, updateSetting } from "../api/settings";

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
