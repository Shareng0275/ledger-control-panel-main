export const API_BASE_URL: string =
  (import.meta.env["VITE_API_BASE_URL"] as string | undefined)?.replace(/\/$/, "") ??
  "http://localhost:8000/api/v1";

const ACCESS_TOKEN_KEY = "ledger_control.token";
const REFRESH_TOKEN_KEY = "ledger_control.refresh_token";
const USER_KEY = "ledger_control.user";

export const tokenStore = {
  get(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(ACCESS_TOKEN_KEY);
  },
  set(token: string) {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(ACCESS_TOKEN_KEY, token);
  },
  getRefreshToken(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(REFRESH_TOKEN_KEY);
  },
  setRefreshToken(token: string) {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(REFRESH_TOKEN_KEY, token);
  },
  clear() {
    if (typeof window === "undefined") return;
    window.localStorage.removeItem(ACCESS_TOKEN_KEY);
    window.localStorage.removeItem(REFRESH_TOKEN_KEY);
    window.localStorage.removeItem(USER_KEY);
  },
  getUserRaw(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(USER_KEY);
  },
  setUserRaw(value: string) {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(USER_KEY, value);
  },
};

export class ApiError extends Error {
  status: number;
  payload: unknown;
  constructor(message: string, status: number, payload?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
  get isUnauthorized() {
    return this.status === 401 || this.status === 403;
  }
}

type SessionExpiredHandler = () => void;
let onSessionExpired: SessionExpiredHandler | null = null;
export function setSessionExpiredHandler(fn: SessionExpiredHandler | null) {
  onSessionExpired = fn;
}

/**
 * Normalizes a path against the configured API base URL.
 */
function resolveUrl(path: string) {
  let p = path.startsWith("/") ? path : `/${path}`;
  if (/\/v\d+$/.test(API_BASE_URL) && /^\/v\d+\//.test(p)) {
    p = p.replace(/^\/v\d+/, "");
  }
  return `${API_BASE_URL}${p}`;
}

interface RequestOptions {
  method?: string | undefined;
  body?: unknown;
  signal?: AbortSignal | undefined;
  auth?: boolean | undefined;
  headers?: Record<string, string> | undefined;
  _retry?: boolean;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, signal, auth = true, headers = {}, _retry = false } = options;

  const finalHeaders: Record<string, string> = { Accept: "application/json", ...headers };
  const isForm = typeof FormData !== "undefined" && body instanceof FormData;
  if (body !== undefined && !isForm) finalHeaders["Content-Type"] = "application/json";

  if (auth) {
    const token = tokenStore.get();
    if (token) finalHeaders["Authorization"] = `Bearer ${token}`;
  }

  let res: Response;
  const init: RequestInit = { method, headers: finalHeaders };
  if (signal) init.signal = signal;
  if (body !== undefined) init.body = isForm ? (body as FormData) : JSON.stringify(body);

  try {
    res = await fetch(resolveUrl(path), init);
  } catch {
    throw new ApiError("Cannot reach the reconciliation service.", 0);
  }

  // Handle Silent Refresh Token Rotation on 401 Unauthorized
  if (res.status === 401 && auth && !_retry && !path.includes("/auth/")) {
    const refreshToken = tokenStore.getRefreshToken();
    if (refreshToken) {
      try {
        const refreshRes = await fetch(resolveUrl("/v1/auth/refresh"), {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ refreshToken }),
        });

        if (refreshRes.ok) {
          const refreshData = await refreshRes.json();
          const newAccess = refreshData.access_token || refreshData.token;
          const newRefresh = refreshData.refresh_token;
          if (newAccess) tokenStore.set(newAccess);
          if (newRefresh) tokenStore.setRefreshToken(newRefresh);

          // Retry original request once with new access token
          return await apiRequest<T>(path, { ...options, _retry: true });
        }
      } catch {
        // Fall through to session expiration
      }
    }
  }

  const text = await res.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }

  if (!res.ok) {
    if ((res.status === 401 || res.status === 403) && !path.includes("/auth/login")) {
      tokenStore.clear();
      onSessionExpired?.();
    }
    const detail =
      (payload as { detail?: string; message?: string; error?: string } | null)?.detail ??
      (payload as { message?: string } | null)?.message ??
      (payload as { error?: string } | null)?.error;
    throw new ApiError(detail || `Request failed (${res.status})`, res.status, payload);
  }

  return payload as T;
}
