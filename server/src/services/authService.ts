import { prisma } from "../config/database.js";
import { AppError } from "../middleware/errorHandler.js";
import {
  generateAccessToken,
  generateRefreshToken,
  hashPassword,
  hashToken,
  verifyPassword,
  verifyRefreshToken,
} from "../utils/security.js";

export class AuthService {
  static async register(data: {
    email: string;
    password: string;
    fullName: string;
    organizationName?: string;
  }) {
    const normalizedEmail = data.email.trim().toLowerCase();

    const existing = await prisma.user.findUnique({
      where: { email: normalizedEmail },
    });

    if (existing) {
      throw new AppError("A user with this email address already exists.", 400);
    }

    const passwordHash = await hashPassword(data.password);
    const orgName = data.organizationName?.trim() || "Acme Financial Corp";
    const slug = orgName.toLowerCase().replace(/[^a-z0-9]+/g, "-") + "-" + Math.floor(Math.random() * 1000);

    const user = await prisma.user.create({
      data: {
        email: normalizedEmail,
        passwordHash,
        fullName: data.fullName.trim(),
        memberships: {
          create: {
            role: "ADMIN",
            organization: {
              create: {
                name: orgName,
                slug,
              },
            },
          },
        },
      },
      include: {
        memberships: {
          include: { organization: true },
        },
      },
    });

    const orgId = user.memberships[0]?.organizationId;
    const accessToken = generateAccessToken({ userId: user.id, email: user.email });
    const rawRefreshToken = generateRefreshToken({ userId: user.id });
    const tokenHash = hashToken(rawRefreshToken);

    const expiresAt = new Date();
    expiresAt.setDate(expiresAt.getDate() + 30);

    await prisma.refreshToken.create({
      data: {
        tokenHash,
        userId: user.id,
        expiresAt,
      },
    });

    if (orgId) {
      await prisma.auditLog.create({
        data: {
          organizationId: orgId,
          actorId: user.id,
          action: "user.registered",
          entityType: "User",
          entityId: user.id,
          details: JSON.stringify({ email: normalizedEmail, role: "admin" }),
        },
      });
    }

    return {
      access_token: accessToken,
      token: accessToken,
      refresh_token: rawRefreshToken,
      token_type: "bearer",
      expires_in: 900,
      user: {
        id: user.id,
        email: user.email,
        full_name: user.fullName,
        role: "admin",
        is_active: user.isActive,
        created_at: user.createdAt,
      },
    };
  }

  static async login(data: { email: string; password: string }) {
    const normalizedEmail = data.email.trim().toLowerCase();

    const user = await prisma.user.findUnique({
      where: { email: normalizedEmail },
      include: {
        memberships: {
          include: { organization: true },
        },
      },
    });

    if (!user) {
      throw new AppError("Invalid email or password.", 401);
    }

    const isValid = await verifyPassword(data.password, user.passwordHash);
    if (!isValid) {
      throw new AppError("Invalid email or password.", 401);
    }

    if (!user.isActive) {
      throw new AppError("User account is deactivated.", 403);
    }

    const role = user.memberships[0]?.role?.toLowerCase() || "viewer";
    const accessToken = generateAccessToken({ userId: user.id, email: user.email, role });
    const rawRefreshToken = generateRefreshToken({ userId: user.id });
    const tokenHash = hashToken(rawRefreshToken);

    const expiresAt = new Date();
    expiresAt.setDate(expiresAt.getDate() + 30);

    await prisma.refreshToken.create({
      data: {
        tokenHash,
        userId: user.id,
        expiresAt,
      },
    });

    const orgId = user.memberships[0]?.organizationId;
    if (orgId) {
      await prisma.auditLog.create({
        data: {
          organizationId: orgId,
          actorId: user.id,
          action: "auth.login",
          entityType: "User",
          entityId: user.id,
          details: JSON.stringify({ email: normalizedEmail, role }),
        },
      });
    }

    return {
      access_token: accessToken,
      token: accessToken,
      refresh_token: rawRefreshToken,
      token_type: "bearer",
      expires_in: 900,
      user: {
        id: user.id,
        email: user.email,
        full_name: user.fullName,
        role,
        is_active: user.isActive,
        created_at: user.createdAt,
      },
    };
  }

  static async refresh(rawRefreshToken: string) {
    try {
      const decoded = verifyRefreshToken(rawRefreshToken);
      const tokenHash = hashToken(rawRefreshToken);

      const record = await prisma.refreshToken.findUnique({
        where: { tokenHash },
        include: { user: { include: { memberships: true } } },
      });

      if (!record || record.revoked || record.expiresAt < new Date()) {
        throw new AppError("Invalid or expired refresh token.", 401);
      }

      // Revoke old token (Rotation)
      await prisma.refreshToken.update({
        where: { id: record.id },
        data: { revoked: true },
      });

      const role = record.user.memberships[0]?.role?.toLowerCase() || "viewer";
      const newAccessToken = generateAccessToken({ userId: record.userId, email: record.user.email, role });
      const newRawRefreshToken = generateRefreshToken({ userId: record.userId });
      const newTokenHash = hashToken(newRawRefreshToken);

      const expiresAt = new Date();
      expiresAt.setDate(expiresAt.getDate() + 30);

      await prisma.refreshToken.create({
        data: {
          tokenHash: newTokenHash,
          userId: record.userId,
          expiresAt,
        },
      });

      return {
        access_token: newAccessToken,
        token: newAccessToken,
        refresh_token: newRawRefreshToken,
        token_type: "bearer",
        expires_in: 900,
        user: {
          id: record.user.id,
          email: record.user.email,
          full_name: record.user.fullName,
          role,
          is_active: record.user.isActive,
          created_at: record.user.createdAt,
        },
      };
    } catch {
      throw new AppError("Invalid or expired refresh token.", 401);
    }
  }

  static async logout(rawRefreshToken?: string) {
    if (rawRefreshToken) {
      const tokenHash = hashToken(rawRefreshToken);
      await prisma.refreshToken.updateMany({
        where: { tokenHash },
        data: { revoked: true },
      });
    }
    return { status: "success", message: "Session successfully revoked." };
  }

  static async getMe(userId: string) {
    const user = await prisma.user.findUnique({
      where: { id: userId },
      include: {
        memberships: {
          include: { organization: true },
        },
      },
    });

    if (!user) throw new AppError("User not found.", 404);

    return {
      id: user.id,
      email: user.email,
      full_name: user.fullName,
      is_active: user.isActive,
      memberships: user.memberships.map((m) => ({
        id: m.id,
        role: m.role,
        organization: {
          id: m.organization.id,
          name: m.organization.name,
          slug: m.organization.slug,
        },
      })),
      created_at: user.createdAt,
    };
  }
}
