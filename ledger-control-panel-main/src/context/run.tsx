import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

const RUN_KEY = "ledger_control.active_run";

interface RunState {
  runId: string | null;
  setRunId: (id: string | null) => void;
}

const RunContext = createContext<RunState | null>(null);

export function RunProvider({ children }: { children: React.ReactNode }) {
  const [runId, setRunIdState] = useState<string | null>(null);

  useEffect(() => {
    const stored = window.localStorage.getItem(RUN_KEY);
    if (stored) setRunIdState(stored);
  }, []);

  const setRunId = useCallback((id: string | null) => {
    setRunIdState(id);
    if (typeof window === "undefined") return;
    if (id) window.localStorage.setItem(RUN_KEY, id);
    else window.localStorage.removeItem(RUN_KEY);
  }, []);

  const value = useMemo(() => ({ runId, setRunId }), [runId, setRunId]);
  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
}

export function useRun() {
  const ctx = useContext(RunContext);
  if (!ctx) throw new Error("useRun must be used inside <RunProvider>");
  return ctx;
}
