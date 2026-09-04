import type { Request, Response } from "express";
import { z } from "zod";
import { AuthService } from "../services/authService.js";
import type { AuthenticatedRequest } from "../types/index.js";

const registerSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
  full_name: z.string().min(1).optional(),
  fullName: z.string().min(1).optional(),
  organization_name: z.string().optional(),
  organizationName: z.string().optional(),
});

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

const refreshSchema = z.object({
  refresh_token: z.string().optional(),
  refreshToken: z.string().optional(),
});

export class AuthController {
  static async register(req: Request, res: Response): Promise<void> {
    const body = registerSchema.parse(req.body);
    const result = await AuthService.register({
      email: body.email,
      password: body.password,
      fullName: body.fullName || body.full_name || "Admin Controller",
      organizationName: body.organizationName || body.organization_name,
    });
    res.status(201).json(result);
  }

  static async login(req: Request, res: Response): Promise<void> {
    const body = loginSchema.parse(req.body);
    const result = await AuthService.login({
      email: body.email,
      password: body.password,
    });
    res.status(200).json(result);
  }

  static async refresh(req: Request, res: Response): Promise<void> {
    const body = refreshSchema.parse(req.body);
    const token = body.refreshToken || body.refresh_token;
    if (!token) {
      res.status(400).json({ error: "BadRequest", detail: "Refresh token is required." });
      return;
    }
    const result = await AuthService.refresh(token);
    res.status(200).json(result);
  }

  static async logout(req: Request, res: Response): Promise<void> {
    const token = req.body?.refreshToken || req.body?.refresh_token;
    const result = await AuthService.logout(token);
    res.status(200).json(result);
  }

  static async getMe(req: AuthenticatedRequest, res: Response): Promise<void> {
    const result = await AuthService.getMe(req.user!.id);
    res.status(200).json(result);
  }
}
