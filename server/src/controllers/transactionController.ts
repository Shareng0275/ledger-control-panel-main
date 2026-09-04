import type { Response } from "express";
import { TransactionService } from "../services/transactionService.js";
import type { AuthenticatedRequest } from "../types/index.js";

export class TransactionController {
  static async list(req: AuthenticatedRequest, res: Response): Promise<void> {
    const { page, page_size, search, status, source, run_id, sort_by, sort_order } = req.query;

    const result = await TransactionService.listTransactions({
      organizationId: req.organizationId!,
      page: page ? parseInt(String(page), 10) : undefined,
      pageSize: page_size ? parseInt(String(page_size), 10) : undefined,
      search: search ? String(search) : undefined,
      status: status ? String(status) : undefined,
      source: source ? String(source) : undefined,
      runId: run_id ? String(run_id) : undefined,
      sortBy: sort_by ? String(sort_by) : undefined,
      sortOrder: sort_order === "asc" ? "asc" : "desc",
    });

    res.status(200).json(result);
  }

  static async getById(req: AuthenticatedRequest, res: Response): Promise<void> {
    const result = await TransactionService.getTransactionById(String(req.params.id), req.organizationId!);
    res.status(200).json(result);
  }

  static async export(req: AuthenticatedRequest, res: Response): Promise<void> {
    const { search, status, source, run_id } = req.query;
    const csvData = await TransactionService.exportTransactionsCsv({
      organizationId: req.organizationId!,
      actorId: req.user?.id,
      search: search ? String(search) : undefined,
      status: status ? String(status) : undefined,
      source: source ? String(source) : undefined,
      runId: run_id ? String(run_id) : undefined,
    });

    res.setHeader("Content-Type", "text/csv");
    res.setHeader("Content-Disposition", `attachment; filename="transactions-${Date.now()}.csv"`);
    res.status(200).send(csvData);
  }
}
