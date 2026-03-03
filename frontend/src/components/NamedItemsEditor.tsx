interface NamedItem {
  name: string;
  content: string;
}

interface NamedItemsEditorProps {
  title: string;
  description: string;
  items: NamedItem[];
  onAdd: () => void;
  onUpdate: (index: number, field: "name" | "content", value: string) => void;
  onRemove: (index: number) => void;
  onSave: () => void;
  saving: boolean;
  lastSaved: string | null;
  error: string | null;
}

export default function NamedItemsEditor({
  title,
  description,
  items,
  onAdd,
  onUpdate,
  onRemove,
  onSave,
  saving,
  lastSaved,
  error,
}: NamedItemsEditorProps) {
  return (
    <div className="bg-abyss border border-foam/8 rounded-lg p-4 mt-6">
      <div className="flex items-center justify-between mb-2">
        <label className="block text-white text-sm font-medium">{title}</label>
        <button
          onClick={onAdd}
          className="px-3 py-1 bg-foam/10 border border-foam/20 rounded-lg text-foam text-xs hover:bg-foam/20 cursor-pointer"
        >
          + Add
        </button>
      </div>
      <p className="text-mist text-xs mb-3">{description}</p>

      {error && <div className="text-coral text-sm mb-3">{error}</div>}

      {items.length === 0 ? (
        <div className="text-mist text-sm py-4">
          No items configured. Click &quot;+ Add&quot; to get started.
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item, index) => (
            <div
              key={index}
              className="border border-foam/10 rounded-lg p-3 bg-deep"
            >
              <div className="flex items-center gap-2 mb-2">
                <input
                  type="text"
                  value={item.name}
                  onChange={(e) => onUpdate(index, "name", e.target.value)}
                  placeholder="Name (used as filename)"
                  className="flex-1 bg-abyss border border-foam/20 rounded px-3 py-1.5 text-white text-sm font-mono focus:outline-none focus:border-foam/50"
                />
                <button
                  onClick={() => onRemove(index)}
                  className="px-2 py-1.5 text-coral text-xs hover:bg-coral/10 rounded cursor-pointer"
                >
                  Remove
                </button>
              </div>
              <textarea
                value={item.content}
                onChange={(e) => onUpdate(index, "content", e.target.value)}
                rows={4}
                placeholder="Content (markdown)"
                className="w-full bg-abyss border border-foam/20 rounded px-3 py-2 text-white text-sm font-mono resize-y focus:outline-none focus:border-foam/50"
              />
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between mt-3">
        <div className="text-mist text-xs">
          {lastSaved
            ? `Last saved: ${new Date(lastSaved).toLocaleString()}`
            : "Not saved yet"}
        </div>
        <button
          onClick={onSave}
          disabled={saving}
          className="px-4 py-2 bg-foam/10 border border-foam/20 rounded-lg text-foam text-sm hover:bg-foam/20 disabled:opacity-50 cursor-pointer"
        >
          {saving ? "Saving..." : "Save"}
        </button>
      </div>
    </div>
  );
}
