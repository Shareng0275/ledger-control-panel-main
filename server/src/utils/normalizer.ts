import crypto from "crypto";

export class Normalizer {
  /**
   * Parse various date strings into standard UTC Date objects.
   */
  static normalizeDate(rawDate: string | Date | null | undefined): Date {
    if (!rawDate) throw new Error("Empty date string provided.");
    if (rawDate instanceof Date) return isNaN(rawDate.getTime()) ? new Date() : rawDate;

    const trimmed = String(rawDate).trim();
    if (!trimmed) throw new Error("Empty date string provided.");

    // YYYY-MM-DD
    const isoMatch = /^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:T.*)?$/.exec(trimmed);
    if (isoMatch) {
      const year = parseInt(isoMatch[1], 10);
      const month = parseInt(isoMatch[2], 10) - 1;
      const day = parseInt(isoMatch[3], 10);
      return new Date(Date.UTC(year, month, day));
    }

    // MM/DD/YYYY or DD/MM/YYYY
    const slashMatch = /^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$/.exec(trimmed);
    if (slashMatch) {
      const p1 = parseInt(slashMatch[1], 10);
      const p2 = parseInt(slashMatch[2], 10);
      const year = parseInt(slashMatch[3], 10);

      // If p1 > 12, it must be DD/MM/YYYY
      if (p1 > 12) {
        return new Date(Date.UTC(year, p2 - 1, p1));
      }
      // Otherwise default to MM/DD/YYYY
      return new Date(Date.UTC(year, p1 - 1, p2));
    }

    // Direct ISO or standard parse fallback
    const parsed = new Date(trimmed);
    if (!isNaN(parsed.getTime())) {
      return parsed;
    }

    throw new Error(`Unable to parse date format: '${trimmed}'`);
  }

  /**
   * Parse amounts supporting currency symbols, thousand commas, negative parentheses, and Debit/Credit columns.
   */
  static normalizeAmount(
    rawAmount?: string | number | null,
    rawDebit?: string | number | null,
    rawCredit?: string | number | null,
  ): number {
    // 1. Separate Debit & Credit columns
    if (rawDebit !== undefined && rawDebit !== null && String(rawDebit).trim() !== "") {
      const dr = this.cleanNumericString(String(rawDebit));
      return -Math.abs(dr);
    }
    if (rawCredit !== undefined && rawCredit !== null && String(rawCredit).trim() !== "") {
      const cr = this.cleanNumericString(String(rawCredit));
      return Math.abs(cr);
    }

    if (rawAmount === undefined || rawAmount === null) {
      throw new Error("Empty monetary amount provided.");
    }

    const str = String(rawAmount).trim();
    if (!str) throw new Error("Empty monetary amount string.");

    return this.cleanNumericString(str);
  }

  private static cleanNumericString(val: string): number {
    let clean = val.trim();
    let isNegative = false;

    // Handle parentheses negatives: (500.00) -> -500.00
    if (clean.startsWith("(") && clean.endsWith(")")) {
      isNegative = true;
      clean = clean.slice(1, -1).trim();
    } else if (clean.endsWith("-")) {
      isNegative = true;
      clean = clean.slice(0, -1).trim();
    } else if (clean.startsWith("-")) {
      isNegative = true;
      clean = clean.slice(1).trim();
    }

    // Remove currency symbols ($, €, £, ₹), thousand commas, and spaces
    clean = clean.replace(/[$€£₹,\s]/g, "");

    const num = parseFloat(clean);
    if (isNaN(num)) {
      throw new Error(`Cannot extract numeric amount from '${val}'`);
    }

    const finalNum = isNegative ? -Math.abs(num) : num;
    return Math.round(finalNum * 10000) / 10000;
  }

  /**
   * Normalize description for deterministic and fuzzy matching.
   */
  static normalizeDescription(rawDescription?: string | null): string {
    if (!rawDescription) return "";

    let desc = String(rawDescription).trim().toLowerCase();
    // Normalize multiple spaces/tabs to single space
    desc = desc.replace(/\s+/g, " ");
    // Remove noisy punctuation while retaining alphanumeric and hyphens
    desc = desc.replace(/[^\w\s-]/g, "");
    return desc.trim();
  }

  /**
   * Normalize external reference codes.
   */
  static normalizeReference(rawRef?: string | null): string | null {
    if (!rawRef) return null;
    const clean = String(rawRef).trim().toUpperCase();
    if (!clean || ["N/A", "NONE", "NULL", "-", "0"].includes(clean)) {
      return null;
    }
    return clean.replace(/\s+/g, "");
  }

  /**
   * Deterministic SHA-256 hash for deduplication and integrity check.
   */
  static computeTransactionHash(
    source: string,
    orgId: string,
    date: Date,
    amount: number,
    currency: string,
    rawDesc: string,
    rawRef?: string | null,
  ): string {
    const payload = `${source}|${orgId}|${date.toISOString()}|${amount.toFixed(4)}|${currency.toUpperCase()}|${this.normalizeDescription(rawDesc)}|${this.normalizeReference(rawRef) || ""}`;
    return crypto.createHash("sha256").update(payload).digest("hex");
  }
}
