import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Eye, EyeOff, Loader2, Lock, Mail, User } from "lucide-react";
import { useState, useEffect } from "react";
import { toast } from "sonner";

import { useAuth } from "@/context/auth";
import { API_BASE_URL, ApiError } from "@/lib/api";
import "../lamp-login.css";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign in — Ledger Control" },
      {
        name: "description",
        content:
          "Authenticate to the Ledger Control reconciliation terminal with interactive lamp illumination.",
      },
      { property: "og:title", content: "Sign in — Ledger Control" },
      {
        property: "og:description",
        content: "Authenticate to the Ledger Control reconciliation terminal.",
      },
    ],
  }),
  component: LampLoginAnimation,
});

export default function LampLoginAnimation() {
  const { login, isAuthenticated, restoring } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [lampOn, setLampOn] = useState(false);

  // Tracks interactive pull-chain physics
  const [isPulling, setIsPulling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const urlError = params.get("error");
      if (urlError) {
        const decoded = decodeURIComponent(urlError);
        setError(decoded);
        toast.error(decoded);
        setLampOn(true);
      }
    }
    if (!restoring && isAuthenticated) void navigate({ to: "/", replace: true });
  }, [restoring, isAuthenticated, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setLampOn(true); // Turn on lamp
    setError(null);

    const trimmedEmail =
      email.trim() ||
      (username.includes("@") ? username.trim() : `${username.trim()}@ledgercontrol.com`);
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      setError("Please enter a valid work email address.");
      setIsLoading(false);
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      setIsLoading(false);
      return;
    }

    try {
      await login(trimmedEmail, password);
      toast.success("Session established");
      void navigate({ to: "/", replace: true });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.status === 401
            ? "Invalid credentials."
            : err.message
          : err instanceof Error
            ? err.message
            : "Login failed.";
      setError(message);
      toast.error(message);
    } finally {
      setTimeout(() => setIsLoading(false), 1200);
    }
  };

  const handlePullChain = () => {
    setIsPulling(true);
    setLampOn((prev) => !prev);
    setTimeout(() => setIsPulling(false), 800);
  };

  const handleOAuth = (provider: "Google" | "GitHub") => {
    setLampOn(true);
    toast.info(`Redirecting to ${provider} OAuth...`);
    setTimeout(() => {
      window.location.href = `${API_BASE_URL}/auth/${provider.toLowerCase()}`;
    }, 400);
  };

  return (
    <div className={`lamp-scene ${lampOn ? "lamp-scene--on" : "lamp-scene--off"}`}>
      {/* Ambient Vignette Overlay */}
      <div className="lamp-ambient-overlay" aria-hidden="true" />

      {/* Floating Animated Flying Elements (Glow Particles & Light Motes) */}
      <div className="lamp-particles" aria-hidden="true">
        <span className="fly-element f1" />
        <span className="fly-element f2" />
        <span className="fly-element f3" />
        <span className="fly-element f4" />
        <span className="fly-element f5" />
        <span className="fly-element f6" />
        <span className="fly-element f7" />
      </div>

      <div className="lamp-layout-container">
        {/* =================================================================== */}
        {/* 3D LAMP MODEL & ANCHORED LIGHT BEAM                                 */}
        {/* =================================================================== */}
        <div className={`lamp-fixture ${isPulling ? "lamp-fixture--swinging" : ""}`}>
          <div className="lamp-cord" />

          {/* Lamp Head & Shade Assembly */}
          <div className="lamp-shade-container">
            <div className="lamp-brass-cap" />
            <div className="lamp-shade">
              <div className="lamp-shade-rim" />
            </div>

            {/* Glowing Edison Bulb */}
            <div className="lamp-bulb-socket" />
            <div className="lamp-bulb">
              <div className="lamp-filament" />
            </div>

            {/* Interactive Pull Chain */}
            <button
              type="button"
              onClick={handlePullChain}
              className={`lamp-pull-chain ${isPulling ? "lamp-pull-chain--pulled" : ""}`}
              title="Click or pull chain to toggle lamp"
              aria-label="Toggle lamp power"
            >
              <div className="chain-link-line" />
              <div className="chain-bead" />
              <div className="chain-tassel" />
            </button>

            {/* Anchored Light Cone (Directly Under Shade Rim) */}
            <div className="lamp-light-cone" aria-hidden="true" />
          </div>

          {/* Stand Pole & Table Base */}
          <div className="lamp-stand-pole" />
          <div className="lamp-stand-base" />
          <div className="lamp-floor-glow" aria-hidden="true" />
        </div>

        {/* =================================================================== */}
        {/* AUTHENTICATION CARD                                                 */}
        {/* =================================================================== */}
        <div className="login-card-wrapper">
          {/* Unlit State Cue / Overlay Prompt */}
          {!lampOn && (
            <div
              onClick={handlePullChain}
              className="lamp-unlit-prompt"
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && handlePullChain()}
              aria-label="Pull lamp chain to illuminate"
            >
              <Lock className="unlit-lock-icon" />
              <p className="unlit-title">Terminal is in the dark</p>
              <span className="unlit-hint">Pull the hanging chain to illuminate</span>
            </div>
          )}

          {/* Main Login Card */}
          <div
            className={`login-card ${lampOn ? "login-card--illuminated" : "login-card--shrouded"}`}
          >
            <header className="login-header">
              <h1 className="login-title">Welcome Back</h1>
              <p className="login-subtitle">Enter your details to access your account</p>
            </header>

            <form onSubmit={handleSubmit} className="login-form">
              {/* Username Field */}
              <div className="form-group">
                <div className="input-wrapper">
                  <User className="input-icon" />
                  <input
                    id="username"
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="Username"
                    className="form-input"
                    autoComplete="username"
                    tabIndex={lampOn ? 0 : -1}
                  />
                </div>
              </div>

              {/* Email Field */}
              <div className="form-group">
                <div className="input-wrapper">
                  <Mail className="input-icon" />
                  <input
                    id="email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Email Address"
                    className="form-input"
                    autoComplete="email"
                    tabIndex={lampOn ? 0 : -1}
                  />
                </div>
              </div>

              {/* Password Field */}
              <div className="form-group">
                <div className="input-wrapper">
                  <Lock className="input-icon" />
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Password"
                    className="form-input password-input"
                    autoComplete="current-password"
                    tabIndex={lampOn ? 0 : -1}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((prev) => !prev)}
                    className="password-toggle-btn"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    tabIndex={lampOn ? 0 : -1}
                  >
                    {showPassword ? (
                      <EyeOff className="toggle-icon" />
                    ) : (
                      <Eye className="toggle-icon" />
                    )}
                  </button>
                </div>
              </div>

              {/* Error Alert */}
              {error ? (
                <p className="form-error" role="alert">
                  {error}
                </p>
              ) : null}

              {/* Sign In Button */}
              <button
                type="submit"
                disabled={isLoading}
                className="submit-btn"
                tabIndex={lampOn ? 0 : -1}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="btn-spinner" />
                    <span>Verifying...</span>
                  </>
                ) : (
                  <span>Sign In</span>
                )}
              </button>

              {/* OAuth Divider */}
              <div className="oauth-divider">
                <span className="oauth-divider-text">Or continue with</span>
              </div>

              {/* Google & GitHub OAuth Buttons */}
              <div className="oauth-grid">
                <button
                  type="button"
                  onClick={() => handleOAuth("Google")}
                  className="oauth-btn"
                  tabIndex={lampOn ? 0 : -1}
                >
                  <svg className="oauth-icon" viewBox="0 0 24 24">
                    <path
                      fill="#4285F4"
                      d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.66-5.17 3.66-9.17z"
                    />
                    <path
                      fill="#34A853"
                      d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.25v3.15C3.26 21.36 7.34 24 12 24z"
                    />
                    <path
                      fill="#FBBC05"
                      d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.25C.45 8.18 0 10.02 0 12s.45 3.82 1.25 5.42l4.03-3.15z"
                    />
                    <path
                      fill="#EA4335"
                      d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.34 0 3.26 2.64 1.25 6.58l4.03 3.15c.95-2.83 3.6-4.98 6.72-4.98z"
                    />
                  </svg>
                  <span>Google</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleOAuth("GitHub")}
                  className="oauth-btn"
                  tabIndex={lampOn ? 0 : -1}
                >
                  <svg className="oauth-icon" fill="currentColor" viewBox="0 0 24 24">
                    <path
                      fillRule="evenodd"
                      clipRule="evenodd"
                      d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
                    />
                  </svg>
                  <span>GitHub</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
