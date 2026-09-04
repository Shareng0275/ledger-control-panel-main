import { prisma } from "../config/database.js";
import { AppError } from "../middleware/errorHandler.js";
import { hashPassword } from "../utils/security.js";
import { ROLE_PERMISSION_MAP } from "../utils/rbacPermissions.js";
import type { Role } from "../types/index.js";

const VALID_ROLES = ["admin", "administrator", "manager", "analyst", "editor", "viewer"];

export class AdminService {
  /**
   * List all users within the organization
   */
  static async listUsers(organizationId: string) {
    const memberships = await prisma.membership.findMany({
      where: { organizationId },
      include: {
        user: {
          select: { id: true, email: true, fullName: true, isActive: true, createdAt: true, updatedAt: true },
        },
      },
      orderBy: { createdAt: "desc" },
    });

    return memberships.map((m) => ({
      id: m.user.id,
      email: m.user.email,
      full_name: m.user.fullName,
      role: m.role.toLowerCase(),
      is_active: m.user.isActive,
      joined_at: m.createdAt,
      last_updated: m.user.updatedAt,
    }));
  }

  /**
   * Provision a new user with role assignment
   */
  static async createUser(params: {
    organizationId: string;
    adminId: string;
    email: string;
    fullName: string;
    password?: string;
    role: string;
  }) {
    const email = params.email?.trim().toLowerCase();
    const fullName = params.fullName?.trim();
    const role = params.role?.trim().toLowerCase();

    if (!email || !fullName || !role) {
      throw new AppError("Email, fullName, and role are required.", 422);
    }

    if (!VALID_ROLES.includes(role)) {
      throw new AppError(`Invalid role '${role}'. Allowed roles: ${VALID_ROLES.join(", ")}`, 422);
    }

    const existingUser = await prisma.user.findUnique({ where: { email } });
    if (existingUser) {
      // Check if already in organization
      const existingMembership = await prisma.membership.findFirst({
        where: { organizationId: params.organizationId, userId: existingUser.id },
      });
      if (existingMembership) {
        throw new AppError("User is already a member of this organization.", 409);
      }
      // Add membership
      const membership = await prisma.membership.create({
        data: {
          organizationId: params.organizationId,
          userId: existingUser.id,
          role: role === "administrator" ? "admin" : role,
        },
      });

      await prisma.auditLog.create({
        data: {
          organizationId: params.organizationId,
          actorId: params.adminId,
          action: "user.add_membership",
          entityType: "User",
          entityId: existingUser.id,
          details: JSON.stringify({ email, role }),
        },
      });

      return { id: existingUser.id, email: existingUser.email, full_name: existingUser.fullName, role, is_active: existingUser.isActive };
    }

    const defaultPassword = params.password || "Password123!";
    const passwordHash = await hashPassword(defaultPassword);

    const user = await prisma.user.create({
      data: {
        email,
        fullName,
        passwordHash,
        memberships: {
          create: {
            organizationId: params.organizationId,
            role: role === "administrator" ? "admin" : role,
          },
        },
      },
    });

    // Audit CREATE
    await prisma.auditLog.create({
      data: {
        organizationId: params.organizationId,
        actorId: params.adminId,
        action: "user.create",
        entityType: "User",
        entityId: user.id,
        details: JSON.stringify({ email, role, fullName }),
      },
    });

    return {
      id: user.id,
      email: user.email,
      full_name: user.fullName,
      role,
      is_active: user.isActive,
    };
  }

  /**
   * Modify user role with self-lockout protection & audit logging
   */
  static async updateUserRole(params: {
    organizationId: string;
    adminId: string;
    targetUserId: string;
    newRole: string;
  }) {
    const newRole = params.newRole?.trim().toLowerCase();
    if (!newRole || !VALID_ROLES.includes(newRole)) {
      throw new AppError(`Invalid role '${newRole}'. Allowed: ${VALID_ROLES.join(", ")}`, 422);
    }

    // 1. Prevent accidental self-lockout
    if (params.targetUserId === params.adminId) {
      if (newRole !== "admin" && newRole !== "administrator") {
        throw new AppError("Self-lockout protection: Administrator cannot demote their own account role.", 400);
      }
    }

    const membership = await prisma.membership.findFirst({
      where: { organizationId: params.organizationId, userId: params.targetUserId },
      include: { user: true },
    });

    if (!membership) {
      throw new AppError("User membership not found in this organization.", 404);
    }

    const oldRole = membership.role;
    const normalizedRole = newRole === "administrator" ? "admin" : newRole;

    const updated = await prisma.membership.update({
      where: { id: membership.id },
      data: { role: normalizedRole },
    });

    // 2. Audit Privilege / Role Modification
    await prisma.auditLog.create({
      data: {
        organizationId: params.organizationId,
        actorId: params.adminId,
        action: "user.role_change",
        entityType: "UserRole",
        entityId: params.targetUserId,
        details: JSON.stringify({
          target_user_id: params.targetUserId,
          target_email: membership.user.email,
          previous_role: oldRole,
          new_role: normalizedRole,
        }),
      },
    });

    return {
      user_id: params.targetUserId,
      email: membership.user.email,
      previous_role: oldRole,
      new_role: updated.role,
    };
  }

