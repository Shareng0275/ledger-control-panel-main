import { prisma } from "../config/database.js";
import { AppError } from "../middleware/errorHandler.js";

export class ManagerService {
  /**
   * List team members within the authorized organization
   */
  static async listTeamMembers(organizationId: string) {
    const memberships = await prisma.membership.findMany({
      where: { organizationId },
      include: {
        user: {
          select: { id: true, email: true, fullName: true, isActive: true, createdAt: true },
        },
      },
      orderBy: { role: "asc" },
    });

    return memberships.map((m) => ({
      id: m.user.id,
      email: m.user.email,
      full_name: m.user.fullName,
      role: m.role.toLowerCase(),
      is_active: m.user.isActive,
      joined_at: m.createdAt,
    }));
  }

  /**
   * Get manager approval queue (all submitted drafts and open high-priority exceptions)
   */
  static async getApprovalQueue(organizationId: string) {
    const [submittedDrafts, openExceptions] = await Promise.all([
      prisma.recordDraft.findMany({
        where: { organizationId, status: "SUBMITTED" },
        orderBy: { updatedAt: "desc" },
        include: {
          author: { select: { id: true, email: true, fullName: true } },
        },
      }),
      prisma.exception.findMany({
        where: { organizationId, status: "OPEN", priority: "HIGH" },
        orderBy: { createdAt: "desc" },
        take: 10,
        include: {
          transaction: true,
        },
      }),
    ]);

    return {
      pending_count: submittedDrafts.length + openExceptions.length,
      drafts: submittedDrafts.map((d) => ({
        id: d.id,
        title: d.title,
        description: d.description,
        amount: d.amount,
        currency: d.currency,
        category: d.category,
        status: d.status,
        version: d.version,
        author: d.author,
        submitted_at: d.updatedAt,
      })),
      high_priority_exceptions: openExceptions.map((e) => ({
        id: e.id,
        reason: e.reasonText,
        priority: e.priority,
        amount: Number(e.transaction.amount),
        description: e.transaction.description,
        date: e.transaction.transactionDate,
      })),
    };
  }

  /**
   * Approve a workflow submission
   */
  static async approveWorkflow(params: {
    id: string;
    organizationId: string;
    managerId: string;
    notes?: string;
  }) {
    const draft = await prisma.recordDraft.findFirst({
      where: { id: params.id, organizationId: params.organizationId },
    });

    if (!draft) throw new AppError("Workflow record not found.", 404);

    if (draft.status !== "SUBMITTED") {
      throw new AppError(`Cannot approve record with status '${draft.status}'. Must be 'SUBMITTED'.`, 400);
    }

    const updated = await prisma.recordDraft.update({
      where: { id: params.id },
      data: {
        status: "APPROVED",
        reviewedBy: params.managerId,
        reviewedAt: new Date(),
        reviewNotes: params.notes || "Approved by Manager",
        version: draft.version + 1,
      },
    });

    // Audit APPROVE
    await prisma.auditLog.create({
      data: {
        organizationId: params.organizationId,
        actorId: params.managerId,
        action: "workflow.approve",
        entityType: "RecordDraft",
        entityId: updated.id,
        details: JSON.stringify({ status: "APPROVED", reviewer_notes: params.notes }),
      },
    });

    return updated;
  }

  /**
   * Reject a workflow submission with required reason
   */
  static async rejectWorkflow(params: {
    id: string;
    organizationId: string;
    managerId: string;
    reason: string;
  }) {
    const reason = params.reason?.trim();
    if (!reason) {
      throw new AppError("Rejection reason is strictly required.", 422);
    }

    const draft = await prisma.recordDraft.findFirst({
      where: { id: params.id, organizationId: params.organizationId },
    });

    if (!draft) throw new AppError("Workflow record not found.", 404);

    if (draft.status !== "SUBMITTED") {
      throw new AppError(`Cannot reject record with status '${draft.status}'. Must be 'SUBMITTED'.`, 400);
    }

    const updated = await prisma.recordDraft.update({
      where: { id: params.id },
      data: {
        status: "REJECTED",
        reviewedBy: params.managerId,
        reviewedAt: new Date(),
        reviewNotes: reason,
        version: draft.version + 1,
      },
    });

    // Audit REJECT
    await prisma.auditLog.create({
      data: {
        organizationId: params.organizationId,
        actorId: params.managerId,
        action: "workflow.reject",
        entityType: "RecordDraft",
        entityId: updated.id,
        details: JSON.stringify({ status: "REJECTED", reason }),
      },
    });

    return updated;
  }

  /**
   * Assign a task to a team member
   */
  static async assignTask(params: {
    organizationId: string;
    managerId: string;
    assigneeId: string;
    taskType: string;
    targetId: string;
    instructions?: string;
  }) {
    const assigneeMembership = await prisma.membership.findFirst({
      where: { organizationId: params.organizationId, userId: params.assigneeId },
      include: { user: true },
    });

    if (!assigneeMembership) {
      throw new AppError("Target assignee is not a member of this organization.", 404);
    }

    // Audit ASSIGN
    const audit = await prisma.auditLog.create({
      data: {
        organizationId: params.organizationId,
        actorId: params.managerId,
        action: "workflow.assign",
        entityType: params.taskType,
        entityId: params.targetId,
        details: JSON.stringify({
          assignee_id: params.assigneeId,
          assignee_email: assigneeMembership.user.email,
          instructions: params.instructions || "Follow up on assigned reconciliation task",
        }),
      },
    });

    return {
      status: "ASSIGNED",
      assignment_id: audit.id,
      assignee: {
        id: assigneeMembership.user.id,
        email: assigneeMembership.user.email,
        full_name: assigneeMembership.user.fullName,
      },
      instructions: params.instructions,
    };
  }

  /**
   * Delegate a workflow item
   */
  static async delegateTask(params: {
    organizationId: string;
    managerId: string;
    delegateId: string;
    targetId: string;
    reason?: string;
  }) {
    const delegateMembership = await prisma.membership.findFirst({
      where: { organizationId: params.organizationId, userId: params.delegateId },
      include: { user: true },
    });

    if (!delegateMembership) {
      throw new AppError("Target delegate is not a member of this organization.", 404);
    }

    // Audit DELEGATE
    const audit = await prisma.auditLog.create({
      data: {
        organizationId: params.organizationId,
        actorId: params.managerId,
        action: "workflow.delegate",
        entityType: "WorkflowDelegation",
        entityId: params.targetId,
        details: JSON.stringify({
          delegate_id: params.delegateId,
          delegate_email: delegateMembership.user.email,
          reason: params.reason || "Delegated approval review",
        }),
      },
    });

    return {
      status: "DELEGATED",
      delegation_id: audit.id,
      delegate: {
        id: delegateMembership.user.id,
        email: delegateMembership.user.email,
        full_name: delegateMembership.user.fullName,
      },
      reason: params.reason,
    };
  }
}
