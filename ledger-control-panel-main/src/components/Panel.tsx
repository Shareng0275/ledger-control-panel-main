import { cn } from "@/lib/utils";

export function Panel({
  title,
  subtitle,
  actions,
  children,
  className,
  bodyClassName,
}: {
  title?: string;
  subtitle?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section
      className={cn(
        "panel overflow-hidden bg-[var(--lc-surface)] border border-[var(--lc-border)] rounded-[6px] shadow-sm",
        className,
      )}
    >
      {title || actions ? (
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--lc-border)] px-4 py-3 bg-[var(--lc-surface-elevated)]">
          <div>
            {title ? (
              <h2 className="font-display text-sm font-semibold text-[var(--lc-text-primary)]">
                {title}
              </h2>
            ) : null}
            {subtitle ? (
              <p className="mt-0.5 text-xs text-[var(--lc-text-muted)] font-mono">{subtitle}</p>
            ) : null}
          </div>
          {actions ? (
            <div className="flex flex-wrap items-center gap-2 text-xs">{actions}</div>
          ) : null}
        </header>
      ) : null}
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}

export function Metric({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "default" | "verify" | "gold" | "amber" | "risk";
}) {
  const toneClass = {
    default: "text-[var(--lc-text-primary)]",
    verify: "text-[var(--lc-success)]",
    gold: "text-[var(--lc-accent)]",
    amber: "text-[var(--lc-warning)]",
    risk: "text-[var(--lc-danger)]",
  }[tone];

  return (
    <div className="border-r border-[var(--lc-border)] px-4 py-3 last:border-r-0">
      <p className="label-micro text-[var(--lc-text-muted)]">{label}</p>
      <p className={cn("num mt-1 text-lg font-bold font-mono tracking-tight", toneClass)}>
        {value}
      </p>
      {hint ? <p className="mt-0.5 text-[11px] text-[var(--lc-text-muted)]">{hint}</p> : null}
    </div>
  );
}
