import type { Response } from "express";
import { AdminService } from "../services/adminService.js";
import type { AuthenticatedRequest } from "../types/index.js";

export class AdminController {
  static async listUsers(req: AuthenticatedRequest, res: Response): Promise<void> {
    const result = await AdminService.listUsers(req.organizationId!);
    res.status(200).json({ users: result });
  }

  static async createUser(req: AuthenticatedRequest, res: Response): Promise<void> {
    const { email, full_name, role, password } = req.body || {};
    const result = await AdminService.createUser({
      organizationId: req.organizationId!,
      adminId: req.user!.id,
      email,
      fullName: full_name,
      role,
      password,
    });
    res.status(201).json(result);
  }

  static async updateUserRole(req: AuthenticatedRequest, res: Response): Promise<void> {
    const { role } = req.body || {};
    const result = await AdminService.updateUserRole({
      organizationId: req.organizationId!,
      adminId: req.user!.id,
      targetUserId: String(req.params.id),
      newRole: role,
    });
    res.status(200).json(result);
  }

  static async setUserStatus(req: AuthenticatedRequest, res: Response): Promise<void> {
    const { is_active, confirm } = req.body || {};
    const result = await AdminService.setUserStatus({
      organizationId: req.organizationId!,
      adminId: req.user!.id,
      targetUserId: String(req.params.id),
      isActive: Boolean(is_active),
      confirm: Boolean(confirm),
    });
    res.status(200).json(result);
  }

  static async getPermissions(_req: AuthenticatedRequest, res: Response): Promise<void> {
    const result = AdminService.getPermissionMatrix();
    res.status(200).json(result);
  }

  static async getSecurityMetrics(req: AuthenticatedRequest, res: Response): Promise<void> {
    const result = await AdminService.getSecurityMetrics(req.organizationId!);
    res.status(200).json(result);
  }

  static async getSettings(req: AuthenticatedRequest, res: Response): Promise<void> {
    const result = await AdminService.getSettings(req.organizationId!);
    res.status(200).json(result);
  }

  static async updateSettings(req: AuthenticatedRequest, res: Response): Promise<void> {
    const { name } = req.body || {};
    const result = await AdminService.updateSettings({
      organizationId: req.organizationId!,
      adminId: req.user!.id,
      name,
    });
    res.status(200).json(result);
  }
}
