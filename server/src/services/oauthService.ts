import { config } from "../config/index.js";
import { prisma } from "../config/database.js";
import { generateAccessToken, generateRefreshToken, hashPassword, hashToken } from "../utils/security.js";
import { AppError } from "../middleware/errorHandler.js";

export class OAuthService {
  /**
   * Check if real Google OAuth credentials are configured
   */
  static isGoogleConfigured(): boolean {
    return Boolean(config.GOOGLE_CLIENT_ID && config.GOOGLE_CLIENT_SECRET);
  }

  /**
   * Check if real GitHub OAuth credentials are configured
   */
  static isGithubConfigured(): boolean {
    return Boolean(config.GITHUB_CLIENT_ID && config.GITHUB_CLIENT_SECRET);
  }

  /**
   * Generates Google OAuth 2.0 Authorization URL or Sandbox Callback
   */
  static getGoogleAuthUrl(): string {
    if (!this.isGoogleConfigured()) {
      return `${config.GOOGLE_CALLBACK_URL}?code=sandbox_google_auth_code`;
    }
    const params = new URLSearchParams({
      client_id: config.GOOGLE_CLIENT_ID,
      redirect_uri: config.GOOGLE_CALLBACK_URL,
      response_type: "code",
      scope: "openid email profile",
      access_type: "offline",
      prompt: "consent",
    });
    return `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
  }

  /**
   * Exchanges Google Auth Code for Tokens and provisions/retrieves User
   */
  static async handleGoogleCallback(code: string) {
    if (!this.isGoogleConfigured() || code.startsWith("sandbox_")) {
      // Local Sandbox / Demo Google OAuth sign-in
      return this.findOrCreateOAuthUser({
        email: "google.user@ledgercontrol.com",
        fullName: "Google Enterprise User",
        provider: "google",
      });
    }

    // 1. Exchange code for Google Access Token
    const tokenRes = await fetch("https://oauth2.googleapis.com/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        code,
        client_id: config.GOOGLE_CLIENT_ID,
        client_secret: config.GOOGLE_CLIENT_SECRET,
        redirect_uri: config.GOOGLE_CALLBACK_URL,
        grant_type: "authorization_code",
      }),
    });

    const tokenData = (await tokenRes.json()) as any;
    if (!tokenRes.ok || !tokenData.access_token) {
      throw new AppError(tokenData.error_description || "Failed to exchange Google authorization code.", 401);
    }

    // 2. Fetch Google User Profile
    const profileRes = await fetch("https://www.googleapis.com/oauth2/v3/userinfo", {
      headers: { Authorization: `Bearer ${tokenData.access_token}` },
    });
    const profile = (await profileRes.json()) as any;
    if (!profileRes.ok || !profile.email) {
      throw new AppError("Failed to fetch Google user profile.", 401);
    }

    return this.findOrCreateOAuthUser({
      email: profile.email,
      fullName: profile.name || profile.given_name || "Google User",
      provider: "google",
    });
  }

  /**
   * Generates GitHub OAuth Authorization URL or Sandbox Callback
   */
  static getGithubAuthUrl(): string {
    if (!this.isGithubConfigured()) {
      return `${config.GITHUB_CALLBACK_URL}?code=sandbox_github_auth_code`;
    }
    const params = new URLSearchParams({
      client_id: config.GITHUB_CLIENT_ID,
      redirect_uri: config.GITHUB_CALLBACK_URL,
      scope: "read:user user:email",
    });
    return `https://github.com/login/oauth/authorize?${params.toString()}`;
  }

  /**
   * Exchanges GitHub Auth Code for Tokens and provisions/retrieves User
   */
  static async handleGithubCallback(code: string) {
    if (!this.isGithubConfigured() || code.startsWith("sandbox_")) {
      // Local Sandbox / Demo GitHub OAuth sign-in
      return this.findOrCreateOAuthUser({
        email: "github.developer@ledgercontrol.com",
        fullName: "GitHub Developer",
        provider: "github",
      });
    }

    // 1. Exchange code for GitHub Access Token
    const tokenRes = await fetch("https://github.com/login/oauth/access_token", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        client_id: config.GITHUB_CLIENT_ID,
        client_secret: config.GITHUB_CLIENT_SECRET,
        code,
        redirect_uri: config.GITHUB_CALLBACK_URL,
      }),
    });

    const tokenData = (await tokenRes.json()) as any;
    if (!tokenRes.ok || !tokenData.access_token) {
      throw new AppError(tokenData.error_description || "Failed to exchange GitHub authorization code.", 401);
    }

    // 2. Fetch GitHub User Profile & Primary Email
    const [profileRes, emailsRes] = await Promise.all([
      fetch("https://api.github.com/user", {
        headers: {
          Authorization: `Bearer ${tokenData.access_token}`,
          "User-Agent": "Ledger-Control-OAuth",
        },
      }),
      fetch("https://api.github.com/user/emails", {
        headers: {
          Authorization: `Bearer ${tokenData.access_token}`,
          "User-Agent": "Ledger-Control-OAuth",
        },
      }),
    ]);

    const profile = (await profileRes.json()) as any;
    const emails = (await emailsRes.json()) as any;

    let primaryEmail = profile.email;
    if (!primaryEmail && Array.isArray(emails)) {
      const primary = emails.find((e: any) => e.primary && e.verified) || emails[0];
      primaryEmail = primary?.email;
    }

    if (!primaryEmail) {
      throw new AppError("No verified email found associated with this GitHub account.", 401);
    }

    return this.findOrCreateOAuthUser({
      email: primaryEmail,
      fullName: profile.name || profile.login || "GitHub User",
      provider: "github",
    });
  }

  /**
   * Helper: Provisions or retrieves user and issues application JWT session tokens
   */
  public static async findOrCreateOAuthUser(params: {
    email: string;
    fullName: string;
    provider: string;
  }) {
    const normalizedEmail = params.email.trim().toLowerCase();

    // Find existing user or create a new user
    let user = await prisma.user.findUnique({
      where: { email: normalizedEmail },
      include: {
        memberships: {
          include: { organization: true },
        },
      },
    });

    if (!user) {
      // Find default organization or create one
      let defaultOrg = await prisma.organization.findFirst();
      if (!defaultOrg) {
        defaultOrg = await prisma.organization.create({
          data: {
            name: "Default Organization",
            slug: "default-org",
          },
        });
      }

      // Generate secure random placeholder hash for OAuth users
      const randomPassword = `oauth_${Math.random().toString(36)}_${Date.now()}`;
      const passwordHash = await hashPassword(randomPassword);

      user = await prisma.user.create({
        data: {
          email: normalizedEmail,
          fullName: params.fullName,
          passwordHash,
          isActive: true,
          memberships: {
            create: {
              organizationId: defaultOrg.id,
              role: "ANALYST", // Default OAuth users to Analyst
            },
          },
        },
        include: {
          memberships: {
            include: { organization: true },
          },
        },
      });
    }

    if (!user.isActive) {
      throw new AppError("Your account has been deactivated. Please contact an administrator.", 403);
    }

    const role = user.memberships[0]?.role?.toLowerCase() || "analyst";
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
          action: `auth.oauth_${params.provider}`,
          entityType: "User",
          entityId: user.id,
          details: JSON.stringify({ email: normalizedEmail, provider: params.provider, role }),
        },
      });
    }

    return {
      accessToken,
      refreshToken: rawRefreshToken,
      user: {
        id: user.id,
        email: user.email,
        full_name: user.fullName,
        role,
        is_active: user.isActive,
      },
    };
  }
}
