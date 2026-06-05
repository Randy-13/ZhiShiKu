import type { TaskStatus } from "../domain";

export function StatusBadge({ tone, children }: { tone: TaskStatus | "muted"; children: string }) {
  return <span className={`status-badge ${tone}`}>{children}</span>;
}
