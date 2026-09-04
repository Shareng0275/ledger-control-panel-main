import type { Response } from "express";
import { z } from "zod";
import { ReconciliationService } from "../services/reconciliationService.js";
import type { AuthenticatedRequest } from "../types/index.js";

const runSchema = z.object({
  statement_upload_id: z.string().optional(),
  statementUploadId: z.string().optional(),
  ledger_upload_id: z.string().optional().nullable(),
  ledgerUploadId: z.string().optional().nullable(),
});

export class ReconciliationController {
  static async startRun(req: AuthenticatedRequest, res: Response): Promise<void> {
    const body = runSchema.parse(req.body);
    const stmtId = body.statementUploadId || body.statement_upload_id;
    const ledgerId = body.ledgerUploadId || body.ledger_upload_id || undefined;

    if (!stmtId) {
      res.status(400).json({ error: "BadRequest", detail: "statement_upload_id is required." });
      return;
    }

    const result = await ReconciliationService.startRun({
      statementUploadId: stmtId,
      ledgerUploadId: ledgerId,
      organizationId: req.organizationId!,
      userId: req.user!.id,
    });

    res.status(201).json(result);
  }

  static async getRun(req: AuthenticatedRequest, res: Response): Promise<void> {
    const runId = String(req.params.run_id || req.params.id);
    const result = await ReconciliationService.getRun(runId, req.organizationId!);
    res.status(200).json(result);
  }

  static async getRunSummary(req: AuthenticatedRequest, res: Response): Promise<void> {
    const runId = String(req.params.run_id || req.params.id);
    const result = await ReconciliationService.getRunSummary(runId, req.organizationId!);
    res.status(200).json(result);
  }
}
