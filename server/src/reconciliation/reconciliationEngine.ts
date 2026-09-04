import { prisma } from "../config/database.js";
import { config } from "../config/index.js";
import type { FuzzyScoreResult } from "../types/index.js";
import { FuzzyMatcher } from "./fuzzyMatcher.js";

export class ReconciliationEngine {
  /**
   * Run the full two-pass reconciliation engine on a run record.
   */
  static async executeRun(runId: string, organizationId: string, userId: string): Promise<void> {
    console.log(`[ReconciliationEngine] Starting run ${runId} for org ${organizationId}`);

    const run = await prisma.reconciliationRun.findFirst({
      where: { id: runId, organizationId },
    });

    if (!run) throw new Error(`Reconciliation run ${runId} not found.`);

    await prisma.reconciliationRun.update({
      where: { id: runId },
      data: {
        status: "PROCESSING",
        startedAt: new Date(),
      },
    });

    try {
      // 1. Fetch statement & ledger transactions
      const statementTxs = await prisma.transaction.findMany({
        where: {
          organizationId,
          uploadId: run.statementUploadId,
          status: { in: ["UNMATCHED", "PENDING_REVIEW"] },
        },
      });

      const ledgerTxs = run.ledgerUploadId
        ? await prisma.transaction.findMany({
            where: {
              organizationId,
              uploadId: run.ledgerUploadId,
              status: { in: ["UNMATCHED", "PENDING_REVIEW"] },
            },
          })
        : [];

      console.log(`[ReconciliationEngine] Ingested ${statementTxs.length} statement txs, ${ledgerTxs.length} ledger txs.`);

      const matchedStatementIds = new Set<string>();
      const matchedLedgerIds = new Set<string>();

      let deterministicMatchCount = 0;
      let fuzzyMatchCount = 0;
      let totalReconciledValue = 0;

      // ─── PASS 1: DETERMINISTIC MATCHING ──────────────────────────────────
      // Rule 1: Exact Reference Match
      for (const s of statementTxs) {
        if (matchedStatementIds.has(s.id)) continue;
        if (!s.normalizedReference) continue;

        const candidate = ledgerTxs.find(
          (l) =>
            !matchedLedgerIds.has(l.id) &&
            l.normalizedReference &&
            l.normalizedReference === s.normalizedReference &&
            Number(l.amount) === Number(s.amount),
        );

        if (candidate) {
          matchedStatementIds.add(s.id);
          matchedLedgerIds.add(candidate.id);
          deterministicMatchCount++;
          totalReconciledValue += Math.abs(Number(s.amount));

          await this.createMatchRecord({
            runId,
            orgId: organizationId,
            statementTxId: s.id,
            ledgerTxId: candidate.id,
            method: "DETERMINISTIC",
            confidence: 1.0,
            reason: "Rule 1: Exact Reference & Amount Match (100%)",
          });
        }
      }

      // Rule 2: Exact Amount + Exact Date Match
      for (const s of statementTxs) {
        if (matchedStatementIds.has(s.id)) continue;

        const sDateStr = s.transactionDate.toISOString().slice(0, 10);
        const candidate = ledgerTxs.find((l) => {
          if (matchedLedgerIds.has(l.id)) return false;
          if (Number(l.amount) !== Number(s.amount)) return false;
          const lDateStr = l.transactionDate.toISOString().slice(0, 10);
          return lDateStr === sDateStr;
        });

        if (candidate) {
          matchedStatementIds.add(s.id);
          matchedLedgerIds.add(candidate.id);
          deterministicMatchCount++;
          totalReconciledValue += Math.abs(Number(s.amount));

          await this.createMatchRecord({
            runId,
            orgId: organizationId,
            statementTxId: s.id,
            ledgerTxId: candidate.id,
            method: "DETERMINISTIC",
            confidence: 1.0,
            reason: "Rule 2: Exact Amount & Transaction Date Match (100%)",
          });
        }
      }

      // Rule 3: Exact Amount + Normalized Description Match
      for (const s of statementTxs) {
        if (matchedStatementIds.has(s.id)) continue;
        if (!s.normalizedDescription) continue;

        const candidate = ledgerTxs.find((l) => {
          if (matchedLedgerIds.has(l.id)) return false;
          if (Number(l.amount) !== Number(s.amount)) return false;
          return l.normalizedDescription && l.normalizedDescription === s.normalizedDescription;
        });

        if (candidate) {
          matchedStatementIds.add(s.id);
          matchedLedgerIds.add(candidate.id);
          deterministicMatchCount++;
          totalReconciledValue += Math.abs(Number(s.amount));

          await this.createMatchRecord({
            runId,
            orgId: organizationId,
            statementTxId: s.id,
            ledgerTxId: candidate.id,
            method: "DETERMINISTIC",
            confidence: 1.0,
            reason: "Rule 3: Exact Amount & Normalized Description Match (100%)",
          });
        }
      }

      // Rule 4: Configurable Date Tolerance (±2 Days)
      for (const s of statementTxs) {
        if (matchedStatementIds.has(s.id)) continue;

        const sTime = s.transactionDate.getTime();
        const candidate = ledgerTxs.find((l) => {
          if (matchedLedgerIds.has(l.id)) return false;
          if (Number(l.amount) !== Number(s.amount)) return false;
          const diffDays = Math.abs(sTime - l.transactionDate.getTime()) / (1000 * 60 * 60 * 24);
          return diffDays <= 2;
        });

        if (candidate) {
          matchedStatementIds.add(s.id);
          matchedLedgerIds.add(candidate.id);
          deterministicMatchCount++;
          totalReconciledValue += Math.abs(Number(s.amount));

          await this.createMatchRecord({
            runId,
            orgId: organizationId,
            statementTxId: s.id,
            ledgerTxId: candidate.id,
            method: "DETERMINISTIC",
            confidence: 0.98,
            reason: "Rule 4: Exact Amount within Date Settlement Tolerance (98%)",
          });
        }
      }

      // ─── PASS 2: AI / FUZZY MATCHING & CONFIDENCE SCORING ───────────────
      const unresolvedStatements = statementTxs.filter((s) => !matchedStatementIds.has(s.id));
      const availableLedgers = ledgerTxs.filter((l) => !matchedLedgerIds.has(l.id));

      let pendingReviewCount = 0;
      let exceptionCount = 0;

      for (const s of unresolvedStatements) {
        let bestCandidate: (typeof ledgerTxs)[0] | null = null;
        let bestScore: FuzzyScoreResult | null = null;

        for (const l of availableLedgers) {
          if (matchedLedgerIds.has(l.id)) continue;

          // Quick candidate filter: Date within window
          const diffDays = Math.abs(s.transactionDate.getTime() - l.transactionDate.getTime()) / (1000 * 60 * 60 * 24);
          if (diffDays > config.FUZZY_MAX_DATE_DIFF_DAYS) continue;

          const score = FuzzyMatcher.scorePair(
            {
              amount: Number(s.amount),
              transactionDate: s.transactionDate,
              description: s.description,
              normalizedDescription: s.normalizedDescription,
              externalReference: s.externalReference,
              normalizedReference: s.normalizedReference,
            },
            {
              amount: Number(l.amount),
              transactionDate: l.transactionDate,
              description: l.description,
              normalizedDescription: l.normalizedDescription,
              externalReference: l.externalReference,
              normalizedReference: l.normalizedReference,
            },
          );

          if (!bestScore || score.overallConfidence > bestScore.overallConfidence) {
            bestScore = score;
            bestCandidate = l;
          }
        }

        if (bestCandidate && bestScore && bestScore.overallConfidence >= config.FUZZY_AUTO_MATCH_THRESHOLD) {
          // Auto-match (High confidence fuzzy match >= 0.88)
          matchedStatementIds.add(s.id);
          matchedLedgerIds.add(bestCandidate.id);
          fuzzyMatchCount++;
          totalReconciledValue += Math.abs(Number(s.amount));

          await this.createMatchRecord({
            runId,
            orgId: organizationId,
            statementTxId: s.id,
            ledgerTxId: bestCandidate.id,
            method: "FUZZY",
            confidence: bestScore.overallConfidence,
            reason: bestScore.explanation,
            scoreDetails: bestScore as unknown as Record<string, unknown>,
          });
        } else if (bestCandidate && bestScore && bestScore.overallConfidence >= config.FUZZY_REVIEW_THRESHOLD) {
          // Pending Review (0.65 - 0.87)
          pendingReviewCount++;
          await prisma.transaction.update({
            where: { id: s.id },
            data: {
              status: "PENDING_REVIEW",
              confidence: bestScore.overallConfidence,
              reconciliationRunId: runId,
            },
          });

          await prisma.exception.create({
            data: {
              organizationId,
              reconciliationRunId: runId,
              transactionId: s.id,
              bestCandidateTransactionId: bestCandidate.id,
              reasonText: `Proposed match with ${(bestScore.overallConfidence * 100).toFixed(1)}% confidence: ${bestScore.explanation}`,
              priority: "MEDIUM",
              status: "PENDING_REVIEW",
            },
          });
        } else {
          // Open Exception (< 0.65)
          exceptionCount++;
          await prisma.transaction.update({
            where: { id: s.id },
            data: {
              status: "EXCEPTION",
              reconciliationRunId: runId,
            },
          });

          await prisma.exception.create({
            data: {
              organizationId,
              reconciliationRunId: runId,
              transactionId: s.id,
              bestCandidateTransactionId: bestCandidate ? bestCandidate.id : null,
              reasonText: bestScore
                ? `Low confidence match (${(bestScore.overallConfidence * 100).toFixed(1)}%): ${bestScore.explanation}`
                : "No matching candidate found in ledger records within date and amount tolerance.",
              priority: Number(s.amount) > 10000 ? "CRITICAL" : "HIGH",
              status: "OPEN",
            },
          });
        }
      }

      // Any remaining unresolved ledger items become exceptions
      const remainingLedgers = availableLedgers.filter((l) => !matchedLedgerIds.has(l.id));
      for (const l of remainingLedgers) {
        exceptionCount++;
        await prisma.transaction.update({
          where: { id: l.id },
          data: {
            status: "EXCEPTION",
            reconciliationRunId: runId,
          },
        });

        await prisma.exception.create({
          data: {
            organizationId,
            reconciliationRunId: runId,
            transactionId: l.id,
            reasonText: "Unmatched internal ledger entry with no counterpart in bank statement.",
            priority: Number(l.amount) > 10000 ? "HIGH" : "MEDIUM",
            status: "OPEN",
          },
        });
      }

      const totalMatched = deterministicMatchCount + fuzzyMatchCount;
      const totalTxs = statementTxs.length + ledgerTxs.length;
      const avgConfidence = totalMatched > 0 ? (deterministicMatchCount * 1.0 + fuzzyMatchCount * 0.94) / totalMatched : 0.0;

      // Update ReconciliationRun Record
      await prisma.reconciliationRun.update({
        where: { id: runId },
        data: {
          status: "COMPLETE",
          totalTransactions: totalTxs,
          matchedCount: totalMatched,
          exceptionCount,
          pendingReviewCount,
          totalValueReconciled: totalReconciledValue,
          averageConfidence: Math.round(avgConfidence * 10000) / 10000,
          completedAt: new Date(),
        },
      });

      // Append Audit Log
      await prisma.auditLog.create({
        data: {
          organizationId,
          actorId: userId,
          action: "reconciliation.completed",
          entityType: "ReconciliationRun",
          entityId: runId,
          details: JSON.stringify({
            total_transactions: totalTxs,
            matched_count: totalMatched,
            deterministic_matches: deterministicMatchCount,
            fuzzy_matches: fuzzyMatchCount,
            exception_count: exceptionCount,
            pending_review_count: pendingReviewCount,
            total_value_reconciled: totalReconciledValue,
          }),
        },
      });

      console.log(`[ReconciliationEngine] Completed run ${runId}: ${totalMatched} matched, ${exceptionCount} exceptions.`);
    } catch (err: any) {
      console.error(`[ReconciliationEngine] Error in run ${runId}:`, err);
      await prisma.reconciliationRun.update({
        where: { id: runId },
        data: {
          status: "FAILED",
          errorMessage: err.message || "Unexpected reconciliation execution failure.",
          completedAt: new Date(),
        },
      });
      throw err;
    }
  }

