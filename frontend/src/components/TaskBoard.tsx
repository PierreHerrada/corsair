import {
  DndContext,
  DragOverlay,
  MouseSensor,
  TouchSensor,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { useState } from "react";
import { updateTaskStatus } from "../api/tasks";
import type { Task, TaskStatus } from "../types";
import TaskCard from "./TaskCard";

const COLUMNS: { status: TaskStatus; label: string }[] = [
  { status: "backlog", label: "Backlog" },
  { status: "planned", label: "Planned" },
  { status: "working", label: "Working" },
  { status: "reviewing", label: "Reviewing" },
  { status: "done", label: "Done" },
  { status: "failed", label: "Failed" },
];

interface TaskBoardProps {
  tasks: Task[];
  onRefresh: () => void;
}

function DroppableColumn({
  status,
  label,
  tasks,
  onRefresh,
  isOver,
}: {
  status: TaskStatus;
  label: string;
  tasks: Task[];
  onRefresh: () => void;
  isOver: boolean;
}) {
  const { setNodeRef } = useDroppable({ id: status });

  return (
    <div ref={setNodeRef} className="min-w-[280px] flex-shrink-0">
      <div className="flex items-center gap-2 mb-3">
        <h2 className="text-sm font-medium text-mist uppercase tracking-wide">
          {label}
        </h2>
        <span className="text-xs bg-navy px-1.5 py-0.5 rounded text-foam">
          {tasks.length}
        </span>
      </div>
      <div
        className={`min-h-[60px] rounded-lg transition-colors ${isOver ? "bg-sky/10 ring-2 ring-sky/40" : ""}`}
      >
        {tasks.map((task) => (
          <TaskCard key={task.id} task={task} onRefresh={onRefresh} />
        ))}
        {tasks.length === 0 && (
          <div className="text-xs text-mist/50 text-center py-8 border border-dashed border-horizon/30 rounded-lg">
            No tasks
          </div>
        )}
      </div>
    </div>
  );
}

export default function TaskBoard({ tasks, onRefresh }: TaskBoardProps) {
  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 8 } }),
    useSensor(TouchSensor, {
      activationConstraint: { delay: 200, tolerance: 5 },
    }),
  );
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const [overId, setOverId] = useState<string | null>(null);

  async function handleDragEnd(event: DragEndEvent) {
    setActiveTask(null);
    setOverId(null);
    const { active, over } = event;
    if (!over) return;
    const taskId = active.id as string;
    const newStatus = over.id as TaskStatus;
    const task = active.data.current?.task as Task | undefined;
    if (!task || task.status === newStatus) return;
    await updateTaskStatus(taskId, newStatus);
    onRefresh();
  }

  function handleDragStart(event: DragStartEvent) {
    setActiveTask((event.active.data.current?.task as Task) ?? null);
  }

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragOver={(e) => setOverId((e.over?.id as string) ?? null)}
      onDragEnd={handleDragEnd}
    >
      <div className="flex gap-4 overflow-x-auto pb-4">
        {COLUMNS.map((col) => {
          const columnTasks = tasks.filter((t) => t.status === col.status);
          return (
            <DroppableColumn
              key={col.status}
              status={col.status}
              label={col.label}
              tasks={columnTasks}
              onRefresh={onRefresh}
              isOver={overId === col.status}
            />
          );
        })}
      </div>
      <DragOverlay>
        {activeTask ? (
          <div className="opacity-80 pointer-events-none">
            <TaskCard task={activeTask} onRefresh={() => {}} />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
