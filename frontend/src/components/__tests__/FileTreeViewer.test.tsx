import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { FileTreeEntry } from "../../types";
import FileTreeViewer from "../FileTreeViewer";

describe("FileTreeViewer", () => {
  it("shows 'No files...' when tree is empty", () => {
    render(<FileTreeViewer fileTree={[]} />);
    expect(screen.getByText("No files...")).toBeInTheDocument();
  });

  it("shows file count in header", () => {
    const fileTree: FileTreeEntry[] = [
      { path: "README.md", type: "file", size: 100 },
      { path: "src", type: "dir" },
      { path: "src/main.py", type: "file", size: 500 },
    ];
    render(<FileTreeViewer fileTree={fileTree} />);
    expect(screen.getByText("Files (3)")).toBeInTheDocument();
  });

  it("renders file names", () => {
    const fileTree: FileTreeEntry[] = [
      { path: "README.md", type: "file", size: 100 },
      { path: "package.json", type: "file", size: 200 },
    ];
    render(<FileTreeViewer fileTree={fileTree} />);
    expect(screen.getByText("README.md")).toBeInTheDocument();
    expect(screen.getByText("package.json")).toBeInTheDocument();
  });

  it("renders directory names with slash suffix", () => {
    const fileTree: FileTreeEntry[] = [
      { path: "src", type: "dir" },
      { path: "src/index.ts", type: "file", size: 50 },
    ];
    render(<FileTreeViewer fileTree={fileTree} />);
    expect(screen.getByText("src/")).toBeInTheDocument();
  });

  it("shows file sizes", () => {
    const fileTree: FileTreeEntry[] = [
      { path: "small.txt", type: "file", size: 512 },
      { path: "large.bin", type: "file", size: 2048 },
    ];
    render(<FileTreeViewer fileTree={fileTree} />);
    expect(screen.getByText("512 B")).toBeInTheDocument();
    expect(screen.getByText("2.0 KB")).toBeInTheDocument();
  });

  it("can toggle directory expansion", () => {
    const fileTree: FileTreeEntry[] = [
      { path: "deep", type: "dir" },
      { path: "deep/nested", type: "dir" },
      { path: "deep/nested/file.txt", type: "file", size: 10 },
    ];
    render(<FileTreeViewer fileTree={fileTree} />);

    // Top-level dir should be expanded by default (depth < 2)
    expect(screen.getByText("deep/")).toBeInTheDocument();

    // Click to collapse
    fireEvent.click(screen.getByText("deep/"));

    // Nested content should be hidden now
    expect(screen.queryByText("file.txt")).not.toBeInTheDocument();

    // Click to expand again
    fireEvent.click(screen.getByText("deep/"));
    expect(screen.getByText("file.txt")).toBeInTheDocument();
  });

  it("sorts directories before files", () => {
    const fileTree: FileTreeEntry[] = [
      { path: "z-file.txt", type: "file", size: 10 },
      { path: "a-dir", type: "dir" },
      { path: "a-dir/child.txt", type: "file", size: 5 },
    ];
    render(<FileTreeViewer fileTree={fileTree} />);

    const items = screen.getAllByText(/.+/);
    const dirIndex = items.findIndex((el) => el.textContent === "a-dir/");
    const fileIndex = items.findIndex((el) => el.textContent === "z-file.txt");
    expect(dirIndex).toBeLessThan(fileIndex);
  });
});
