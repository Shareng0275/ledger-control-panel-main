import { config } from "../config/index.js";
import type { FuzzyScoreResult } from "../types/index.js";

export class FuzzyMatcher {
  /**
   * Levenshtein Distance similarity ratio (0.0 to 1.0).
   */
  static levenshteinRatio(s1: string, s2: string): number {
    if (s1 === s2) return 1.0;
    if (!s1 || !s2) return 0.0;

    const len1 = s1.length;
    const len2 = s2.length;
    const matrix: number[][] = [];

    for (let i = 0; i <= len1; i++) {
      matrix[i] = [i];
    }
    for (let j = 0; j <= len2; j++) {
      matrix[0][j] = j;
    }

    for (let i = 1; i <= len1; i++) {
      for (let j = 1; j <= len2; j++) {
        const cost = s1[i - 1] === s2[j - 1] ? 0 : 1;
        matrix[i][j] = Math.min(
          matrix[i - 1][j] + 1,
          matrix[i][j - 1] + 1,
          matrix[i - 1][j - 1] + cost,
        );
      }
    }

    const dist = matrix[len1][len2];
    const maxLen = Math.max(len1, len2);
    return maxLen === 0 ? 1.0 : Math.max(0.0, 1.0 - dist / maxLen);
  }

  /**
   * Token Set / Jaccard similarity between words in descriptions.
   */
  static tokenSimilarity(s1: string, s2: string): number {
    const tokens1 = new Set(s1.toLowerCase().split(/\s+/).filter(Boolean));
    const tokens2 = new Set(s2.toLowerCase().split(/\s+/).filter(Boolean));

    if (tokens1.size === 0 && tokens2.size === 0) return 1.0;
    if (tokens1.size === 0 || tokens2.size === 0) return 0.0;

    let intersection = 0;
    tokens1.forEach((t) => {
      if (tokens2.has(t)) intersection++;
    });

    const union = new Set([...tokens1, ...tokens2]).size;
    return union === 0 ? 1.0 : intersection / union;
  }

  /**
   * Compute monetary amount similarity with small variance / fee tolerance.
   */
  static computeAmountScore(amt1: number, amt2: number): { score: number; explanation: string } {
    if (amt1 === amt2) {
      return { score: 1.0, explanation: "Amount matches exactly (100%)" };
    }

    // Opposite signs cannot match
    if ((amt1 > 0 && amt2 < 0) || (amt1 < 0 && amt2 > 0)) {
      return { score: 0.0, explanation: "Amount sign mismatch (0%)" };
    }

    const abs1 = Math.abs(amt1);
    const abs2 = Math.abs(amt2);
    const maxAbs = Math.max(abs1, abs2);
    if (maxAbs === 0) return { score: 1.0, explanation: "Zero amount match (100%)" };

    const diff = Math.abs(abs1 - abs2);
    const pctDiff = diff / maxAbs;

    if (pctDiff <= config.FUZZY_MAX_AMOUNT_DIFF_PERCENT) {
      const score = Math.max(0.0, 1.0 - pctDiff * 4.0);
      return {
        score: Math.round(score * 10000) / 10000,
        explanation: `Amount variance of $${diff.toFixed(2)} (${(score * 100).toFixed(1)}%)`,
      };
    }

    return {
      score: 0.0,
      explanation: `Amount variance of $${diff.toFixed(2)} exceeds tolerance (0%)`,
    };
  }

  /**
   * Compute date proximity score.
   */
  static computeDateScore(d1: Date, d2: Date): { score: number; explanation: string } {
    const diffMs = Math.abs(d1.getTime() - d2.getTime());
    const deltaDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (deltaDays === 0) {
      return { score: 1.0, explanation: "Same transaction date (100%)" };
    } else if (deltaDays === 1) {
      return { score: 0.95, explanation: "Date differs by 1 day (95%)" };
    } else if (deltaDays === 2) {
      return { score: 0.9, explanation: "Date differs by 2 days (90%)" };
    } else if (deltaDays === 3) {
      return { score: 0.8, explanation: "Date differs by 3 days (80%)" };
    } else if (deltaDays <= config.FUZZY_MAX_DATE_DIFF_DAYS) {
      const score = Math.max(0.4, 1.0 - deltaDays * 0.09);
      return {
        score: Math.round(score * 10000) / 10000,
        explanation: `Date differs by ${deltaDays} days (${(score * 100).toFixed(1)}%)`,
      };
    }

    return {
      score: 0.0,
      explanation: `Date difference of ${deltaDays} days exceeds window (0%)`,
    };
  }

