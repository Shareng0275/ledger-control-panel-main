import { createFileRoute } from "@tanstack/react-router";
import {
  CornerDownLeft,
  Loader2,
  Sparkles,
  Bot,
  User,
  Database,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/DataState";
import { AppShell } from "@/layouts/AppShell";
import { ask } from "@/services/ledger";

export const Route = createFileRoute("/ask")({
  head: () => ({
    meta: [
      { title: "Financial AI Copilot — Ledger Control" },
      {
        name: "description",
        content:
          "Ask natural-language questions about reconciled ledger activity and read backend AI answers with supporting rows.",
      },
      { property: "og:title", content: "Financial AI Copilot — Ledger Control" },
      {
        property: "og:description",
        content: "Natural-language financial analysis grounded in backend ledger data.",
      },
    ],
  }),
  component: AskPage,
});

const PROMPTS = [
  "Which exceptions carry the highest value at risk?",
  "Summarise settlement gaps between bank and gateway this period.",
  "Where is confidence lowest in the latest reconciliation run?",
];

type Turn =
  | { role: "user"; id: string; question: string }
  | {
      role: "assistant";
      id: string;
      question: string;
      answer: string;
      rows: Array<Record<string, unknown>>;
    };

function EvidenceTable({ rows }: { rows: Array<Record<string, unknown>> }) {
  const [expanded, setExpanded] = useState(true);

  if (!rows || rows.length === 0 || !rows[0]) return null;

  return (
    <div className="rounded-[6px] border border-[var(--lc-border)] bg-[var(--lc-bg)] p-3">
      <div className="flex items-center justify-between pb-2">
        <p className="label-micro text-[var(--lc-text-muted)] flex items-center gap-1.5">
          <Database className="size-3 text-[var(--lc-accent)]" />
          Grounded Database Evidence ({rows.length} records)
        </p>
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-[11px] font-mono text-[var(--lc-text-muted)] hover:text-[var(--lc-text-primary)] transition-colors"
        >
          <span>{expanded ? "Collapse" : "Expand"}</span>
          {expanded ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
        </button>
      </div>

      {expanded && (
        <div className="overflow-x-auto border-t border-[var(--lc-border)] pt-2">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="border-b border-[var(--lc-border)] text-left text-[10px] text-[var(--lc-text-muted)]">
                {Object.keys(rows[0] || {})
                  .slice(0, 6)
                  .map((k) => (
                    <th key={k} className="p-1.5 uppercase font-semibold">
                      {k}
                    </th>
                  ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--lc-border-subtle)] text-[11px] text-[var(--lc-text-secondary)]">
              {rows.map((r, i) => (
                <tr key={i} className="hover:bg-[rgba(168,85,247,0.04)]">
                  {Object.values(r)
                    .slice(0, 6)
                    .map((v, j) => (
                      <td key={j} className="p-1.5 truncate max-w-[160px]">
                        {String(v ?? "—")}
                      </td>
                    ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function AskPage() {
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [error, setError] = useState<{ question: string; message: string } | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [turns, pending, error]);

  async function submit(q: string) {
    const trimmed = q.trim();
    if (!trimmed || pending) return;
    setPending(true);
    setError(null);
    setQuestion("");
    setTurns((prev) => [...prev, { role: "user", id: `${Date.now()}-q`, question: trimmed }]);
    try {
      const res = await ask(trimmed);
      setTurns((prev) => [
        ...prev,
        {
          role: "assistant",
          id: `${Date.now()}-a`,
          question: trimmed,
          answer: res.answer,
          rows: Array.isArray(res.supporting_rows) ? res.supporting_rows : [],
        },
      ]);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "The controller could not answer the query.";
      setError({ question: trimmed, message });
      toast.error(message);
    } finally {
      setPending(false);
    }
  }

  return (
    <AppShell
      title="Financial AI Copilot"
      description="Natural language queries grounded in real-time verified ledger databases and exception state."
    >
      <div className="flex h-[calc(100vh-140px)] flex-col gap-3">
        {/* Suggested Prompts Strip */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="label-micro text-[var(--lc-text-muted)] flex items-center gap-1.5">
            <Sparkles className="size-3 text-[var(--lc-accent)]" />
            Quick Inquiries:
          </span>
          {PROMPTS.map((p) => (
            <button
              key={p}
              type="button"
              disabled={pending}
              onClick={() => void submit(p)}
              className="rounded-[4px] border border-[var(--lc-border)] bg-[var(--lc-surface)] px-2.5 py-1 text-left text-xs font-medium text-[var(--lc-text-secondary)] transition-all hover:border-[var(--lc-accent)] hover:text-[var(--lc-text-primary)] hover:bg-[rgba(168,85,247,0.06)] disabled:opacity-50"
            >
              {p}
            </button>
          ))}
        </div>

        {/* Conversation Stream */}
        <div
          ref={scrollRef}
          className="panel flex-1 space-y-4 overflow-y-auto p-4 bg-[var(--lc-surface)] border border-[var(--lc-border)] rounded-[6px]"
        >
          {turns.length === 0 && !pending && !error ? (
            <EmptyState
              title="Financial Intelligence Console Ready"
              description="Inquire about settlement gaps, reconciliation confidence anomalies, break isolation, or forward cash flows."
            />
          ) : null}

          {turns.map((t) => {
            if (t.role === "user") {
              return (
                <div key={t.id} className="flex justify-end">
                  <div className="lc-chat-user flex items-start gap-2.5">
                    <p className="text-xs font-medium text-[var(--lc-text-primary)] leading-relaxed">
                      {t.question}
                    </p>
                    <User className="size-3.5 mt-0.5 text-[var(--lc-accent)] shrink-0" />
                  </div>
                </div>
              );
            }

            return (
              <div key={t.id} className="flex justify-start">
                <div className="lc-chat-assistant space-y-3">
                  <div className="flex items-center gap-2 border-b border-[var(--lc-border)] pb-2 text-[var(--lc-accent)]">
                    <Bot className="size-4" />
                    <span className="font-display text-xs font-bold">
                      Ledger Controller Analysis
                    </span>
                  </div>

                  <p className="whitespace-pre-wrap text-xs text-[var(--lc-text-primary)] leading-relaxed">
                    {t.answer}
                  </p>

                  <EvidenceTable rows={t.rows} />
                </div>
              </div>
            );
          })}

          {pending ? (
            <div className="flex justify-start">
              <div className="lc-chat-assistant flex items-center gap-2.5 text-xs text-[var(--lc-text-muted)]">
                <Loader2 className="size-4 animate-spin text-[var(--lc-accent)]" />
                <span className="font-mono">Analyzing reconciled ledger data…</span>
              </div>
            </div>
          ) : null}

          {error ? (
            <div className="flex justify-start">
              <div className="lc-chat-assistant border-[rgba(239,68,68,0.3)] bg-[rgba(239,68,68,0.06)]">
                <p className="text-xs font-semibold text-[var(--lc-danger)]">
                  Analysis Query Failed
                </p>
                <p className="mt-1 text-xs text-[var(--lc-text-muted)]">{error.message}</p>
                <button
                  type="button"
                  onClick={() => void submit(error.question)}
                  className="lc-btn lc-btn--secondary text-xs mt-2"
                >
                  Retry Analysis
                </button>
              </div>
            </div>
          ) : null}
        </div>

        {/* Query Input Box */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void submit(question);
          }}
          className="flex items-center gap-2 rounded-[6px] border border-[var(--lc-border)] bg-[var(--lc-surface)] p-2 shadow-sm focus-within:border-[var(--lc-accent)] transition-colors"
        >
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={pending}
            placeholder="Ask anything regarding ledger discrepancies, transaction confidence, cash trends..."
            aria-label="Ask controller question"
            className="flex-1 bg-transparent px-2 text-xs text-[var(--lc-text-primary)] placeholder-[var(--lc-text-muted)] outline-none"
          />
          <button
            type="submit"
            disabled={!question.trim() || pending}
            className="lc-btn lc-btn--primary text-xs py-1.5 px-3"
            aria-label="Submit question"
          >
            <span>Analyze</span>
            <CornerDownLeft className="size-3.5" />
          </button>
        </form>
      </div>
    </AppShell>
  );
}
