import type { SessionGuideState, GuideStatus } from "./guideTypes";

const MEMORY_STORAGE: Record<string, string> = {};

function safeSessionGet(key: string): string | null {
  try {
    if (typeof window !== "undefined" && window.sessionStorage) {
      return window.sessionStorage.getItem(key);
    }
  } catch {
    // Incognito or security sandbox fallback
  }
  return MEMORY_STORAGE[key] ?? null;
}

function safeSessionSet(key: string, value: string): void {
  try {
    if (typeof window !== "undefined" && window.sessionStorage) {
      window.sessionStorage.setItem(key, value);
    }
  } catch {
    // Incognito or quota exceeded
  }
  MEMORY_STORAGE[key] = value;
}

function safeLocalGet(key: string): string | null {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      return window.localStorage.getItem(key);
    }
  } catch {
    // Fallback
  }
  return MEMORY_STORAGE[key] ?? null;
}

function safeLocalSet(key: string, value: string): void {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      window.localStorage.setItem(key, value);
    }
  } catch {
    // Fallback
  }
  MEMORY_STORAGE[key] = value;
}

const SESSION_KEY = "lc_active_session_id";
const SYNC_CHANNEL_NAME = "lc_guide_broadcast_v1";

let syncChannel: BroadcastChannel | null = null;
try {
  if (typeof window !== "undefined" && "BroadcastChannel" in window) {
    syncChannel = new BroadcastChannel(SYNC_CHANNEL_NAME);
  }
} catch {
  syncChannel = null;
}

export const guideStorage = {
  /**
   * Retrieves or initializes the active login session identifier
   */
  getOrCreateSessionId(): string {
    let sessId = safeSessionGet(SESSION_KEY);
    if (!sessId) {
      sessId = `sess_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      safeSessionSet(SESSION_KEY, sessId);
    }
    return sessId;
  },

  /**
   * Clears the current session id on explicit logout
   */
  clearSession(): void {
    try {
      if (typeof window !== "undefined" && window.sessionStorage) {
        window.sessionStorage.removeItem(SESSION_KEY);
      }
    } catch {}
    delete MEMORY_STORAGE[SESSION_KEY];
  },

  /**
   * Retrieves session state for the given user and session ID
   */
  getSessionState(userId: string, sessionId: string): SessionGuideState | null {
    const key = `lc_guide_state_${userId}_${sessionId}`;
    const raw = safeSessionGet(key) || safeLocalGet(key);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as SessionGuideState;
    } catch {
      return null;
    }
  },

  /**
   * Saves or updates session guide state and broadcasts across concurrent tabs
   */
  setSessionState(userId: string, state: SessionGuideState): void {
    const key = `lc_guide_state_${userId}_${state.sessionId}`;
    const payload = JSON.stringify(state);
    safeSessionSet(key, payload);
    safeLocalSet(key, payload);

    if (syncChannel) {
      try {
        syncChannel.postMessage({ type: "GUIDE_STATE_UPDATE", userId, state });
      } catch {}
    }
  },

  /**
   * Marks guide as dismissed for this specific session
   */
  dismissSession(userId: string, sessionId: string, role: string, step: number): void {
    const state: SessionGuideState = {
      sessionId,
      userId,
      role,
      step,
      status: "dismissed",
      dismissedAt: Date.now(),
      updatedAt: Date.now(),
    };
    guideStorage.setSessionState(userId, state);
  },

  /**
   * Marks guide as completed for this specific session
   */
  completeSession(userId: string, sessionId: string, role: string, step: number): void {
    const state: SessionGuideState = {
      sessionId,
      userId,
      role,
      step,
      status: "completed",
      completedAt: Date.now(),
      updatedAt: Date.now(),
    };
    guideStorage.setSessionState(userId, state);
  },

  /**
   * Subscribe to multi-tab guide synchronization events
   */
  onSync(callback: (state: SessionGuideState) => void): () => void {
    if (!syncChannel) return () => {};
    const handler = (event: MessageEvent) => {
      if (event.data?.type === "GUIDE_STATE_UPDATE" && event.data.state) {
        callback(event.data.state);
      }
    };
    syncChannel.addEventListener("message", handler);
    return () => {
      syncChannel?.removeEventListener("message", handler);
    };
  },
};
