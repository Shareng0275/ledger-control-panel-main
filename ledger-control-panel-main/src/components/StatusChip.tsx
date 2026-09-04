import React from "react";
import { AlertTriangle, CheckCircle2, Clock, CircleDashed, ShieldAlert } from "lucide-react";

import { cn } from "@/lib/utils";
import type { TxStatus } from "@/types";

const MAP: Record<
  string,
  { label: string; bg: string; text: string; border: string; Icon: typeof CheckCircle2 }
> = {
  matched: {
    label: "Matched",
    bg: "rgba(34, 197, 94, 0.12)",
    text: "#22C55E",
    border: "rgba(34, 197, 94, 0.25)",
    Icon: CheckCircle2,
  },
  exception: {
    label: "Exception",
    bg: "rgba(239, 68, 68, 0.12)",
    text: "#EF4444",
    border: "rgba(239, 68, 68, 0.25)",
    Icon: AlertTriangle,
  },
  pending_review: {
    label: "Pending Review",
    bg: "rgba(245, 158, 11, 0.12)",
    text: "#F59E0B",
    border: "rgba(245, 158, 11, 0.25)",
    Icon: Clock,
  },
  high_risk: {
    label: "High Risk",
    bg: "rgba(239, 68, 68, 0.2)",
    text: "#F87171",
    border: "rgba(239, 68, 68, 0.4)",
    Icon: ShieldAlert,
  },
};

export const StatusChip = React.memo(function StatusChip({
  status,
  className,
}: {
  status: TxStatus | string;
  className?: string;
}) {
  const conf = MAP[status] ?? {
    label: String(status).replace(/_/g, " "),
    bg: "rgba(255, 255, 255, 0.06)",
    text: "#A7A7B0",
    border: "rgba(255, 255, 255, 0.12)",
    Icon: CircleDashed,
  };
  const { Icon } = conf;
  return (
    <span
      style={{
        backgroundColor: conf.bg,
        color: conf.text,
        borderColor: conf.border,
      }}
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-[4px] border font-mono text-[11px] font-semibold tracking-wide",
        className,
      )}
    >
      <Icon className="size-3 shrink-0" aria-hidden />
      <span>{conf.label}</span>
    </span>
  );
});
