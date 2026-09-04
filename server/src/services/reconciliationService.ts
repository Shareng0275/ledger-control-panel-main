import { prisma } from "../config/database.js";
import { dispatchReconciliationJob } from "../jobs/reconciliationQueue.js";
import { AppError } from "../middleware/errorHandler.js";

export class ReconciliationService {
  static async startRun(params: {
    statementUploadId: string;
    ledgerUploadId?: string;
    organizationId: string;
    userId: string;
  }) {
    const stmtUpload = await prisma.upload.findFirst({
      where: { id: params.statementUploadId, organizationId: params.organizationId },
    });

    if (!stmtUpload) {
      throw new AppError("Statement upload record not found.", 404);
    }

    if (params.ledgerUploadId) {
      const ledgerUpload = await prisma.upload.findFirst({
        where: { id: params.ledgerUploadId, organizationId: params.organizationId },
      });
      if (!ledgerUpload) {
        throw new AppError("Ledger upload record not found.", 404);
      }
    }

    const stmtTxCount = await prisma.transaction.count({
      where: { uploadId: params.statementUploadId, organizationId: params.organizationId },
    });

    const ledgerTxCount = params.ledgerUploadId
      ? await prisma.transaction.count({
          where: { uploadId: params.ledgerUploadId, organizationId: params.organizationId },
        })
      : 0;

    const totalTxs = stmtTxCount + ledgerTxCount;

    // Create ReconciliationRun record in PENDING state
    const run = await prisma.reconciliationRun.create({
      data: {
        organizationId: params.organizationId,
        statementUploadId: params.statementUploadId,
        ledgerUploadId: params.ledgerUploadId || null,
        status: "PROCESSING",
        totalTransactions: totalTxs,
        createdBy: params.userId,
      },
    });

    // Create Audit Log
    await prisma.auditLog.create({
      data: {
        organizationId: params.organizationId,
        actorId: params.userId,
        action: "reconciliation.started",
        entityType: "ReconciliationRun",
        entityId: run.id,
        details: JSON.stringify({ total_transactions: totalTxs }),
      },
    });

    // Dispatch background matching job
    await dispatchReconciliationJob({
      runId: run.id,
      organizationId: params.organizationId,
      userId: params.userId,
    });

    return {
      id: run.id,
      run_id: run.id,
      status: "processing",
      total_transactions: totalTxs,
      matched_count: 0,
      exception_count: 0,
      pending_review_count: 0,
      total_value_reconciled: "0.0000",
      average_confidence: null,
      summary: {
        total: totalTxs,
        matched: 0,
        exceptions: 0,
        pending_review: 0,
        matched_value: 0.0,
        exception_value: 0.0,
      },
      created_at: run.createdAt,
    };
  }

  static async getRun(runId: string, organizationId: string) {
    const whereClause: any = { organizationId };
    if (runId && runId !== "latest") {
      whereClause.id = runId;
    }

    const run = await prisma.reconciliationRun.findFirst({
      where: whereClause,
      orderBy: { createdAt: "desc" },
      include: {
        statementUpload: true,
        ledgerUpload: true,
      },
    });

    if (!run) throw new AppError("Reconciliation run not found.", 404);

    const matchedTxs = await prisma.transaction.aggregate({
      where: { reconciliationRunId: run.id, status: "MATCHED" },
      _sum: { amount: true },
    });

    const exceptionTxs = await prisma.transaction.aggregate({
      where: { reconciliationRunId: run.id, status: { in: ["EXCEPTION", "PENDING_REVIEW"] } },
      _sum: { amount: true },
    });

    const matchedVal = Math.abs(Number(matchedTxs._sum.amount || 0));
    const exceptionVal = Math.abs(Number(exceptionTxs._sum.amount || 0));

    return {
      id: run.id,
      run_id: run.id,
      status: run.status.toLowerCase(),
      total_transactions: run.totalTransactions,
      matched_count: run.matchedCount,
      exception_count: run.exceptionCount,
      pending_review_count: run.pendingReviewCount,
      total_value_reconciled: Number(run.totalValueReconciled).toFixed(4),
      average_confidence: run.averageConfidence ? Number(run.averageConfidence).toFixed(4) : null,
      error_message: run.errorMessage,
      started_at: run.startedAt,
      completed_at: run.completedAt,
      created_at: run.createdAt,
      summary: {
        total: run.totalTransactions,
        matched: run.matchedCount,
        exceptions: run.exceptionCount,
        pending_review: run.pendingReviewCount,
        matched_value: matchedVal,
        exception_value: exceptionVal,
      },
    };
  }

  static async getRunSummary(runId: string, organizationId: string) {
    const run = await this.getRun(runId, organizationId);

    const matches = await prisma.match.findMany({
      where: { reconciliationRunId: runId, organizationId },
    });

    const methodBreakdown = {
      deterministic: matches.filter((m) => m.method === "DETERMINISTIC").length,
      fuzzy: matches.filter((m) => m.method === "FUZZY").length,
      manual: matches.filter((m) => m.method === "MANUAL").length,
    };

    return {
      ...run,
      match_method_breakdown: methodBreakdown,
      confidence_distribution: [
        {
          status: "matched",
          count: run.matched_count,
          total_amount: run.summary.matched_value.toFixed(2),
          average_confidence: run.average_confidence || "1.0000",
        },
        {
          status: "exception",
          count: run.exception_count,
          total_amount: run.summary.exception_value.toFixed(2),
          average_confidence: null,
        },
      ],
    };
  }
}
