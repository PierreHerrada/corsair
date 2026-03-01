import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { CostBreakdown, RunStage } from "../../types";
import CostWidget from "../CostWidget";

describe("CostWidget", () => {
  const costByStage: Record<RunStage, number> = {
    plan: 1.5,
    work: 3.25,
    review: 0.75,
  };

  it("renders cost by stage", () => {
    render(<CostWidget costs={[]} costByStage={costByStage} />);
    expect(screen.getByText("Cost by Stage")).toBeInTheDocument();
    expect(screen.getByText("$1.50")).toBeInTheDocument();
    expect(screen.getByText("$3.25")).toBeInTheDocument();
    expect(screen.getByText("$0.75")).toBeInTheDocument();
  });

  it("renders stage labels", () => {
    render(<CostWidget costs={[]} costByStage={costByStage} />);
    expect(screen.getByText("plan")).toBeInTheDocument();
    expect(screen.getByText("work")).toBeInTheDocument();
    expect(screen.getByText("review")).toBeInTheDocument();
  });

  it("does not show cost per task table when no costs", () => {
    render(<CostWidget costs={[]} costByStage={costByStage} />);
    expect(screen.queryByText("Cost per Task")).not.toBeInTheDocument();
  });

  it("renders cost per task table when costs provided", () => {
    const costs: CostBreakdown[] = [
      {
        task_id: "t1",
        task_title: "Fix login",
        total_cost_usd: 2.5,
        cost_by_stage: { plan: 0.5, work: 1.5, review: 0.5 },
      },
    ];
    render(<CostWidget costs={costs} costByStage={costByStage} />);
    expect(screen.getByText("Cost per Task")).toBeInTheDocument();
    expect(screen.getByText("Fix login")).toBeInTheDocument();
    expect(screen.getByText("$2.5000")).toBeInTheDocument();
  });

  it("renders multiple task rows", () => {
    const costs: CostBreakdown[] = [
      {
        task_id: "t1",
        task_title: "Task A",
        total_cost_usd: 1.0,
        cost_by_stage: { plan: 0.2, work: 0.6, review: 0.2 },
      },
      {
        task_id: "t2",
        task_title: "Task B",
        total_cost_usd: 2.0,
        cost_by_stage: { plan: 0.4, work: 1.2, review: 0.4 },
      },
    ];
    render(<CostWidget costs={costs} costByStage={costByStage} />);
    expect(screen.getByText("Task A")).toBeInTheDocument();
    expect(screen.getByText("Task B")).toBeInTheDocument();
  });
});
