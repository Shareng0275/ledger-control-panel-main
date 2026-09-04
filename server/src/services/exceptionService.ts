import { prisma } from "../config/database.js";
import { AppError } from "../middleware/errorHandler.js";

export class ExceptionService {
  static async listExceptions(params: {
    organizationId: string;
    page?: number;
    pageSize?: number;
    status?: string;
    priority?: string;
    runId?: string;
  }) {
    const page = Math.max(1, params.page || 1);
    const pageSize = Math.min(100, Math.max(1, params.pageSize || 25));
    const skip = (page - 1) * pageSize;

    const where: any = { organizationId: params.organizationId };

    if (params.status) {
      where.status = params.status.toUpperCase();
    }
    if (params.priority) {
      where.priority = params.priority.toUpperCase();
    }
    if (params.runId) {
      where.reconciliationRunId = params.runId;
    }

    const [items, total] = await Promise.all([
      prisma.exception.findMany({
        where,
        skip,
        take: pageSize,
        orderBy: { createdAt: "desc" },
        include: {
          transaction: true,
          bestCandidateTransaction: true,
        },
      }),
      prisma.exception.count({ where }),
    ]);

    const formatted = items.map((exc) => ({
      id: exc.id,
      reconciliation_run_id: exc.reconciliationRunId,
      transaction_id: exc.transactionId,
      date: exc.transaction.transactionDate.toISOString(),
      description: exc.transaction.description,
      amount: Number(exc.transaction.amount),
      currency: exc.transaction.currency,
      status: exc.status.toLowerCase(),
      priority: exc.priority.toLowerCase(),
      reason: exc.reasonText,
      confidence: exc.transaction.confidence ? Number(exc.transaction.confidence) : null,
      statement_side: {
        id: exc.transaction.id,
        date: exc.transaction.transactionDate.toISOString(),
        description: exc.transaction.description,
        amount: Number(exc.transaction.amount),
        source: exc.transaction.source.toLowerCase(),
      },
      best_candidate: exc.bestCandidateTransaction
        ? {
            id: exc.bestCandidateTransaction.id,
            date: exc.bestCandidateTransaction.transactionDate.toISOString(),
            description: exc.bestCandidateTransaction.description,
            amount: Number(exc.bestCandidateTransaction.amount),
            source: exc.bestCandidateTransaction.source.toLowerCase(),
            confidence: exc.transaction.confidence ? Number(exc.transaction.confidence) : null,
          }
        : null,
    }));

    const totalPages = Math.ceil(total / pageSize) || 1;

    return {
      items: formatted,
      exceptions: formatted, // Frontend compatibility
      total,
      page,
      page_size: pageSize,
      total_pages: totalPages,
      has_next: page < totalPages,
      has_prev: page > 1,
    };
  }

  static async getExceptionDetail(id: string, organizationId: string) {
    const exc = await prisma.exception.findFirst({
      where: { id, organizationId },
      include: {
        transaction: true,
        bestCandidateTransaction: true,
        resolutions: {
          include: { resolver: true },
        },
      },
    });

    if (!exc) throw new AppError("Exception record not found.", 404);

    return {
      id: exc.id,
      reconciliation_run_id: exc.reconciliationRunId,
      transaction_id: exc.transactionId,
      date: exc.transaction.transactionDate.toISOString(),
      description: exc.transaction.description,
      amount: Number(exc.transaction.amount),
      currency: exc.transaction.currency,
      status: exc.status.toLowerCase(),
      priority: exc.priority.toLowerCase(),
      reason: exc.reasonText,
      confidence: exc.transaction.confidence ? Number(exc.transaction.confidence) : null,
      statement_side: {
        id: exc.transaction.id,
        date: exc.transaction.transactionDate.toISOString(),
        description: exc.transaction.description,
        amount: Number(exc.transaction.amount),
        currency: exc.transaction.currency,
        source: exc.transaction.source.toLowerCase(),
        external_reference: exc.transaction.externalReference,
      },
      candidate_side: exc.bestCandidateTransaction
        ? {
            id: exc.bestCandidateTransaction.id,
            date: exc.bestCandidateTransaction.transactionDate.toISOString(),
            description: exc.bestCandidateTransaction.description,
            amount: Number(exc.bestCandidateTransaction.amount),
            currency: exc.bestCandidateTransaction.currency,
            source: exc.bestCandidateTransaction.source.toLowerCase(),
            external_reference: exc.bestCandidateTransaction.externalReference,
          }
        : null,
      resolutions: exc.resolutions.map((r) => ({
        id: r.id,
        action: r.action,
        note: r.note,
        resolved_by: r.resolver.fullName,
        resolved_at: r.createdAt.toISOString(),
      })),
    };
  }

