import type { LucideIcon } from "lucide-react";
import type { Permission } from "@/components/Can";

export type RoleType = "admin" | "editor" | "viewer" | "manager" | "analyst";

export type GuideStatus = "hydrating" | "ready_to_display" | "dismissed" | "completed";

export interface RoleRule {
  id: string;
  category: "reconciliation" | "exceptions" | "forecast" | "ai" | "audit" | "governance";
  ruleCode: string;
  title: string;
  description: string;
  isAllowed: boolean;
  permissionKey: Permission;
  enforcementLevel: "enforced" | "restricted" | "audited";
}

export interface GuideStep {
  id: string;
  route: string;
  title: string;
  badge: string;
  Icon: LucideIcon;
  description: string;
  bulletPoints: string[];
  roleHighlight?: string;
  applicableRules?: RoleRule[];
  roleNote?: (role?: string) => string;
}

export interface RoleGuideConfig {
  role: RoleType;
  displayName: string;
  tagline: string;
  description: string;
  badgeColor: string;
  rules: RoleRule[];
  steps: GuideStep[];
}

export interface SessionGuideState {
  sessionId: string;
  userId: string;
  role: string;
  step: number;
  status: GuideStatus;
  completedAt?: number;
  dismissedAt?: number;
  updatedAt: number;
}
