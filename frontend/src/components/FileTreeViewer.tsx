import { useState } from "react";
import type { FileTreeEntry } from "../types";

interface TreeNode {
  name: string;
  path: string;
  type: "file" | "dir";
  size?: number;
  children: Map<string, TreeNode>;
}

function buildTree(entries: FileTreeEntry[]): TreeNode {
  const root: TreeNode = { name: "", path: "", type: "dir", children: new Map() };

  for (const entry of entries) {
    const parts = entry.path.split("/");
    let current = root;

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const isLast = i === parts.length - 1;

      if (!current.children.has(part)) {
        current.children.set(part, {
          name: part,
          path: parts.slice(0, i + 1).join("/"),
          type: isLast ? entry.type : "dir",
          size: isLast ? entry.size : undefined,
          children: new Map(),
        });
      }

      const node = current.children.get(part)!;
      if (isLast) {
        node.type = entry.type;
        node.size = entry.size;
      }
      current = node;
    }
  }

  return root;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function TreeNodeView({ node, depth }: { node: TreeNode; depth: number }) {
  const [expanded, setExpanded] = useState(depth < 2);
  const children = Array.from(node.children.values()).sort((a, b) => {
    if (a.type !== b.type) return a.type === "dir" ? -1 : 1;
    return a.name.localeCompare(b.name);
  });

  if (node.type === "file") {
    return (
      <div
        className="flex items-center gap-1.5 py-0.5 text-mist hover:text-white"
        style={{ paddingLeft: `${depth * 16}px` }}
      >
        <span className="text-mist/40">-</span>
        <span>{node.name}</span>
        {node.size !== undefined && (
          <span className="text-mist/30 ml-auto">{formatSize(node.size)}</span>
        )}
      </div>
    );
  }

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 py-0.5 text-sky hover:text-white w-full text-left cursor-pointer"
        style={{ paddingLeft: `${depth * 16}px` }}
      >
        <span className="text-sky/60">{expanded ? "v" : ">"}</span>
        <span>{node.name}/</span>
      </button>
      {expanded &&
        children.map((child) => (
          <TreeNodeView key={child.path} node={child} depth={depth + 1} />
        ))}
    </div>
  );
}

interface FileTreeViewerProps {
  fileTree: FileTreeEntry[];
}

export default function FileTreeViewer({ fileTree }: FileTreeViewerProps) {
  const tree = buildTree(fileTree);
  const children = Array.from(tree.children.values()).sort((a, b) => {
    if (a.type !== b.type) return a.type === "dir" ? -1 : 1;
    return a.name.localeCompare(b.name);
  });

  return (
    <div className="bg-abyss border border-foam/8 rounded-lg overflow-hidden">
      <div className="px-4 py-2 bg-navy border-b border-foam/8">
        <span className="text-sm text-mist">
          Files ({fileTree.length})
        </span>
      </div>
      <div className="p-4 max-h-[70vh] overflow-y-auto font-mono text-xs leading-relaxed">
        {children.length === 0 ? (
          <span className="text-mist/50">No files...</span>
        ) : (
          children.map((child) => (
            <TreeNodeView key={child.path} node={child} depth={0} />
          ))
        )}
      </div>
    </div>
  );
}
