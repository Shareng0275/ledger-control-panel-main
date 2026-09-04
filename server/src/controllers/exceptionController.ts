import type { Response } from "express";
import { z } from "zod";
import { ExceptionService } from "../services/exceptionService.js";
import type { AuthenticatedRequest } from "../types/index.js";

const resolveSchema = z.object({
  action: z.string().min(1),
  candidate_id: z.string().optional(),
  candidateId: z.string().optional(),
  note: z.string().optional(),
});

const bulkResolveSchema = z.object({
  exception_ids: z.array(z.string()).optional(),
  exceptionIds: z.array(z.string()).optional(),
  action: z.string().min(1),
  note: z.string().optional(),
});

export class ExceptionController {
  static async list(req: AuthenticatedRequest, res: Response): Promise<void> {
    const { page, page_size, status, priority, run_id } = req.query;

    const result = await ExceptionService.listExceptions({
      organizationId: req.organizationId!,
      page: page ? parseInt(String(page), 10) : undefined,
      pageSize: page_size ? parseInt(String(page_size), 10) : undefined,
      status: status ? String(status) : undefined,
      priority: priority ? String(priority) : undefined,
      runId: run_id ? String(run_id) : undefined,
    });

    res.status(200).json(result);
  }

  static async getById(req: AuthenticatedRequest, res: Response): Promise<void> {
    const result = await ExceptionService.getExceptionDetail(String(req.params.id), req.organizationId!);
    res.status(200).json(result);
  }

  static async resolve(req: AuthenticatedRequest, res: Response): Promise<void> {
    const body = resolveSchema.parse(req.body);
    const candidateId = body.candidateId || body.candidate_id;

    const result = await ExceptionService.resolveException({
      exceptionId: String(req.params.id),
      action: body.action as any,
      candidateId,
      note: body.note,
      organizationId: req.organizationId!,
      userId: req.user!.id,
    });

    res.status(200).json(result);
  }

  static async bulkResolve(req: AuthenticatedRequest, res: Response): Promise<void> {
    const body = bulkResolveSchema.parse(req.body);
    const ids = body.exceptionIds || body.exception_ids || [];

    if (ids.length === 0) {
      res.status(400).json({ error: "BadRequest", detail: "exception_ids array is required." });
      return;
    }

    const result = await ExceptionService.bulkResolve({
      exceptionIds: ids,
      action: body.action as any,
      note: body.note,
      organizationId: req.organizationId!,
      userId: req.user!.id,
    });

    res.status(200).json(result);
  }
}
