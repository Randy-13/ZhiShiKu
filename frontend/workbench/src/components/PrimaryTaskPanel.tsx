import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";

export function PrimaryTaskPanel({
  eyebrow,
  title,
  body,
  action,
  disabled,
  disabledReason,
  children,
  onAction,
}: {
  eyebrow: string;
  title: string;
  body: string;
  action?: string;
  disabled?: boolean;
  disabledReason?: string;
  children?: ReactNode;
  onAction?: () => void;
}) {
  return (
    <section className="primary-task-panel">
      <div>
        <span>{eyebrow}</span>
        <h2>{title}</h2>
        <p>{body}</p>
      </div>
      {children ? <div className="primary-task-content">{children}</div> : null}
      {action && onAction ? (
        <button className="primary-cta" type="button" disabled={disabled} onClick={onAction}>
          <strong>{action}</strong>
          <ChevronRight size={18} />
        </button>
      ) : null}
      {disabled && disabledReason ? <p className="disabled-reason">{disabledReason}</p> : null}
    </section>
  );
}
