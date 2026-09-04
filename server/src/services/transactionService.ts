import { prisma } from "../config/database.js";
import { AppError } from "../middleware/errorHandler.js";

export class TransactionService {
  static async listTransactions(params: {
    organizationId: string;
    page?: number;
    pageSize?: number;
    search?: string;
    status?: string;
    source?: string;
    runId?: string;
    sortBy?: string;
    sortOrder?: "asc" | "desc";
  }) {
    const page = Math.max(1, params.page || 1);
    const pageSize = Math.min(100, Math.max(1, params.pageSize || 25));
    const skip = (page - 1) * pageSize;

    const where: any = { organizationId: params.organizationId };

    if (params.status) {
      where.status = params.status.toUpperCase();
    }

    if (params.source) {
      where.source = params.source.toUpperCase();
    }

    if (params.runId) {
      where.reconciliationRunId = params.runId;
    }

    if (params.search) {
      const q = params.search.trim();
      where.OR = [
        { description: { contains: q, mode: "insensitive" } },
        { normalizedDescription: { contains: q, mode: "insensitive" } },
        { externalReference: { contains: q, mode: "insensitive" } },
        { normalizedReference: { contains: q, mode: "insensitive" } },
      ];
    }

    const sortField = params.sortBy === "amount" ? "amount" : params.sortBy === "confidence" ? "confidence" : "transactionDate";
    const sortDir = params.sortOrder === "asc" ? "asc" : "desc";

    const [items, total] = await Promise.all([
      prisma.transaction.findMany({
        where,
        skip,
        take: pageSize,
        orderBy: { [sortField]: sortDir },
        include: {
          statementMatches: true,
          ledgerMatches: true,
        },
      }),
      prisma.transaction.count({ where }),
    ]);

    const formatted = items.map((tx) => {
      const match = tx.statementMatches[0] || tx.ledgerMatches[0];
      return {
        id: tx.id,
        date: tx.transactionDate.toISOString(),
        description: tx.description,
        amount: Number(tx.amount),
        currency: tx.currency,
        source: tx.source.toLowerCase(),
        status: tx.status.toLowerCase(),
        confidence: tx.confidence ? Number(tx.confidence) : null,
        external_ref: tx.externalReference,
        match_id: match ? match.id : null,
        match_method: match ? match.method.toLowerCase() : null,
        reason: match ? match.reason : null,
      };
    });

    const totalPages = Math.ceil(total / pageSize) || 1;

    return {
      items: formatted,
      transactions: formatted, // Frontend compatibility alias
      total,
      page,
      page_size: pageSize,
      total_pages: totalPages,
      has_next: page < totalPages,
      has_prev: page > 1,
    };
  }

  static async getTransactionById(id: string, organizationId: string) {
    const tx = await prisma.transaction.findFirst({
      where: { id, organizationId },
      include: {
        statementMatches: { include: { ledgerTransaction: true } },
        ledgerMatches: { include: { statementTransaction: true } },
      },
    });

    if (!tx) throw new AppError("Transaction not found.", 404);

    const match = tx.statementMatches[0] || tx.ledgerMatches[0];
    const counterpart = tx.statementMatches[0]?.ledgerTransaction || tx.ledgerMatches[0]?.statementTransaction;

    return {
      id: tx.id,
      date: tx.transactionDate.toISOString(),
      description: tx.description,
      amount: Number(tx.amount),
      currency: tx.currency,
      source: tx.source.toLowerCase(),
      status: tx.status.toLowerCase(),
      confidence: tx.confidence ? Number(tx.confidence) : null,
      external_ref: tx.externalReference,
      match_id: match ? match.id : null,
      match_method: match ? match.method.toLowerCase() : null,
      reason: match ? match.reason : null,
      counterpart: counterpart
        ? {
            id: counterpart.id,
            date: counterpart.transactionDate.toISOString(),
            description: counterpart.description,
            amount: Number(counterpart.amount),
            source: counterpart.source.toLowerCase(),
          }
        : null,
    };
  }

  static async exportTransactionsCsv(params: {
    organizationId: string;
    actorId?: string;
    search?: string;
    status?: string;
    source?: string;
    runId?: string;
  }): Promise<string> {
    const where: any = { organizationId: params.organizationId };
    if (params.status) where.status = params.status.toUpperCase();
    if (params.source) where.source = params.source.toUpperCase();
    if (params.runId) where.reconciliationRunId = params.runId;

    if (params.search) {
      const q = params.search.trim();
      where.OR = [
        { description: { contains: q, mode: "insensitive" } },
        { externalReference: { contains: q, mode: "insensitive" } },
      ];
    }

    const items = await prisma.transaction.findMany({
      where,
      orderBy: { transactionDate: "desc" },
      take: 5000,
    });

    if (params.actorId) {
      await prisma.auditLog.create({
        data: {
          organizationId: params.organizationId,
          actorId: params.actorId,
          action: "report.exported",
          entityType: "TransactionReport",
          entityId: params.organizationId,
          details: JSON.stringify({ recordCount: items.length, format: "csv" }),
        },
      });
    }

    const headers = ["ID", "Date", "Description", "Amount", "Currency", "Source", "Status", "Confidence", "External Reference"];
    const rows = items.map((t) => [
      t.id,
      t.transactionDate.toISOString().split("T")[0],
      `"${t.description.replace(/"/g, '""')}"`,
      t.amount,
      t.currency,
      t.source,
      t.status,
      t.confidence ?? "",
      `"${(t.externalReference || "").replace(/"/g, '""')}"`,
    ]);

    return [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
  }
}
