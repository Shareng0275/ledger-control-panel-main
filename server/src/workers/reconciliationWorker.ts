import { Worker } from "bullmq";
import { getRedisConnection } from "../config/redis.js";
import { ReconciliationEngine } from "../reconciliation/reconciliationEngine.js";

export function startReconciliationWorker(): Worker | null {
  const redis = getRedisConnection();
  if (!redis) {
    console.log("[Worker] Redis unavailable; in-process async worker active.");
    return null;
  }

  try {
    const worker = new Worker(
      "reconciliation-jobs",
      async (job) => {
        const { runId, organizationId, userId } = job.data;
        console.log(`[Worker] Processing reconciliation job ${job.id} for run ${runId}`);
        await ReconciliationEngine.executeRun(runId, organizationId, userId);
      },
      { connection: redis, concurrency: 2 },
    );

    worker.on("completed", (job) => {
      console.log(`[Worker] Job ${job.id} completed successfully.`);
    });

    worker.on("failed", (job, err) => {
      console.error(`[Worker] Job ${job?.id} failed:`, err);
    });

    return worker;
  } catch (err) {
    console.warn("[Worker] Worker initialization error:", err);
    return null;
  }
}