  private static async createMatchRecord(params: {
    runId: string;
    orgId: string;
    statementTxId: string;
    ledgerTxId: string;
    method: "DETERMINISTIC" | "FUZZY" | "MANUAL";
    confidence: number;
    reason: string;
    scoreDetails?: Record<string, unknown>;
  }): Promise<void> {
    const existing = await prisma.match.findFirst({
      where: {
        OR: [
          { statementTransactionId: params.statementTxId },
          { ledgerTransactionId: params.ledgerTxId },
        ],
      },
    });

    if (existing) {
      return;
    }

    await prisma.match.create({
      data: {
        organizationId: params.orgId,
        reconciliationRunId: params.runId,
        statementTransactionId: params.statementTxId,
        ledgerTransactionId: params.ledgerTxId,
        method: params.method,
        confidence: params.confidence,
        reason: params.reason,
        scoreDetails: params.scoreDetails ? JSON.stringify(params.scoreDetails) : undefined,
      },
    });

    await prisma.transaction.update({
      where: { id: params.statementTxId },
      data: {
        status: "MATCHED",
        confidence: params.confidence,
        reconciliationRunId: params.runId,
      },
    });

    await prisma.transaction.update({
      where: { id: params.ledgerTxId },
      data: {
        status: "MATCHED",
        confidence: params.confidence,
        reconciliationRunId: params.runId,
      },
    });
  }
}
