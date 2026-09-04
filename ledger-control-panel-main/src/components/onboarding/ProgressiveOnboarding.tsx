import React, { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "@tanstack/react-router";
import {
  Sparkles,
  ArrowRight,
  ArrowLeft,
  X,
  Check,
  Scale,
  AlertTriangle,
  TrendingUp,
  MessageSquareText,
  ClipboardList,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Sliders,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { useAuth } from "@/context/auth";
import { useReducedMotion } from "@/hooks/useReducedMotion";
import type { Role } from "@/types";
import {
  ROLE_CONFIGS,
  ROLE_RULES_CATALOG,
  normalizeRole,
} from "./guideContent";
import { guideStorage } from "./guideStorage";
import type { GuideStatus, RoleRule, RoleType } from "./guideTypes";

export function ProgressiveOnboarding() {
  const { user, isAuthenticated, restoring, sessionId, switchRole } = useAuth();
  const navigate = useNavigate();
  const prefersReducedMotion = useReducedMotion();

  // Normalized active role
  const activeRole: RoleType = useMemo(() => normalizeRole(user?.role), [user?.role]);
  const roleConfig = useMemo(() => ROLE_CONFIGS[activeRole] || ROLE_CONFIGS.viewer, [activeRole]);
  const activeSteps = roleConfig.steps;

  // Active user identifier and persistent session ID
  const userId = user?.id || user?.email || "authenticated_operator";
  const activeSessionId = sessionId || guideStorage.getOrCreateSessionId();

  // Tri-State Hydration & Visibility State
  const [guideStatus, setGuideStatus] = useState<GuideStatus>("hydrating");
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [mounted, setMounted] = useState(false);
  const [roleChangeNotice, setRoleChangeNotice] = useState<string | null>(null);
  const [showRulesMatrix, setShowRulesMatrix] = useState(false);

  // Track previous role to detect mid-session role switches
  const prevRoleRef = useRef<RoleType>(activeRole);

  // Mount detection for React Portals
  useEffect(() => {
    setMounted(true);
  }, []);

  // 1. Initial State Hydration per Session
  useEffect(() => {
    if (restoring) return; // Wait until authentication restores
    if (!isAuthenticated || !user) {
      setGuideStatus("dismissed");
      return;
    }

    const savedState = guideStorage.getSessionState(userId, activeSessionId);
    if (!savedState) {
      // Fresh login detected for this session — trigger automatically
      setCurrentStepIndex(0);
      setGuideStatus("ready_to_display");
      guideStorage.setSessionState(userId, {
        sessionId: activeSessionId,
        userId,
        role: activeRole,
        step: 0,
        status: "ready_to_display",
        updatedAt: Date.now(),
      });
    } else if (savedState.status === "ready_to_display") {
      const stepIdx = Math.min(savedState.step || 0, Math.max(0, activeSteps.length - 1));
      setCurrentStepIndex(stepIdx);
      setGuideStatus("ready_to_display");
    } else {
      setGuideStatus(savedState.status);
    }
  }, [restoring, isAuthenticated, user, userId, activeSessionId, activeRole, activeSteps.length]);

  // 2. React to explicit login events across the app
  useEffect(() => {
    function handleFreshLogin(e: Event) {
      const detail = (e as CustomEvent).detail;
      const newSessId = detail?.sessionId || guideStorage.getOrCreateSessionId();
      setCurrentStepIndex(0);
      setGuideStatus("ready_to_display");
      guideStorage.setSessionState(userId, {
        sessionId: newSessId,
        userId,
        role: normalizeRole(detail?.user?.role || activeRole),
        step: 0,
        status: "ready_to_display",
        updatedAt: Date.now(),
      });
    }

    window.addEventListener("lc-auth-login", handleFreshLogin);
    return () => window.removeEventListener("lc-auth-login", handleFreshLogin);
  }, [userId, activeRole]);

  // 3. Detect and handle mid-session role switching
  useEffect(() => {
    if (prevRoleRef.current !== activeRole) {
      const oldRole = prevRoleRef.current.toUpperCase();
      const newRole = activeRole.toUpperCase();
      prevRoleRef.current = activeRole;

      setRoleChangeNotice(`Role changed from ${oldRole} to ${newRole}. Guide path updated.`);
      
      // Ensure step index is valid within new role's step collection
      setCurrentStepIndex((prevIdx) => {
        const maxIdx = Math.max(0, ROLE_CONFIGS[activeRole].steps.length - 1);
        const clamped = Math.min(prevIdx, maxIdx);
        // Persist the updated role and step
        guideStorage.setSessionState(userId, {
          sessionId: activeSessionId,
          userId,
          role: activeRole,
          step: clamped,
          status: guideStatus,
          updatedAt: Date.now(),
        });
        return clamped;
      });

      // Clear notice banner after 6 seconds
      const timer = setTimeout(() => {
        setRoleChangeNotice(null);
      }, 6000);
      return () => clearTimeout(timer);
    }
  }, [activeRole, userId, activeSessionId, guideStatus]);

  // 4. Multi-tab synchronization
  useEffect(() => {
    const unsub = guideStorage.onSync((state) => {
      if (state.userId === userId && state.sessionId === activeSessionId) {
        setGuideStatus(state.status);
        if (typeof state.step === "number") {
          setCurrentStepIndex(state.step);
        }
      }
    });
    return unsub;
  }, [userId, activeSessionId]);

  // 5. Global manual re-trigger event listener (via Topbar Guide button)
  useEffect(() => {
    function handleManualOpen() {
      setCurrentStepIndex(0);
      setGuideStatus("ready_to_display");
      guideStorage.setSessionState(userId, {
        sessionId: activeSessionId,
        userId,
        role: activeRole,
        step: 0,
        status: "ready_to_display",
        updatedAt: Date.now(),
      });
      void navigate({ to: "/" });
    }

    window.addEventListener("open-product-guide", handleManualOpen);
    return () => window.removeEventListener("open-product-guide", handleManualOpen);
  }, [navigate, userId, activeSessionId, activeRole]);

  // Progress Handlers
  const handleFinish = useCallback(() => {
    setGuideStatus("completed");
    guideStorage.completeSession(userId, activeSessionId, activeRole, currentStepIndex);
  }, [userId, activeSessionId, activeRole, currentStepIndex]);

  const handleSkip = useCallback(() => {
    setGuideStatus("dismissed");
    guideStorage.dismissSession(userId, activeSessionId, activeRole, currentStepIndex);
  }, [userId, activeSessionId, activeRole, currentStepIndex]);

  const handleNext = useCallback(() => {
    if (currentStepIndex < activeSteps.length - 1) {
      const nextIndex = currentStepIndex + 1;
      setCurrentStepIndex(nextIndex);
      guideStorage.setSessionState(userId, {
        sessionId: activeSessionId,
        userId,
        role: activeRole,
        step: nextIndex,
        status: "ready_to_display",
        updatedAt: Date.now(),
      });
      const nextStep = activeSteps[nextIndex];
      if (nextStep?.route) {
        void navigate({ to: nextStep.route });
      }
    } else {
      handleFinish();
    }
  }, [currentStepIndex, activeSteps, userId, activeSessionId, activeRole, navigate, handleFinish]);

  const handleBack = useCallback(() => {
    if (currentStepIndex > 0) {
      const prevIndex = currentStepIndex - 1;
      setCurrentStepIndex(prevIndex);
      guideStorage.setSessionState(userId, {
        sessionId: activeSessionId,
        userId,
        role: activeRole,
        step: prevIndex,
        status: "ready_to_display",
        updatedAt: Date.now(),
      });
      const prevStep = activeSteps[prevIndex];
      if (prevStep?.route) {
        void navigate({ to: prevStep.route });
      }
    }
  }, [currentStepIndex, activeSteps, userId, activeSessionId, activeRole, navigate]);

  // Keyboard navigation
  useEffect(() => {
    if (guideStatus !== "ready_to_display") return;

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        handleSkip();
      } else if (e.key === "ArrowRight" || e.key === "Enter") {
        e.preventDefault();
        handleNext();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        handleBack();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [guideStatus, handleNext, handleBack, handleSkip]);

  if (!mounted || guideStatus !== "ready_to_display" || typeof document === "undefined") {
    return null;
  }

  const currentStep = activeSteps[currentStepIndex] || activeSteps[0]!;
  const isWelcome = currentStepIndex === 0;
  const isFinal = currentStepIndex === activeSteps.length - 1;
  const StepIcon = currentStep.Icon;
  const roleRules = roleConfig.rules;

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label={currentStep.title}
      className="authenticated-app onboarding-portal"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 99999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "1rem",
        fontFamily: "'Inter', sans-serif",
      }}
    >
      {/* 1. Backdrop Overlay */}
      <div
        onClick={handleSkip}
        className={`fixed inset-0 bg-black/85 backdrop-blur-sm transition-opacity duration-150 ${
          prefersReducedMotion ? "" : "animate-[lc-backdrop-fade_180ms_ease-out]"
        }`}
        aria-hidden="true"
      />

      {/* 2. High-Contrast Modal Dialog Card */}
      <div
        className={`relative w-full max-w-xl rounded-xl border border-[#383846] bg-[#141418] p-6 shadow-[0_25px_60px_rgba(0,0,0,0.95),0_0_35px_rgba(168,85,247,0.22)] transition-all duration-150 text-white ${
          prefersReducedMotion ? "" : "animate-[scaleIn_150ms_ease-out]"
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Dynamic Role Change Alert Banner */}
        {roleChangeNotice && (
          <div className="mb-4 flex items-center justify-between rounded-lg border border-purple-500/40 bg-purple-950/60 px-3.5 py-2 text-xs font-medium text-purple-200 shadow-md">
            <div className="flex items-center gap-2">
              <RefreshCw className="size-3.5 text-purple-400 animate-spin" />
              <span>{roleChangeNotice}</span>
            </div>
            <button
              type="button"
              onClick={() => setRoleChangeNotice(null)}
              className="text-purple-300 hover:text-white"
            >
              <X className="size-3.5" />
            </button>
          </div>
        )}

        {/* Header Strip with Role Indicator & Role Switcher */}
        <div className="flex items-center justify-between border-b border-[#2C2C38] pb-4">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-lg bg-purple-950/60 border border-purple-500/30 text-purple-300 shadow-md">
              <StepIcon className="size-5 text-purple-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-purple-400">
                  {currentStep.badge}
                </span>
                <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase border ${roleConfig.badgeColor}`}>
                  <ShieldCheck className="size-2.5" />
                  {roleConfig.displayName}
                </span>
              </div>
              <h2 className="text-base font-bold text-white tracking-tight">{currentStep.title}</h2>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Live Role Switcher for RBAC Testing */}
            <div className="flex items-center gap-1.5 rounded-lg border border-[#383846] bg-[#1E1E26] px-2 py-1">
              <Sliders className="size-3 text-slate-400" />
              <select
                aria-label="Simulate user role"
                value={activeRole}
                onChange={(e) => switchRole(e.target.value as Role)}
                className="bg-transparent font-mono text-[11px] font-semibold text-purple-300 outline-none cursor-pointer"
              >
                <option value="admin" className="bg-[#141418] text-white">Administrator</option>
                <option value="editor" className="bg-[#141418] text-white">Operational Editor</option>
                <option value="viewer" className="bg-[#141418] text-white">Read-Only Viewer</option>
              </select>
            </div>

            <button
              type="button"
              onClick={handleSkip}
              aria-label="Close guide"
              className="rounded-lg border border-[#383846] p-1.5 text-slate-400 transition-colors hover:bg-white/10 hover:text-white"
            >
              <X className="size-4" />
            </button>
          </div>
        </div>

        {/* Body Content */}
        <div className="py-4 space-y-4 max-h-[60vh] overflow-y-auto pr-1">
          <p className="text-sm text-slate-300 leading-relaxed font-normal">
            {currentStep.description}
          </p>

          {/* Key Bullet Highlights */}
          <div className="rounded-lg border border-[#2E2E3A] bg-[#1A1A22] p-4">
            <ul className="space-y-2.5">
              {currentStep.bulletPoints.map((pt, i) => (
                <li key={i} className="flex items-start gap-2.5 text-xs text-slate-100">
                  <span className="mt-1.5 size-1.5 rounded-full bg-purple-400 shrink-0 shadow-[0_0_6px_#C084FC]" />
                  <span className="leading-snug font-medium">{pt}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Role Highlight Callout */}
          {currentStep.roleHighlight && (
            <div className="flex items-start gap-2.5 rounded-lg border border-purple-500/30 bg-purple-950/35 p-3 text-xs text-purple-200">
              <ShieldCheck className="size-4 text-purple-400 shrink-0 mt-0.5" />
              <span className="leading-tight font-medium">{currentStep.roleHighlight}</span>
            </div>
          )}

          {/* Collapsible Role Rules & Permissions Inspector */}
          <div className="rounded-lg border border-[#2E2E3A] bg-[#16161D] overflow-hidden">
            <button
              type="button"
              onClick={() => setShowRulesMatrix((v) => !v)}
              className="flex w-full items-center justify-between px-3.5 py-2.5 text-left text-xs font-semibold text-slate-200 hover:bg-white/5 transition-colors"
            >
              <span className="flex items-center gap-2">
                <ShieldCheck className="size-3.5 text-purple-400" />
                <span>Applicable Role Rules & Permissions ({roleConfig.displayName})</span>
              </span>
              {showRulesMatrix ? (
                <ChevronUp className="size-3.5 text-slate-400" />
              ) : (
                <ChevronDown className="size-3.5 text-slate-400" />
              )}
            </button>

            {showRulesMatrix && (
              <div className="border-t border-[#2E2E3A] p-3 space-y-2.5 bg-[#121217]">
                <p className="text-[11px] text-slate-400">
                  Governed rules active for this role. Disallowed rules are restricted at both API and UI layers:
                </p>
                <div className="space-y-2">
                  {roleRules.map((rule) => (
                    <div
                      key={rule.id}
                      className="flex items-start justify-between gap-3 rounded border border-[#2C2C38] bg-[#191922] p-2.5 text-xs"
                    >
                      <div className="space-y-0.5 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-[10px] font-bold text-slate-400">
                            {rule.ruleCode}
                          </span>
                          <span className="font-semibold text-white truncate">{rule.title}</span>
                        </div>
                        <p className="text-[11px] text-slate-400 leading-tight">{rule.description}</p>
                        <span className="font-mono text-[9px] text-purple-300">
                          Key: {rule.permissionKey}
                        </span>
                      </div>

                      <div className="shrink-0 pt-0.5">
                        {rule.isAllowed ? (
                          <span className="inline-flex items-center gap-1 rounded bg-emerald-950/70 border border-emerald-500/40 px-2 py-0.5 text-[10px] font-bold text-emerald-300">
                            <CheckCircle2 className="size-3 text-emerald-400" />
                            Permitted
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded bg-rose-950/70 border border-rose-500/40 px-2 py-0.5 text-[10px] font-bold text-rose-300">
                            <XCircle className="size-3 text-rose-400" />
                            Restricted
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer Navigation Strip */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[#2C2C38] pt-4">
          {/* Progress Step Indicators */}
          <div className="flex items-center gap-2">
            {activeSteps.map((_, i) => (
              <button
                key={i}
                type="button"
                onClick={() => {
                  setCurrentStepIndex(i);
                  guideStorage.setSessionState(userId, {
                    sessionId: activeSessionId,
                    userId,
                    role: activeRole,
                    step: i,
                    status: "ready_to_display",
                    updatedAt: Date.now(),
                  });
                  const step = activeSteps[i];
                  if (step?.route) void navigate({ to: step.route });
                }}
                title={`Go to step ${i + 1}`}
                className={`h-2 rounded-full transition-all duration-200 cursor-pointer ${
                  i === currentStepIndex
                    ? "w-7 bg-purple-500 shadow-[0_0_10px_rgba(168,85,247,0.8)]"
                    : i < currentStepIndex
                      ? "w-2.5 bg-emerald-400"
                      : "w-2.5 bg-slate-700 hover:bg-slate-600"
                }`}
              />
            ))}
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={handleSkip}
              className="px-3 py-1.5 text-xs font-semibold text-slate-400 hover:text-white transition-colors cursor-pointer rounded-md hover:bg-white/5"
            >
              Dismiss for this session
            </button>

            {!isWelcome && (
              <button
                type="button"
                onClick={handleBack}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-200 bg-[#22222C] hover:bg-[#2C2C38] border border-[#383846] rounded-md transition-colors cursor-pointer"
              >
                <ArrowLeft className="size-3.5" />
                <span>Back</span>
              </button>
            )}

            <button
              type="button"
              onClick={handleNext}
              className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-semibold text-white bg-purple-600 hover:bg-purple-500 rounded-md transition-all shadow-[0_2px_12px_rgba(168,85,247,0.45)] cursor-pointer"
            >
              {isWelcome ? (
                <>
                  <span>Getting Started</span>
                  <ArrowRight className="size-3.5" />
                </>
              ) : isFinal ? (
                <>
                  <Check className="size-3.5" />
                  <span>Complete Guide</span>
                </>
              ) : (
                <>
                  <span>Continue</span>
                  <ArrowRight className="size-3.5" />
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}

/**
 * Global helper to trigger the product guide from anywhere in the app
 */
export function openProductGuide() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("open-product-guide"));
  }
}
