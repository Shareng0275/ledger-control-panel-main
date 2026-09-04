import { Queue } from "bullmq";
import { getRedisConnection } from "../config/redis.js";
import { ReconciliationEngine } from "../reconciliation/reconciliationEngine.js";

let reconciliationQueue: Queue | null = null;

export function getReconciliationQueue(): Queue | null {
  const redis = getRedisConnection();
  if (!redis) return null;

  if (!reconciliationQueue) {
    try {
      reconciliationQueue = new Queue("reconciliation-jobs", {
        connection: redis,
        defaultJobOptions: {
          attempts: 2,
          backoff: { type: "exponential", delay: 1000 },
          removeOnComplete: true,
          removeOnFail: false,
        },
      });
    } catch {
      reconciliationQueue = null;
    }
  }

  return reconciliationQueue;
}

export async function dispatchReconciliationJob(params: {
  runId: string;
  organizationId: string;
  userId: string;
}): Promise<void> {
  const queue = getReconciliationQueue();

  if (queue) {
    try {
      await queue.add("run-reconciliation", params);
      console.log(`[Queue] Dispatched reconciliation job ${params.runId} to BullMQ.`);
      return;
    } catch (err) {
      console.warn("⚠️ BullMQ dispatch failed, falling back to background worker process:", err);
    }
  }

  // Graceful in-process async execution fallback
  setImmediate(() => {
    ReconciliationEngine.executeRun(params.runId, params.organizationId, params.userId).catch((err) => {
      console.error(`[In-Process Job Error] Run ${params.runId}:`, err);
    });
  });
}
