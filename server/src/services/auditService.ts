import { prisma } from "../config/database.js";

export class AuditService {
  static async listAuditLogs(params: {
    organizationId: string;
    runId?: string;
    action?: string;
    entityType?: string;
    startDate?: Date;
    endDate?: Date;
    page?: number;
    pageSize?: number;
  }) {
    const page = Math.max(1, params.page || 1);
    const pageSize = Math.min(100, Math.max(1, params.pageSize || 25));
    const skip = (page - 1) * pageSize;

    const where: any = { organizationId: params.organizationId };

    if (params.action) {
      where.action = { contains: params.action, mode: "insensitive" };
    }
    if (params.entityType) {
      where.entityType = { contains: params.entityType, mode: "insensitive" };
    }
    if (params.startDate || params.endDate) {
      where.createdAt = {};
      if (params.startDate) where.createdAt.gte = params.startDate;
      if (params.endDate) where.createdAt.lte = params.endDate;
    }

    const [items, total] = await Promise.all([
      prisma.auditLog.findMany({
        where,
        skip,
        take: pageSize,
        orderBy: { createdAt: "desc" },
        include: { actor: true },
      }),
      prisma.auditLog.count({ where }),
    ]);

    const formatted = items.map((log) => {
      let parsedDetails = log.details;
      if (typeof log.details === "string") {
        try {
          parsedDetails = JSON.parse(log.details);
        } catch {
          parsedDetails = log.details;
        }
      }

      return {
        id: log.id,
        timestamp: log.createdAt.toISOString(),
        actor: log.actor ? log.actor.fullName : "System Engine",
        action: log.action,
        entity_type: log.entityType,
        entity_id: log.entityId,
        details: parsedDetails,
        ip_address: log.ipAddress,
      };
    });

    const totalPages = Math.ceil(total / pageSize) || 1;

    return {
      items: formatted,
      entries: formatted, // Frontend compatibility
      total,
      page,
      page_size: pageSize,
      total_pages: totalPages,
      has_next: page < totalPages,
      has_prev: page > 1,
    };
  }
}
