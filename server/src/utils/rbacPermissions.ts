import type { Role } from "../types/index.js";

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

export const ROLE_PERMISSION_MAP: Record<string, Permission[]> = {
  // ADMINISTRATOR / ADMIN (Full System Governance)
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

  // MANAGER (Operational Leadership & Approvals)
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

  // ANALYST (Financial Intelligence & Exception Triage)
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

  // EDITOR (Data Entry & Execution)
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

  // VIEWER (Strict Read-Only Observation)
  viewer: [
    "records.read",
    "documents.read",
    "reconciliation.read",
    "analytics.read",
  ],
};

/**
 * Centralized server-authoritative permission checker.
 * Evaluates whether a normalized role possesses the required permission.
 */
export function checkPermission(role: Role | string, requiredPermission: Permission): boolean {
  const normalizedRole = role.toLowerCase();
  if (normalizedRole === "admin" || normalizedRole === "administrator") return true;
  const userPermissions = ROLE_PERMISSION_MAP[normalizedRole] || [];
  return userPermissions.includes(requiredPermission);
}

/**
 * Returns all assigned permissions for a given role.
 */
export function getPermissionsForRole(role: Role | string): Permission[] {
  const normalizedRole = role.toLowerCase();
  return ROLE_PERMISSION_MAP[normalizedRole] || [];
}
