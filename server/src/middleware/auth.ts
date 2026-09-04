import type { NextFunction, Response } from "express";
import { prisma } from "../config/database.js";
import type { AuthenticatedRequest, Role } from "../types/index.js";
import { checkPermission, type Permission } from "../utils/rbacPermissions.js";
import { verifyAccessToken } from "../utils/security.js";

export async function requireAuth(
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction,
): Promise<void> {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    res.status(401).json({
      error: "Unauthorized",
      detail: "Authentication credentials were not provided.",
      status_code: 401,
    });
    return;
  }

  const token = authHeader.split(" ")[1];
  try {
    const decoded = verifyAccessToken(token);
    const user = await prisma.user.findUnique({
      where: { id: decoded.userId },
      select: { id: true, email: true, fullName: true, isActive: true },
    });

    if (!user || !user.isActive) {
      res.status(401).json({
        error: "Unauthorized",
        detail: "User account is invalid or deactivated.",
        status_code: 401,
      });
      return;
    }

    req.user = {
      id: user.id,
      email: user.email,
      fullName: user.fullName,
    };
    next();
  } catch (err: any) {
    res.status(401).json({
      error: "Unauthorized",
      detail: err.name === "TokenExpiredError" ? "Token has expired." : "Invalid authentication token.",
      status_code: 401,
    });
  }
}

export async function requireOrg(
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction,
): Promise<void> {
  if (!req.user) {
    res.status(401).json({ error: "Unauthorized", detail: "User unauthenticated.", status_code: 401 });
    return;
  }

  const xOrgId = req.headers["x-organization-id"] as string | undefined;

  if (xOrgId) {
    const membership = await prisma.membership.findFirst({
      where: {
        organizationId: xOrgId,
        userId: req.user.id,
      },
    });

    if (!membership) {
      res.status(403).json({
        error: "Forbidden",
        detail: "Access denied: You do not have membership in this organization.",
        status_code: 403,
      });
      return;
    }

    req.organizationId = xOrgId;
    req.user.organizationId = xOrgId;
    req.user.role = membership.role.toLowerCase() as Role;
    next();
    return;
  }

  // Fallback to user's primary organization membership
  const primaryMembership = await prisma.membership.findFirst({
    where: { userId: req.user.id },
    select: { organizationId: true, role: true },
  });

  if (!primaryMembership) {
    res.status(400).json({
      error: "BadRequest",
      detail: "No active organization context found for this user.",
      status_code: 400,
    });
    return;
  }

  req.organizationId = primaryMembership.organizationId;
  req.user.organizationId = primaryMembership.organizationId;
  req.user.role = primaryMembership.role.toLowerCase() as Role;
  next();
}

export function requireRole(allowedRoles: Role[]) {
  return (req: AuthenticatedRequest, res: Response, next: NextFunction): void => {
    if (!req.user || !req.user.role) {
      res.status(403).json({ error: "Forbidden", detail: "Insufficient permissions.", status_code: 403 });
      return;
    }

    const userRole = req.user.role.toLowerCase() as Role;
    const allowed = allowedRoles.map((r) => r.toLowerCase());

    if (!allowed.includes(userRole)) {
      res.status(403).json({
        error: "Forbidden",
        detail: `Action requires one of the following roles: [${allowedRoles.join(", ")}].`,
        status_code: 403,
      });
      return;
    }

    next();
  };
}

export function requirePermission(permission: Permission) {
  return (req: AuthenticatedRequest, res: Response, next: NextFunction): void => {
    if (!req.user || !req.user.role) {
      res.status(403).json({ error: "Forbidden", detail: "Insufficient permissions.", status_code: 403 });
      return;
    }

    const userRole = req.user.role.toLowerCase() as Role;

    if (!checkPermission(userRole, permission)) {
      res.status(403).json({
        error: "Forbidden",
        detail: `Operation requires '${permission}' permission which is not granted to role '${userRole}'.`,
        status_code: 403,
      });
      return;
    }

    next();
  };
}
