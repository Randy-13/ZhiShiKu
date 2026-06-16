export function EmptyState({ title, body }: { title: string; body?: string }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      {body ? <p>{body}</p> : null}
    </div>
  );
}
