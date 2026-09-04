import fs from "fs";
import path from "path";
import { prisma } from "../server/src/config/database.js";
import { UploadService } from "../server/src/services/uploadService.js";
import { ReconciliationService } from "../server/src/services/reconciliationService.js";
import { hashPassword } from "../server/src/utils/security.js";

async function main() {
  console.log("==================================================================");
  console.log("  LEDGER CONTROL — DATASET SEEDING & INGESTION PIPELINE");
  console.log("==================================================================");

  // 1. Transaction: Ensure Demo Tenant & Admin User
  const demoEmail = "admin@ledgercontrol.com";
  const demoPassword = "Password123!";
  const orgName = "Acme Financial Corp";
  const orgSlug = "acme-financial-corp";

  let organization = await prisma.organization.findUnique({
    where: { slug: orgSlug },
  });

  let user = await prisma.user.findUnique({
    where: { email: demoEmail },
  });

  if (!organization || !user) {
    console.log("[Seed] Seeding initial organization and admin user...");
    const hashedPassword = await hashPassword(demoPassword);

    await prisma.$transaction(async (tx) => {
      organization = await tx.organization.upsert({
        where: { slug: orgSlug },
        update: { name: orgName },
        create: { name: orgName, slug: orgSlug },
      });

      user = await tx.user.upsert({
        where: { email: demoEmail },
        update: { fullName: "Alex Mercer (Admin)", isActive: true },
        create: {
          email: demoEmail,
          passwordHash: hashedPassword,
          fullName: "Alex Mercer (Admin)",
          isActive: true,
        },
      });

      const existingMember = await tx.membership.findFirst({
        where: { userId: user.id, organizationId: organization.id },
      });

      if (!existingMember) {
        await tx.membership.create({
          data: {
            userId: user.id,
            organizationId: organization.id,
            role: "admin",
          },
        });
      }
    });
  }

  const activeOrg = organization!;
  const activeUser = user!;

  console.log(`[Seed] Active Tenant: ${activeOrg.name} (${activeOrg.id})`);
  console.log(`[Seed] Admin User:   ${activeUser.email} (${activeUser.id})`);

  // 2. Validate Raw Files Existence
  const rawStmtPath = path.resolve("data/raw/statement_data.csv");
  const rawLedgerPath = path.resolve("data/raw/ledger_data.csv");

  if (!fs.existsSync(rawStmtPath) || !fs.existsSync(rawLedgerPath)) {
    throw new Error("Raw dataset files missing in data/raw/");
  }

  // Copy raw files to processed directory
  const processedStmtPath = path.resolve("data/processed/statement_data_processed.csv");
  const processedLedgerPath = path.resolve("data/processed/ledger_data_processed.csv");

  fs.copyFileSync(rawStmtPath, processedStmtPath);
  fs.copyFileSync(rawLedgerPath, processedLedgerPath);

  // Copy to server storage directory
  const storageDir = path.resolve("server/storage/uploads");
  if (!fs.existsSync(storageDir)) {
    fs.mkdirSync(storageDir, { recursive: true });
  }

  const serverStmtPath = path.join(storageDir, "statement_seed.csv");
  const serverLedgerPath = path.join(storageDir, "ledger_seed.csv");
  fs.copyFileSync(processedStmtPath, serverStmtPath);
  fs.copyFileSync(processedLedgerPath, serverLedgerPath);

  // 3. Process Bank Statement CSV
  console.log("\n[Seed] Processing Bank Statement Dataset...");
  const stmtUpload = await UploadService.processCsvUpload({
    filePath: serverStmtPath,
    filename: "statement_data.csv",
    uploadType: "statement",
    organizationId: activeOrg.id,
    userId: activeUser.id,
  });
  console.log(`[+] Statement Upload ID: ${stmtUpload.upload_id} (Parsed Rows: ${stmtUpload.row_count})`);

  // 4. Process Gateway Ledger CSV
  console.log("\n[Seed] Processing Gateway / Ledger Dataset...");
  const ledgerUpload = await UploadService.processCsvUpload({
    filePath: serverLedgerPath,
    filename: "ledger_data.csv",
    uploadType: "ledger",
    organizationId: activeOrg.id,
    userId: activeUser.id,
  });
  console.log(`[+] Ledger Upload ID: ${ledgerUpload.upload_id} (Parsed Rows: ${ledgerUpload.row_count})`);

  // 5. Execute Two-Pass Reconciliation Engine
  console.log("\n[Seed] Running Two-Pass Reconciliation Engine...");
  const run = await ReconciliationService.startRun({
    statementUploadId: stmtUpload.upload_id,
    ledgerUploadId: ledgerUpload.upload_id,
    organizationId: activeOrg.id,
    userId: activeUser.id,
  });

  // Poll until run completes
  let finalRun = await ReconciliationService.getRunSummary(run.id, activeOrg.id);
  let retries = 0;
  while ((finalRun.status === "pending" || finalRun.status === "processing") && retries < 10) {
    await new Promise((r) => setTimeout(r, 500));
    finalRun = await ReconciliationService.getRunSummary(run.id, activeOrg.id);
    retries++;
  }

  console.log("==================================================================");
  console.log("  SEEDING & RECONCILIATION COMPLETE");
  console.log("==================================================================");
  console.log(`  Run ID           : ${finalRun.id}`);
  console.log(`  Status           : ${finalRun.status}`);
  console.log(`  Total Batched    : ${finalRun.summary.total} transactions`);
  console.log(`  Auto-Matched     : ${finalRun.summary.matched} pairs (${finalRun.summary.matched * 2} txs)`);
  console.log(`  Exceptions       : ${finalRun.summary.exceptions} discrepancies`);
  console.log(`  Reconciled Value : $${finalRun.summary.matched_value.toFixed(2)} USD`);
  console.log("==================================================================");
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("❌ Seeding Failed:", err);
    process.exit(1);
  });