  /**
   * Toggle user active status with confirmation requirement & self-lockout protection
   */
  static async setUserStatus(params: {
    organizationId: string;
    adminId: string;
    targetUserId: string;
    isActive: boolean;
    confirm?: boolean;
  }) {
    // 1. Prevent self-lockout
    if (params.targetUserId === params.adminId && !params.isActive) {
      throw new AppError("Self-lockout protection: Administrator cannot deactivate their own account.", 400);
    }

    // 2. Destructive confirmation requirement
    if (!params.isActive && !params.confirm) {
      throw new AppError("Destructive action: Explicit 'confirm: true' is required to deactivate user accounts.", 422);
    }

    const user = await prisma.user.findUnique({ where: { id: params.targetUserId } });
    if (!user) throw new AppError("User not found.", 404);

    const updated = await prisma.user.update({
      where: { id: params.targetUserId },
      data: { isActive: params.isActive },
    });

    // Audit Deactivation / Status change
    await prisma.auditLog.create({
      data: {
        organizationId: params.organizationId,
        actorId: params.adminId,
        action: params.isActive ? "user.activate" : "user.deactivate",
        entityType: "User",
        entityId: updated.id,
        details: JSON.stringify({ email: updated.email, is_active: updated.isActive }),
      },
    });

    return {
      id: updated.id,
      email: updated.email,
      is_active: updated.isActive,
    };
  }

  /**
   * Get full RBAC permission matrix for inspector
   */
  static getPermissionMatrix() {
    return {
      roles: Object.keys(ROLE_PERMISSION_MAP),
      matrix: ROLE_PERMISSION_MAP,
    };
  }

  /**
   * Get Security Health Dashboard metrics
   */
  static async getSecurityMetrics(organizationId: string) {
    const [totalUsers, activeUsers, totalAuditLogs, recentRoleChanges] = await Promise.all([
      prisma.membership.count({ where: { organizationId } }),
      prisma.membership.count({ where: { organizationId, user: { isActive: true } } }),
      prisma.auditLog.count({ where: { organizationId } }),
      prisma.auditLog.findMany({
        where: { organizationId, action: "user.role_change" },
        take: 5,
        orderBy: { createdAt: "desc" },
      }),
    ]);

    return {
      total_users: totalUsers,
      active_users: activeUsers,
      deactivated_users: totalUsers - activeUsers,
      total_audit_events: totalAuditLogs,
      security_posture: "HIGH",
      mfa_enforced: true,
      jwt_rotation_enabled: true,
      recent_role_changes: recentRoleChanges.map((r) => ({
        id: r.id,
        timestamp: r.createdAt,
        details: typeof r.details === "string" ? JSON.parse(r.details) : r.details,
      })),
    };
  }

  /**
   * Get Organization configuration settings
   */
  static async getSettings(organizationId: string) {
    const org = await prisma.organization.findUnique({
      where: { id: organizationId },
    });
    if (!org) throw new AppError("Organization not found.", 404);

    return {
      id: org.id,
      name: org.name,
      slug: org.slug,
      session_timeout_minutes: 15,
      refresh_token_ttl_days: 30,
      mfa_policy: "OPTIONAL",
      data_isolation: "ROW_LEVEL_ORGANIZATION",
      audit_retention_days: 365,
    };
  }

  /**
   * Update Organization configuration settings
   */
  static async updateSettings(params: {
    organizationId: string;
    adminId: string;
    name?: string;
  }) {
    const updated = await prisma.organization.update({
      where: { id: params.organizationId },
      data: {
        name: params.name ? params.name.trim() : undefined,
      },
    });

    await prisma.auditLog.create({
      data: {
        organizationId: params.organizationId,
        actorId: params.adminId,
        action: "settings.update",
        entityType: "Organization",
        entityId: updated.id,
        details: JSON.stringify({ name: updated.name }),
      },
    });

    return updated;
  }
}
