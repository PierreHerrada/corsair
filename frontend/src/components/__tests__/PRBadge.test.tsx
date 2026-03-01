import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import PRBadge from "../PRBadge";

describe("PRBadge", () => {
  it("renders PR number", () => {
    render(<PRBadge url="https://github.com/pr/42" number={42} />);
    expect(screen.getByText("PR #42")).toBeInTheDocument();
  });

  it("renders PR without number", () => {
    render(<PRBadge url="https://github.com/pr/1" number={null} />);
    expect(screen.getByText(/^PR\s*$/)).toBeInTheDocument();
  });

  it("links to the PR URL", () => {
    render(<PRBadge url="https://github.com/pr/42" number={42} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "https://github.com/pr/42");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });
});
