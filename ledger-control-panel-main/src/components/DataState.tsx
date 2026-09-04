import { AlertOctagon, Inbox, Loader2, RefreshCw } from "lucide-react";

import { cn } from "@/lib/utils";

export function LoadingState({
  label = "Loading",
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-center justify-center gap-2.5 px-4 py-14 text-[var(--ledger-text-muted)]",
        className,
      )}
      role="status"
      aria-live="polite"
    >
      <Loader2 className="size-4 animate-spin text-[var(--ledger-primary)]" aria-hidden />
      <span className="label-micro font-mono tracking-wider">{label}…</span>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
  className,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 px-6 py-14 text-center",
        className,
      )}
    >
      <div className="flex size-10 items-center justify-center rounded-[4px] bg-[var(--ledger-surface-elevated)] border border-[var(--ledger-border)] text-[var(--ledger-text-muted)]">
        <Inbox className="size-5" aria-hidden />
      </div>
      <div>
        <p className="font-display text-sm font-semibold text-[var(--ledger-text)]">{title}</p>
        {description ? (
          <p className="mt-1 max-w-md text-xs text-[var(--ledger-text-muted)]">{description}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

export function ErrorState({
  title = "Request failed",
  message,
  onRetry,
  className,
}: {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 px-6 py-14 text-center",
        className,
      )}
      role="alert"
    >
      <div className="flex size-10 items-center justify-center rounded-[4px] bg-[rgba(239,68,68,0.12)] border border-[rgba(239,68,68,0.25)] text-[var(--lc-danger)]">
        <AlertOctagon className="size-5" aria-hidden />
      </div>
      <div>
        <p className="font-display text-sm font-semibold text-[var(--lc-danger)]">{title}</p>
        <p className="mt-1 max-w-md text-xs text-[var(--lc-text-muted)]">
          {message || "The backend did not return data for this view."}
        </p>
      </div>
      {onRetry ? (
        <button type="button" onClick={onRetry} className="lc-btn lc-btn--secondary text-xs mt-1">
          <RefreshCw className="size-3.5" aria-hidden />
          Retry
        </button>
      ) : null}
    </div>
  );
}
