import { Search, Upload } from "lucide-react";

export function Topbar({
  title,
  description,
  searchPlaceholder,
  importLabel,
  queueLabel,
  queueStatus,
  search,
  onSearchChange,
  onImport,
}: {
  title: string;
  description: string;
  searchPlaceholder: string;
  importLabel: string;
  queueLabel: string;
  queueStatus: string;
  search: string;
  onSearchChange: (value: string) => void;
  onImport: () => void;
}) {
  return (
    <header className="topbar">
      <div className="topbar-title">
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <label className="search-box">
        <Search size={17} />
        <input value={search} placeholder={searchPlaceholder} onChange={(event) => onSearchChange(event.target.value)} />
      </label>
      <button className="secondary-button" type="button" onClick={onImport}>
        <Upload size={17} />
        <span>{importLabel}</span>
      </button>
      <div className="queue-chip">
        <span>{queueLabel}</span>
        <strong>{queueStatus}</strong>
      </div>
    </header>
  );
}
