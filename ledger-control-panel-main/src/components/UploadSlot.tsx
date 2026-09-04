import { CheckCircle2, FileSpreadsheet, Loader2, Trash2, Upload, XCircle } from "lucide-react";
import { useRef } from "react";
import { cn } from "@/lib/utils";

export interface UploadSlotState {
  file: File | null;
  uploadId: string | null;
  rows?: number | null;
  status: "idle" | "uploading" | "ready" | "error";
  error?: string | null;
}

function formatBytes(bytes?: number): string {
  if (!bytes || bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function UploadSlot({
  code,
  title,
  description,
  state,
  disabled,
  onSelect,
  onRemove,
}: {
  code: string;
  title: string;
  description: string;
  state: UploadSlotState;
  disabled?: boolean;
  onSelect: (file: File) => void;
  onRemove?: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div
      className={cn(
        "panel flex flex-col justify-between gap-3 p-4 bg-[var(--lc-surface)] border border-[var(--lc-border)] rounded-[6px] shadow-sm transition-all duration-150 hover:border-[rgba(168,85,247,0.35)]",
        state.status === "ready" && "border-[rgba(34,197,94,0.35)] bg-[rgba(34,197,94,0.03)]",
        state.status === "error" && "border-[rgba(239,68,68,0.35)] bg-[rgba(239,68,68,0.03)]",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] font-bold text-[var(--lc-accent)] bg-[var(--lc-accent-muted)] border border-[rgba(168,85,247,0.2)] px-1.5 py-0.5 rounded-[3px]">
              {code}
            </span>
            <p className="font-display font-semibold text-xs text-[var(--lc-text-primary)]">
              {title}
            </p>
          </div>
          <p className="mt-1.5 text-xs text-[var(--lc-text-secondary)] leading-relaxed">
            {description}
          </p>
        </div>
        {state.status === "ready" ? (
          <CheckCircle2 className="size-4 shrink-0 text-[var(--lc-success)]" aria-hidden />
        ) : state.status === "uploading" ? (
          <Loader2 className="size-4 shrink-0 animate-spin text-[var(--lc-accent)]" aria-hidden />
        ) : state.status === "error" ? (
          <XCircle className="size-4 shrink-0 text-[var(--lc-danger)]" aria-hidden />
        ) : (
          <FileSpreadsheet className="size-4 shrink-0 text-[var(--lc-text-muted)]" aria-hidden />
        )}
      </div>

      <div className="border-t border-[var(--lc-border)] pt-3">
        {state.file ? (
          <div className="space-y-1">
            <div className="flex items-center justify-between gap-2">
              <p
                className="num truncate text-xs font-mono font-medium text-[var(--lc-text-primary)]"
                title={state.file.name}
              >
                {state.file.name}
              </p>
              <span className="text-[10px] font-mono text-[var(--lc-text-muted)] shrink-0">
                {formatBytes(state.file.size)}
              </span>
            </div>
            {state.status === "ready" ? (
              <p className="num text-[11px] font-mono text-[var(--lc-success)]">
                upload_id: {state.uploadId}
                {state.rows ? ` · ${state.rows} records verified` : ""}
              </p>
            ) : null}
            {state.status === "error" && state.error ? (
              <p className="text-[11px] font-mono text-[var(--lc-danger)]">{state.error}</p>
            ) : null}
          </div>
        ) : (
          <p className="text-xs text-[var(--lc-text-muted)]">No CSV file selected</p>
        )}
      </div>

      <div className="flex items-center gap-2 pt-1">
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          disabled={disabled || state.status === "uploading"}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onSelect(f);
            e.target.value = "";
          }}
        />
        <button
          type="button"
          disabled={disabled || state.status === "uploading"}
          onClick={() => inputRef.current?.click()}
          className="lc-btn lc-btn--secondary text-xs"
        >
          <Upload className="size-3.5" aria-hidden />
          {state.status === "uploading"
            ? "Uploading..."
            : state.file
              ? "Replace File"
              : "Choose CSV"}
        </button>

        {state.file && onRemove && (
          <button
            type="button"
            disabled={disabled || state.status === "uploading"}
            onClick={onRemove}
            className="lc-btn lc-btn--ghost text-xs p-1.5 text-[var(--lc-text-muted)] hover:text-[var(--lc-danger)]"
            title="Remove selected file"
          >
            <Trash2 className="size-3.5" aria-hidden />
          </button>
        )}
      </div>
    </div>
  );
}