  static async resolveException(params: {
    exceptionId: string;
    action: "CONFIRM_MATCH" | "REJECT_MATCH" | "confirm_match" | "reject";
    candidateId?: string;
    note?: string;
    organizationId: string;
    userId: string;
  }) {
    const exc = await prisma.exception.findFirst({
      where: { id: params.exceptionId, organizationId: params.organizationId },
      include: { transaction: true, bestCandidateTransaction: true },
    });

    if (!exc) throw new AppError("Exception not found.", 404);
    if (exc.status === "RESOLVED") {
      throw new AppError("Exception has already been resolved.", 400);
    }

    const actionUpper = params.action.toUpperCase();
    const isConfirm = actionUpper.includes("CONFIRM");
    const candidateId = params.candidateId || exc.bestCandidateTransactionId;

    let matchId: string | null = null;

    if (isConfirm) {
      if (candidateId) {
        const match = await prisma.match.create({
          data: {
            organizationId: params.organizationId,
            reconciliationRunId: exc.reconciliationRunId,
            statementTransactionId: exc.transaction.source === "STATEMENT" ? exc.transaction.id : candidateId,
            ledgerTransactionId: exc.transaction.source === "LEDGER" ? exc.transaction.id : candidateId,
            method: "MANUAL",
            confidence: 1.0,
            reason: `Manual Match Confirmation: ${params.note || "Approved by controller"}`,
          },
        });
        matchId = match.id;

        await prisma.transaction.update({
          where: { id: exc.transaction.id },
          data: { status: "MATCHED", confidence: 1.0 },
        });

        await prisma.transaction.update({
          where: { id: candidateId },
          data: { status: "MATCHED", confidence: 1.0 },
        });
      } else {
        // Single-sided transaction verification / adjustment approval
        const match = await prisma.match.create({
          data: {
            organizationId: params.organizationId,
            reconciliationRunId: exc.reconciliationRunId,
            statementTransactionId: exc.transaction.id,
            ledgerTransactionId: exc.transaction.id,
            method: "MANUAL",
            confidence: 1.0,
            reason: `Single-Sided Entry Confirmation: ${params.note || "Acknowledged and resolved by controller"}`,
          },
        });
        matchId = match.id;

        await prisma.transaction.update({
          where: { id: exc.transaction.id },
          data: { status: "MATCHED", confidence: 1.0 },
        });
      }
    } else {
      await prisma.transaction.update({
        where: { id: exc.transaction.id },
        data: { status: "EXCEPTION" },
      });
    }

    // Update exception status
    await prisma.exception.update({
      where: { id: exc.id },
      data: {
        status: isConfirm ? "RESOLVED" : "REJECTED",
        resolutionAction: actionUpper,
        resolvedBy: params.userId,
        resolvedAt: new Date(),
      },
    });

    // Record resolution detail
    await prisma.exceptionResolution.create({
      data: {
        organizationId: params.organizationId,
        exceptionId: exc.id,
        reconciliationRunId: exc.reconciliationRunId,
        action: actionUpper,
        candidateTransactionId: candidateId || null,
        note: params.note || null,
        resolvedBy: params.userId,
      },
    });

    // Append Audit Log
    await prisma.auditLog.create({
      data: {
        organizationId: params.organizationId,
        actorId: params.userId,
        action: isConfirm ? "exception.resolved_match" : "exception.rejected",
        entityType: "Exception",
        entityId: exc.id,
        details: JSON.stringify({ action: actionUpper, candidateId, note: params.note }),
      },
    });

    return {
      exception_id: exc.id,
      status: isConfirm ? "resolved" : "rejected",
      message: isConfirm ? "Exception confirmed and matched successfully." : "Exception rejected.",
      match_id: matchId,
    };
  }

  static async bulkResolve(params: {
    exceptionIds: string[];
    action: "CONFIRM_MATCH" | "REJECT_MATCH" | "confirm_match" | "reject";
    note?: string;
    organizationId: string;
    userId: string;
  }) {
    let resolvedCount = 0;
    let failedCount = 0;

    for (const id of params.exceptionIds) {
      try {
        await this.resolveException({
          exceptionId: id,
          action: params.action,
          note: params.note,
          organizationId: params.organizationId,
          userId: params.userId,
        });
        resolvedCount++;
      } catch (err: any) {
        console.warn(`[BulkResolve] Error on ${id}: ${err.message}`);
        failedCount++;
      }
    }

    return {
      total_requested: params.exceptionIds.length,
      resolved_count: resolvedCount,
      failed_count: failedCount,
    };
  }
}
