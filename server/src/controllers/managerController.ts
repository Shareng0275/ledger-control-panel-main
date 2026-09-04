import type { Response } from "express";
import { ManagerService } from "../services/managerService.js";
import type { AuthenticatedRequest } from "../types/index.js";

export class ManagerController {
  static async getTeam(req: AuthenticatedRequest, res: Response): Promise<void> {
    const result = await ManagerService.listTeamMembers(req.organizationId!);
    res.status(200).json({ members: result });
  }

  static async getApprovalQueue(req: AuthenticatedRequest, res: Response): Promise<void> {
    const result = await ManagerService.getApprovalQueue(req.organizationId!);
    res.status(200).json(result);
  }

  static async approve(req: AuthenticatedRequest, res: Response): Promise<void> {
    const { notes } = req.body || {};
    const result = await ManagerService.approveWorkflow({
      id: String(req.params.id),
      organizationId: req.organizationId!,
      managerId: req.user!.id,
      notes,
    });
    res.status(200).json(result);
  }

  static async reject(req: AuthenticatedRequest, res: Response): Promise<void> {
    const { reason } = req.body || {};
    const result = await ManagerService.rejectWorkflow({
      id: String(req.params.id),
      organizationId: req.organizationId!,
      managerId: req.user!.id,
      reason,
    });
    res.status(200).json(result);
  }

  static async assign(req: AuthenticatedRequest, res: Response): Promise<void> {
    const { assignee_id, task_type, target_id, instructions } = req.body || {};
    const result = await ManagerService.assignTask({
      organizationId: req.organizationId!,
      managerId: req.user!.id,
      assigneeId: assignee_id,
      taskType: task_type || "ReviewTask",
      targetId: target_id || "general",
      instructions,
    });
    res.status(200).json(result);
  }

  static async delegate(req: AuthenticatedRequest, res: Response): Promise<void> {
    const { delegate_id, target_id, reason } = req.body || {};
    const result = await ManagerService.delegateTask({
      organizationId: req.organizationId!,
      managerId: req.user!.id,
      delegateId: delegate_id,
      targetId: target_id || "general",
      reason,
    });
    res.status(200).json(result);
  }
}
