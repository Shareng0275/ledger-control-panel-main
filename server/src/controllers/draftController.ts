import type { Response } from "express";
import { DraftService } from "../services/draftService.js";
import type { AuthenticatedRequest } from "../types/index.js";

export class DraftController {
  static async create(req: AuthenticatedRequest, res: Response): Promise<void> {
    const { title, description, amount, currency, category } = req.body;
    const result = await DraftService.createDraft({
      organizationId: req.organizationId!,
      authorId: req.user!.id,
      title,
      description,
      amount: Number(amount) || 0,
      currency,
      category,
    });
    res.status(201).json(result);
  }

  static async list(req: AuthenticatedRequest, res: Response): Promise<void> {
    const { status, author_id } = req.query;
    const result = await DraftService.listDrafts({
      organizationId: req.organizationId!,
      status: status ? String(status) : undefined,
      authorId: author_id ? String(author_id) : undefined,
    });
    res.status(200).json(result);
  }

  static async getById(req: AuthenticatedRequest, res: Response): Promise<void> {
    const result = await DraftService.getDraftById(String(req.params.id), req.organizationId!);
    res.status(200).json(result);
  }

  static async update(req: AuthenticatedRequest, res: Response): Promise<void> {
    const { title, description, amount, currency, category, expected_version } = req.body;
    const result = await DraftService.updateDraft({
      id: String(req.params.id),
      organizationId: req.organizationId!,
      userId: req.user!.id,
      userRole: req.user!.role || "editor",
      title,
      description,
      amount: amount !== undefined ? Number(amount) : undefined,
      currency,
      category,
      expectedVersion: expected_version !== undefined ? Number(expected_version) : undefined,
    });
    res.status(200).json(result);
  }

  static async submit(req: AuthenticatedRequest, res: Response): Promise<void> {
    const result = await DraftService.submitDraft({
      id: String(req.params.id),
      organizationId: req.organizationId!,
      userId: req.user!.id,
      userRole: req.user!.role || "editor",
    });
    res.status(200).json(result);
  }

  static async approve(req: AuthenticatedRequest, res: Response): Promise<void> {
    const { notes } = req.body || {};
    const result = await DraftService.approveDraft({
      id: String(req.params.id),
      organizationId: req.organizationId!,
      reviewerId: req.user!.id,
      notes,
    });
    res.status(200).json(result);
  }
}