  /**
   * Compute normalized description similarity.
   */
  static computeDescriptionScore(desc1?: string | null, desc2?: string | null): { score: number; explanation: string } {
    if (!desc1 || !desc2) {
      return { score: 0.0, explanation: "Missing description" };
    }

    const d1 = desc1.trim().toLowerCase();
    const d2 = desc2.trim().toLowerCase();

    if (d1 === d2) {
      return { score: 1.0, explanation: "Description identical (100%)" };
    }

    const tokenSim = this.tokenSimilarity(d1, d2);
    const levSim = this.levenshteinRatio(d1, d2);

    // Blended score favoring token containment and substring overlap
    const combined = Math.max(tokenSim, levSim * 0.4 + tokenSim * 0.6);
    const score = Math.round(combined * 10000) / 10000;

    return {
      score,
      explanation: `Description similarity ${(score * 100).toFixed(1)}% ('${desc1}' ~ '${desc2}')`,
    };
  }

  /**
   * Compute external reference similarity.
   */
  static computeReferenceScore(ref1?: string | null, ref2?: string | null): { score: number; explanation: string | null } {
    if (!ref1 || !ref2) {
      return { score: 0.0, explanation: null };
    }

    const r1 = ref1.trim().toUpperCase();
    const r2 = ref2.trim().toUpperCase();

    if (r1 === r2) {
      return { score: 1.0, explanation: "Reference exact match (100%)" };
    }

    if (r1.includes(r2) || r2.includes(r1)) {
      return { score: 0.9, explanation: `Reference partial match (${r1} ~ ${r2})` };
    }

    const sim = this.levenshteinRatio(r1, r2);
    const score = Math.round(sim * 10000) / 10000;
    return { score, explanation: `Reference similarity ${(score * 100).toFixed(1)}%` };
  }

  /**
   * Compute overall explainable confidence score.
   */
  static scorePair(stmtTx: {
    amount: number;
    transactionDate: Date;
    normalizedDescription?: string | null;
    description: string;
    normalizedReference?: string | null;
    externalReference?: string | null;
  }, ledgerTx: {
    amount: number;
    transactionDate: Date;
    normalizedDescription?: string | null;
    description: string;
    normalizedReference?: string | null;
    externalReference?: string | null;
  }): FuzzyScoreResult {
    const amtResult = this.computeAmountScore(stmtTx.amount, ledgerTx.amount);
    const dateResult = this.computeDateScore(stmtTx.transactionDate, ledgerTx.transactionDate);
    const descResult = this.computeDescriptionScore(
      stmtTx.normalizedDescription || stmtTx.description,
      ledgerTx.normalizedDescription || ledgerTx.description,
    );
    const refResult = this.computeReferenceScore(
      stmtTx.normalizedReference || stmtTx.externalReference,
      ledgerTx.normalizedReference || ledgerTx.externalReference,
    );

    const wAmt = config.FUZZY_WEIGHT_AMOUNT;
    const wDesc = config.FUZZY_WEIGHT_DESCRIPTION;
    const wDate = config.FUZZY_WEIGHT_DATE;
    const wRef = config.FUZZY_WEIGHT_REFERENCE;

    let overall = 0;
    if (refResult.explanation !== null) {
      overall = amtResult.score * wAmt + descResult.score * wDesc + dateResult.score * wDate + refResult.score * wRef;
    } else {
      const totalW = wAmt + wDesc + wDate;
      overall = (amtResult.score * wAmt + descResult.score * wDesc + dateResult.score * wDate) / totalW;
    }

    const clamped = Math.min(1.0, Math.max(0.0, Math.round(overall * 10000) / 10000));
    const explanations = [amtResult.explanation, dateResult.explanation, descResult.explanation];
    if (refResult.explanation) explanations.push(refResult.explanation);

    return {
      overallConfidence: clamped,
      amountScore: amtResult.score,
      dateScore: dateResult.score,
      descriptionScore: descResult.score,
      referenceScore: refResult.score,
      explanation: `Confidence ${(clamped * 100).toFixed(1)}%: ${explanations.join("; ")}.`,
    };
  }
}
