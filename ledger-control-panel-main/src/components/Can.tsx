import React from "react";
import { useAuth } from "@/context/auth";

export type Permission =
  | "users.read"
  | "users.write"
  | "users.manage"
  | "roles.manage"
  | "records.read"
  | "records.create"
  | "records.update"
  | "records.delete"
  | "documents.read"
  | "documents.create"
  | "documents.update"
  | "documents.delete"
  | "reconciliation.read"
  | "reconciliation.execute"
  | "reconciliation.resolve"
  | "analytics.read"
  | "analytics.export"
  | "workflow.approve"
  | "workflow.assign"
  | "audit.read"
  | "settings.manage";

export const ROLE_PERMISSIONS: Record<string, Permission[]> = {
  administrator: [
    "users.read",
    "users.write",
    "users.manage",
    "roles.manage",
    "records.read",
    "records.create",
    "records.update",
    "records.delete",
    "documents.read",
    "documents.create",
    "documents.update",
    "documents.delete",
    "reconciliation.read",
    "reconciliation.execute",
    "reconciliation.resolve",
    "analytics.read",
    "analytics.export",
    "workflow.approve",
    "workflow.assign",
    "audit.read",
    "settings.manage",
  ],
  admin: [
    "users.read",
    "users.write",
    "users.manage",
    "roles.manage",
    "records.read",
    "records.create",
    "records.update",
    "records.delete",
    "documents.read",
    "documents.create",
    "documents.update",
    "documents.delete",
    "reconciliation.read",
    "reconciliation.execute",
    "reconciliation.resolve",
    "analytics.read",
    "analytics.export",
    "workflow.approve",
    "workflow.assign",
    "audit.read",
    "settings.manage",
  ],
  manager: [
    "users.read",
    "records.read",
    "records.create",
    "records.update",
    "documents.read",
    "documents.create",
    "documents.update",
    "reconciliation.read",
    "reconciliation.execute",
    "reconciliation.resolve",
    "analytics.read",
    "analytics.export",
    "workflow.approve",
    "workflow.assign",
  ],
  analyst: [
    "records.read",
    "records.create",
    "documents.read",
    "documents.create",
    "reconciliation.read",
    "reconciliation.execute",
    "reconciliation.resolve",
    "analytics.read",
    "analytics.export",
  ],
  editor: [
    "records.read",
    "records.create",
    "records.update",
    "documents.read",
    "documents.create",
    "documents.update",
    "reconciliation.read",
    "reconciliation.execute",
    "analytics.read",
  ],
  viewer: ["records.read", "documents.read", "reconciliation.read", "analytics.read"],
};

export function hasPermission(role: string | undefined, permission: Permission): boolean {
  const normalizedRole = (role || "viewer").toLowerCase();
  if (normalizedRole === "admin" || normalizedRole === "administrator") return true;
  return ROLE_PERMISSIONS[normalizedRole]?.includes(permission) ?? false;
}

interface CanProps {
  permission: Permission;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export function Can({ permission, children, fallback = null }: CanProps) {
  const { user } = useAuth();
  const allowed = hasPermission(user?.role, permission);

  if (!allowed) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
}
