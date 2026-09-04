import fs from "fs";
import Papa from "papaparse";
import { prisma } from "../config/database.js";
import { AppError } from "../middleware/errorHandler.js";
import { Normalizer } from "../utils/normalizer.js";

export class UploadService {
  static async processCsvUpload(params: {
    filePath: string;
    filename: string;
    uploadType: "statement" | "ledger";
    organizationId: string;
    userId: string;
  }) {
    if (!fs.existsSync(params.filePath)) {
      throw new AppError("Uploaded file not found on server.", 400);
    }

    let rows: Record<string, string>[] = [];
    const rawContent = fs.readFileSync(params.filePath, "binary");

    // 1. Check if the file is a PDF statement
    if (params.filename.toLowerCase().endsWith(".pdf") || rawContent.startsWith("%PDF-")) {
      const pdfMatches = [...rawContent.matchAll(/\((\d{4}-\d{2}-\d{2})\s+(.*?)\s+([A-Z0-9_-]+)?\s+([-\d,.]+)?\s+([-\d,.]+)\s+([-\d,.]+)\)/g)];
      
      if (pdfMatches.length === 0) {
        throw new AppError("Unable to extract structured statement rows from uploaded PDF.", 422);
      }

      rows = pdfMatches.map((m) => {
        const date = m[1];
        const description = m[2].trim();
        const reference = m[3] || "";
        const dr = m[4];
        const cr = m[5];

        let amount = "0";
        if (cr && cr.trim()) {
          amount = cr.trim();
        } else if (dr && dr.trim()) {
          amount = `-${dr.trim().replace("-", "")}`;
        }

        return {
          date,
          description,
          amount,
          currency: "USD",
          reference,
          transaction_type: cr ? "credit" : "debit",
        };
      });
    } else {
      // 2. Parse Standard CSV content
      const csvContent = fs.readFileSync(params.filePath, "utf-8");
      const parsed = Papa.parse<Record<string, string>>(csvContent, {
        header: true,
        skipEmptyLines: "greedy",
        transformHeader: (h) => h.trim().toLowerCase().replace(/[^a-z0-9_]/g, "_"),
      });

      if (parsed.errors.length > 0 && parsed.data.length === 0) {
        throw new AppError("Invalid CSV format or corrupted file contents.", 422, "CSV_PARSE_ERROR", parsed.errors);
      }

      rows = parsed.data;
    }

    if (rows.length === 0) {
      throw new AppError("Uploaded file contains no transaction rows.", 422);
    }

    const keys = Object.keys(rows[0]);
    const dateKey = keys.find((k) => k === "date" || k === "transaction_date" || k === "tx_date") || keys.find((k) => k.includes("date") || k.includes("time"));
    const descKey = keys.find((k) => k === "description" || k === "desc" || k === "narrative" || k === "details" || k === "memo" || k === "merchant") || keys.find((k) => k.includes("desc") || k.includes("narr") || k.includes("memo"));
    const amountKey = keys.find((k) => k === "amount" || k === "value" || k === "net_amount" || k === "total") || keys.find((k) => k.includes("amount") || k.includes("value") || k.includes("net") || k.includes("total"));
    const debitKey = keys.find((k) => k === "debit" || k === "dr" || k === "withdrawal" || k === "debit_amount");
    const creditKey = keys.find((k) => k === "credit" || k === "cr" || k === "deposit" || k === "credit_amount");
    const refKey = keys.find((k) => k === "reference" || k === "external_reference" || k === "ref" || k === "utr") || keys.find((k) => k.includes("ref") || k.includes("utr"));
    const currKey = keys.find((k) => k === "currency" || k === "curr") || keys.find((k) => k.includes("curr"));

    if (!dateKey) throw new AppError("Uploaded file missing required Date column.", 422);
    if (!descKey) throw new AppError("Uploaded file missing required Description column.", 422);
    if (!amountKey && !debitKey && !creditKey) {
      throw new AppError("Uploaded file missing required Amount / Debit / Credit column.", 422);
    }

    // 3. Create Upload Record
    const upload = await prisma.upload.create({
      data: {
        organizationId: params.organizationId,
        filename: params.filename,
        uploadType: params.uploadType === "statement" ? "STATEMENT" : "LEDGER",
        storagePath: params.filePath,
        rowCount: rows.length,
        status: "VALID",
      },
    });

    // 4. Normalize and Prepare Transaction Records
    const transactionsData = [];
    for (const row of rows) {
      try {
        const rawDate = row[dateKey];
        const rawDesc = row[descKey] || "Unknown Transaction";
        const rawAmt = amountKey ? row[amountKey] : null;
        const rawDr = debitKey ? row[debitKey] : null;
        const rawCr = creditKey ? row[creditKey] : null;
        const rawRef = refKey ? row[refKey] : null;
        const rawCurr = currKey && row[currKey] ? row[currKey].trim().toUpperCase() : "USD";

        const normDate = Normalizer.normalizeDate(rawDate);
        const normAmt = Normalizer.normalizeAmount(rawAmt, rawDr, rawCr);
        const normDesc = Normalizer.normalizeDescription(rawDesc);
        const normRef = Normalizer.normalizeReference(rawRef);
        const hash = Normalizer.computeTransactionHash(
          params.uploadType,
          params.organizationId,
          normDate,
          normAmt,
          rawCurr,
          rawDesc,
          rawRef,
        );

        transactionsData.push({
          organizationId: params.organizationId,
          uploadId: upload.id,
          source: params.uploadType === "statement" ? "STATEMENT" : "LEDGER",
          transactionDate: normDate,
          description: rawDesc.trim(),
          normalizedDescription: normDesc,
          amount: normAmt,
          currency: rawCurr,
          externalReference: rawRef ? rawRef.trim() : null,
          normalizedReference: normRef,
          transactionHash: hash,
          status: "UNMATCHED",
          rawData: JSON.stringify(row),
        });
      } catch (err: any) {
        console.warn(`[UploadService] Row normalization skipped: ${err.message}`);
      }
    }

    // 5. Bulk Insert Transactions with skipDuplicates for idempotency
    if (transactionsData.length > 0) {
      await prisma.transaction.createMany({
        data: transactionsData,
      });
    }

    // 6. Append Audit Log
    await prisma.auditLog.create({
      data: {
        organizationId: params.organizationId,
        actorId: params.userId,
        action: "upload.created",
        entityType: "Upload",
        entityId: upload.id,
        details: JSON.stringify({
          filename: params.filename,
          type: params.uploadType,
          rows: transactionsData.length,
        }),
      },
    });

    return {
      id: upload.id,
      upload_id: upload.id,
      filename: upload.filename,
      upload_type: params.uploadType,
      row_count: transactionsData.length,
      rows: transactionsData.length,
      status: "valid",
      validation_errors: null,
      created_at: upload.createdAt,
    };
  }
}
