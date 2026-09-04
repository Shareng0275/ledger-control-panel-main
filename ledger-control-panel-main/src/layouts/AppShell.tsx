import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import {
  AlertTriangle,
  ClipboardList,
  LogOut,
  MessageSquareText,
  Scale,
  TrendingUp,
  Menu,
  X,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/auth";
import { useRun } from "@/context/run";
import { cn } from "@/lib/utils";
import { LoadingState } from "@/components/DataState";
import { hasPermission, type Permission } from "@/components/Can";
import {
  ProgressiveOnboarding,
  openProductGuide,
} from "@/components/onboarding/ProgressiveOnboarding";

/* Import the authenticated dark theme — scoped to .authenticated-app */
import "@/theme/theme.css";

const NAV = [
  {
    to: "/",
    label: "Reconcile",
    code: "R1",
    Icon: Scale,
    permission: "reconciliation.read" as Permission,
  },
  {
    to: "/exceptions",
    label: "Exceptions",
    code: "E2",
    Icon: AlertTriangle,
    permission: "reconciliation.read" as Permission,
  },
  {
    to: "/forecast",
    label: "Forecast",
    code: "F3",
    Icon: TrendingUp,
    permission: "analytics.read" as Permission,
  },
  {
    to: "/ask",
    label: "Ask AI",
    code: "A4",
    Icon: MessageSquareText,
    permission: "analytics.read" as Permission,
  },
  {
    to: "/audit",
    label: "Audit Log",
    code: "T5",
    Icon: ClipboardList,
    permission: "audit.read" as Permission,
  },
];

export function AppShell({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  const { isAuthenticated, restoring, user, logout } = useAuth();
  const { runId } = useRun();
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const [navOpen, setNavOpen] = useState(false);

  useEffect(() => {
    if (!restoring && !isAuthenticated) {
      void navigate({ to: "/login", replace: true });
    }
  }, [restoring, isAuthenticated, navigate]);

  useEffect(() => {
    setNavOpen(false);
  }, [pathname]);

  if (restoring || !isAuthenticated) {
    return (
      <div
        className="flex min-h-screen items-center justify-center"
        style={{ backgroundColor: "#0B090D" }}
      >
        <LoadingState label="Restoring enterprise session..." />
      </div>
    );
  }

  return (
    <div className="authenticated-app flex min-h-screen flex-col lg:flex-row">
      {/* ═══════════════════════════════════════════════════
          SIDEBAR — Premium Dark Navigation Rail
          ═══════════════════════════════════════════════════ */}
      <aside className="lc-sidebar">
        {/* Brand */}
        <div className="lc-sidebar__brand">
          <Link to="/" className="lc-sidebar__logo">
            <span className="lc-sidebar__logo-mark">
              <span>LC</span>
            </span>
            <span className="lc-sidebar__logo-name">LEDGER CONTROL</span>
          </Link>
          <button
            type="button"
            className="lc-sidebar__toggle"
            aria-label={navOpen ? "Close navigation" : "Open navigation"}
            aria-expanded={navOpen}
            onClick={() => setNavOpen((v) => !v)}
          >
            {navOpen ? <X className="size-4" /> : <Menu className="size-4" />}
          </button>
        </div>

        {/* Navigation Links */}
        <nav
          className={cn("lc-sidebar__nav", navOpen ? "flex" : "hidden lg:flex")}
          aria-label="Primary Navigation"
        >
          {NAV.filter((item) => hasPermission(user?.role, item.permission)).map(
            ({ to, label, code, Icon }) => {
              const active = to === "/" ? pathname === "/" : pathname.startsWith(to);
              return (
                <Link
                  key={to}
                  to={to}
                  className={cn("lc-nav-link", active && "lc-nav-link--active")}
                >
                  <Icon className={cn("lc-nav-link__icon")} aria-hidden />
                  <span className="lc-nav-link__label">{label}</span>
                  <span className="lc-nav-link__code">{code}</span>
                </Link>
              );
            },
          )}
        </nav>

        {/* Footer: Run Context + User Profile */}
        <div className={cn("lc-sidebar__footer", navOpen ? "block" : "hidden lg:block")}>
          <p className="lc-sidebar__context-label">Active Run Context</p>
          <p className="lc-sidebar__run-id">{runId ?? "none"}</p>

          <div className="lc-sidebar__user">
            <p className="lc-sidebar__email">{user?.email ?? user?.name ?? "Operator"}</p>
            <span className="lc-sidebar__role-badge">
              <ShieldCheck className="size-3" aria-hidden />
              ROLE: {(user?.role || "viewer").toUpperCase()}
            </span>
            <button type="button" onClick={() => logout()} className="lc-sidebar__signout">
              <LogOut className="size-3.5" aria-hidden />
              Sign out
            </button>
          </div>
        </div>
      </aside>

      {/* ═══════════════════════════════════════════════════
          MAIN CONTENT WORKSPACE
          ═══════════════════════════════════════════════════ */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top Bar */}
        <header className="lc-topbar">
          <div className="min-w-0">
            <h1 className="lc-topbar__title">{title}</h1>
            {description ? <p className="lc-topbar__subtitle">{description}</p> : null}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => openProductGuide()}
              className="lc-btn lc-btn--secondary text-xs py-1 px-2.5"
              title="Product Guide & Overview"
            >
              <Sparkles className="size-3.5 text-[var(--ledger-primary)]" />
              <span>Guide</span>
            </button>
            <span className="lc-status-badge">
              <span className="lc-status-badge__dot" aria-hidden />
              Control Tower Online
            </span>
          </div>
        </header>

        {/* Page Content */}
        <main className="lc-main">{children}</main>

        {/* Footer */}
        <footer className="lc-footer">
          <p className="lc-footer__text">
            Ledger Control Enterprise Platform · Verified Real-Time Ledger Reconciliation
          </p>
        </footer>
      </div>

      {/* Progressive Onboarding Guide Overlay */}
      <ProgressiveOnboarding />
    </div>
  );
}
