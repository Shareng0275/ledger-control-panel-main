import type { Request, Response } from "express";
import { OAuthService } from "../services/oauthService.js";
import { config } from "../config/index.js";

export class OAuthController {
  /**
   * Initiate Google OAuth redirect
   */
  static googleRedirect(_req: Request, res: Response): void {
    try {
      const url = OAuthService.getGoogleAuthUrl();
      res.redirect(url);
    } catch (err: any) {
      res.redirect(`${config.FRONTEND_URL}/login?error=${encodeURIComponent(err.message)}`);
    }
  }

  /**
   * Handle Google OAuth Callback
   */
  static async googleCallback(req: Request, res: Response): Promise<void> {
    const code = req.query.code as string | undefined;
    if (!code) {
      res.redirect(`${config.FRONTEND_URL}/login?error=Authorization code missing from Google callback.`);
      return;
    }

    try {
      const result = await OAuthService.handleGoogleCallback(code);
      const userParam = encodeURIComponent(JSON.stringify(result.user));
      res.redirect(
        `${config.FRONTEND_URL}/auth/callback?access_token=${result.accessToken}&refresh_token=${result.refreshToken}&user=${userParam}`,
      );
    } catch (err: any) {
      res.redirect(`${config.FRONTEND_URL}/login?error=${encodeURIComponent(err.message || "Google authentication failed.")}`);
    }
  }

  /**
   * Initiate GitHub OAuth redirect
   */
  static githubRedirect(_req: Request, res: Response): void {
    try {
      const url = OAuthService.getGithubAuthUrl();
      res.redirect(url);
    } catch (err: any) {
      res.redirect(`${config.FRONTEND_URL}/login?error=${encodeURIComponent(err.message)}`);
    }
  }

  /**
   * Handle GitHub OAuth Callback
   */
  static async githubCallback(req: Request, res: Response): Promise<void> {
    const code = req.query.code as string | undefined;
    if (!code) {
      res.redirect(`${config.FRONTEND_URL}/login?error=Authorization code missing from GitHub callback.`);
      return;
    }

    try {
      const result = await OAuthService.handleGithubCallback(code);
      const userParam = encodeURIComponent(JSON.stringify(result.user));
      res.redirect(
        `${config.FRONTEND_URL}/auth/callback?access_token=${result.accessToken}&refresh_token=${result.refreshToken}&user=${userParam}`,
      );
    } catch (err: any) {
      res.redirect(`${config.FRONTEND_URL}/login?error=${encodeURIComponent(err.message || "GitHub authentication failed.")}`);
    }
  }
}
