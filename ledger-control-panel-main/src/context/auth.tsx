import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { apiRequest, setSessionExpiredHandler, tokenStore } from "@/lib/api";
import type { LoginResponse, User } from "@/types";

interface AuthState {
  user: User | null;
  token: string | null;
  restoring: boolean;
  isAuthenticated: boolean;
  sessionId: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: (reason?: string) => void;
  switchRole: (role: Role | string) => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [restoring, setRestoring] = useState(true);

  // Session restoration happens after hydration so SSR output stays stable.
  useEffect(() => {
    const stored = tokenStore.get();
    const rawUser = tokenStore.getUserRaw();
    if (stored) {
      setToken(stored);
      if (rawUser) {
        try {
          setUser(JSON.parse(rawUser) as User);
        } catch {
          setUser(null);
        }
      }
      // Ensure a persistent session id exists in sessionStorage
      let activeSess = typeof window !== "undefined" ? sessionStorage.getItem("lc_active_session_id") : null;
      if (!activeSess) {
        activeSess = `sess_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
        try {
          sessionStorage.setItem("lc_active_session_id", activeSess);
          sessionStorage.setItem("lc_session_login_time", Date.now().toString());
        } catch {}
      }
      setSessionId(activeSess);
    }
    setRestoring(false);
  }, []);

  const logout = useCallback((reason?: string) => {
    const refreshToken = tokenStore.getRefreshToken();
    if (refreshToken) {
      void apiRequest("/v1/auth/logout", {
        method: "POST",
        auth: false,
        body: { refreshToken },
      }).catch(() => {});
    }
    try {
      sessionStorage.removeItem("lc_active_session_id");
      sessionStorage.removeItem("lc_session_login_time");
    } catch {}
    tokenStore.clear();
    setToken(null);
    setUser(null);
    setSessionId(null);
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("lc-auth-logout"));
    }
    if (reason) toast.error(reason);
  }, []);

  useEffect(() => {
    setSessionExpiredHandler(() => {
      tokenStore.clear();
      setToken(null);
      setUser(null);
      setSessionId(null);
      toast.error("Session expired. Sign in again to continue.");
    });
    return () => setSessionExpiredHandler(null);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await apiRequest<LoginResponse>("/v1/auth/login", {
      method: "POST",
      auth: false,
      body: { email, password },
    });
    const token = res.access_token || res.token;
    if (!token) throw new Error("Login response did not include a session token.");
    
    // Generate a fresh unique session identifier on every explicit login
    const newSessionId = `sess_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    try {
      sessionStorage.setItem("lc_active_session_id", newSessionId);
      sessionStorage.setItem("lc_session_login_time", Date.now().toString());
    } catch {}

    tokenStore.set(token);
    if (res.refresh_token) {
      tokenStore.setRefreshToken(res.refresh_token);
    }
    tokenStore.setUserRaw(JSON.stringify(res.user ?? {}));
    setToken(token);
    setUser(res.user ?? null);
    setSessionId(newSessionId);

    // Dispatch global event notifying that a fresh login occurred
    if (typeof window !== "undefined") {
      window.dispatchEvent(
        new CustomEvent("lc-auth-login", {
          detail: {
            sessionId: newSessionId,
            user: res.user,
            timestamp: Date.now(),
          },
        }),
      );
    }
  }, []);

  const switchRole = useCallback((newRole: Role | string) => {
    setUser((prev) => {
      if (!prev) return null;
      const updated: User = { ...prev, role: newRole };
      tokenStore.setUserRaw(JSON.stringify(updated));
      if (typeof window !== "undefined") {
        window.dispatchEvent(
          new CustomEvent("lc-role-changed", {
            detail: {
              previousRole: prev.role,
              role: newRole,
              timestamp: Date.now(),
            },
          }),
        );
      }
      return updated;
    });
    toast.success(`Role updated to ${String(newRole).toUpperCase()}`);
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      token,
      restoring,
      isAuthenticated: Boolean(token),
      sessionId,
      login,
      logout,
      switchRole,
    }),
    [user, token, restoring, sessionId, login, logout, switchRole],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
