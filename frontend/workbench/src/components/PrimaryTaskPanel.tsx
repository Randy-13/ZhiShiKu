import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";

export function PrimaryTaskPanel({
  className,
  eyebrow,
  title,
  body,
  status,
  action,
  disabled,
  disabledReason,
  children,
  onAction,
}: {
  className?: string;
  eyebrow: string;
  title: string;
  body?: string;
  status?: ReactNode;
  action?: string;
  disabled?: boolean;
  disabledReason?: string;
  children?: ReactNode;
  onAction?: () => void;
}) {
  return (
    <section className={className ? `primary-task-panel ${className}` : "primary-task-panel"}>
      <div className="primary-task-header">
        <div className="primary-task-copy">
          <span>{eyebrow}</span>
          <h2>{title}</h2>
          {body ? <p>{body}</p> : null}
        </div>
        {status ? <div className="primary-task-status">{status}</div> : null}
      </div>
      {children ? <div className="primary-task-content">{children}</div> : null}
      {action && onAction ? (
        <div className="primary-task-actions">
          <button className="primary-cta" type="button" disabled={disabled} onClick={onAction}>
            <strong>{action}</strong>
            <ChevronRight size={18} />
          </button>
          {disabled && disabledReason ? <p className="disabled-reason">{disabledReason}</p> : null}
        </div>
      ) : disabled && disabledReason ? <p className="disabled-reason">{disabledReason}</p> : null}
    </section>
  );
}
