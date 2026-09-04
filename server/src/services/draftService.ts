import { prisma } from "../config/database.js";
import { AppError } from "../middleware/errorHandler.js";

export class DraftService {
  /**
   * Create a new draft record (Editor capability)
   */
  static async createDraft(params: {
    organizationId: string;
    authorId: string;
    title: string;
    description: string;
    amount: number;
    currency?: string;
    category?: string;
  }) {
    const title = params.title?.trim();
    const description = params.description?.trim();
    if (!title || !description) {
      throw new AppError("Draft title and description are required.", 422);
    }

    const draft = await prisma.recordDraft.create({
      data: {
        organizationId: params.organizationId,
        authorId: params.authorId,
        title,
        description,
        amount: Number(params.amount) || 0,
        currency: params.currency || "USD",
        category: params.category || "ADJUSTMENT",
        status: "DRAFT",
        version: 1,
      },
      include: {
        author: { select: { id: true, email: true, fullName: true } },
      },
    });

    // Audit CREATE
    await prisma.auditLog.create({
      data: {
        organizationId: params.organizationId,
        actorId: params.authorId,
        action: "draft.create",
        entityType: "RecordDraft",
        entityId: draft.id,
        details: JSON.stringify({ title, amount: draft.amount, status: "DRAFT" }),
      },
    });

    return draft;
  }

  /**
   * List authorized drafts within organization
   */
  static async listDrafts(params: {
    organizationId: string;
    authorId?: string;
    status?: string;
  }) {
    const where: any = { organizationId: params.organizationId };
    if (params.status) where.status = params.status.toUpperCase();
    if (params.authorId) where.authorId = params.authorId;

    return prisma.recordDraft.findMany({
      where,
      orderBy: { updatedAt: "desc" },
      include: {
        author: { select: { id: true, email: true, fullName: true } },
        reviewer: { select: { id: true, email: true, fullName: true } },
      },
    });
  }

  /**
   * Get draft by ID with tenant check
   */
  static async getDraftById(id: string, organizationId: string) {
    const draft = await prisma.recordDraft.findFirst({
      where: { id, organizationId },
      include: {
        author: { select: { id: true, email: true, fullName: true } },
        reviewer: { select: { id: true, email: true, fullName: true } },
      },
    });
    if (!draft) throw new AppError("Draft record not found.", 404);
    return draft;
  }

  /**
   * Update draft with ownership validation & optimistic concurrency protection
   */
  static async updateDraft(params: {
    id: string;
    organizationId: string;
    userId: string;
    userRole: string;
    title?: string;
    description?: string;
    amount?: number;
    currency?: string;
    category?: string;
    expectedVersion?: number;
  }) {
    const draft = await prisma.recordDraft.findFirst({
      where: { id: params.id, organizationId: params.organizationId },
    });

    if (!draft) throw new AppError("Draft record not found.", 404);

    // Ownership check: Only author or manager/admin can edit
    const isOwner = draft.authorId === params.userId;
    const isManager = ["admin", "administrator", "manager"].includes(params.userRole.toLowerCase());
    if (!isOwner && !isManager) {
      throw new AppError("Forbidden: You can only edit records you authored.", 403);
    }

    if (draft.status === "APPROVED") {
      throw new AppError("Cannot modify an already approved and published record.", 400);
    }

    // Optimistic concurrency protection
    if (params.expectedVersion !== undefined && draft.version !== params.expectedVersion) {
      throw new AppError("Conflict: Record has been modified by another process. Please refresh and retry.", 409);
    }

    const updated = await prisma.recordDraft.update({
      where: { id: params.id },
      data: {
        title: params.title !== undefined ? params.title.trim() : draft.title,
        description: params.description !== undefined ? params.description.trim() : draft.description,
        amount: params.amount !== undefined ? Number(params.amount) : draft.amount,
        currency: params.currency || draft.currency,
        category: params.category || draft.category,
        version: draft.version + 1,
      },
      include: {
        author: { select: { id: true, email: true, fullName: true } },
      },
    });

    // Audit UPDATE
    await prisma.auditLog.create({
      data: {
        organizationId: params.organizationId,
        actorId: params.userId,
        action: "draft.update",
        entityType: "RecordDraft",
        entityId: updated.id,
        details: JSON.stringify({ version: updated.version }),
      },
    });

    return updated;
  }

  /**
   * Submit draft for Manager review
   */
  static async submitDraft(params: {
    id: string;
    organizationId: string;
    userId: string;
    userRole: string;
  }) {
    const draft = await prisma.recordDraft.findFirst({
      where: { id: params.id, organizationId: params.organizationId },
    });

    if (!draft) throw new AppError("Draft record not found.", 404);

    const isOwner = draft.authorId === params.userId;
    const isManager = ["admin", "administrator", "manager"].includes(params.userRole.toLowerCase());
    if (!isOwner && !isManager) {
      throw new AppError("Forbidden: You can only submit your own drafts.", 403);
    }

    if (draft.status !== "DRAFT") {
      throw new AppError(`Cannot submit record with status '${draft.status}'. Must be 'DRAFT'.`, 400);
    }

    const submitted = await prisma.recordDraft.update({
      where: { id: params.id },
      data: {
        status: "SUBMITTED",
        version: draft.version + 1,
      },
    });

    // Audit SUBMIT
    await prisma.auditLog.create({
      data: {
        organizationId: params.organizationId,
        actorId: params.userId,
        action: "draft.submit",
        entityType: "RecordDraft",
        entityId: submitted.id,
        details: JSON.stringify({ status: "SUBMITTED", version: submitted.version }),
      },
    });

    return submitted;
  }

  /**
   * Approve draft (Restricted to Manager / Admin)
   */
  static async approveDraft(params: {
    id: string;
    organizationId: string;
    reviewerId: string;
    notes?: string;
  }) {
    const draft = await prisma.recordDraft.findFirst({
      where: { id: params.id, organizationId: params.organizationId },
    });

    if (!draft) throw new AppError("Draft record not found.", 404);

    const approved = await prisma.recordDraft.update({
      where: { id: params.id },
      data: {
        status: "APPROVED",
        reviewedBy: params.reviewerId,
        reviewedAt: new Date(),
        reviewNotes: params.notes || "Approved by Manager",
        version: draft.version + 1,
      },
    });

    // Audit APPROVE
    await prisma.auditLog.create({
      data: {
        organizationId: params.organizationId,
        actorId: params.reviewerId,
        action: "draft.approve",
        entityType: "RecordDraft",
        entityId: approved.id,
        details: JSON.stringify({ status: "APPROVED" }),
      },
    });

    return approved;
  }
}
