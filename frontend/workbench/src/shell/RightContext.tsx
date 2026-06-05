import type { ReactNode } from "react";

export function RightContext({ title, children }: { title: string; children: ReactNode }) {
  return (
    <aside className="right-context" aria-label={title}>
      <h2>{title}</h2>
      {children}
    </aside>
  );
}
