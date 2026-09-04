import type { Request } from "express";

export type Role = "admin" | "manager" | "analyst" | "editor" | "viewer";

export interface AuthenticatedUser {
  id: string;
  email: string;
  fullName: string;
  organizationId?: string;
  role?: Role;
}

export interface AuthenticatedRequest extends Request {
  user?: AuthenticatedUser;
  organizationId?: string;
}

export interface NormalizedTransactionInput {
  date: Date;
  description: string;
  normalizedDescription: string;
  amount: number;
  currency: string;
  externalReference?: string | null;
  normalizedReference?: string | null;
  rawData?: Record<string, unknown>;
  transactionHash?: string;
}

export interface FuzzyScoreResult {
  overallConfidence: number;
  amountScore: number;
  dateScore: number;
  descriptionScore: number;
  referenceScore: number;
  explanation: string;
}

export interface MatchCandidate {
  statementTxId: string;
  ledgerTxId: string;
  confidence: number;
  method: "deterministic" | "fuzzy" | "manual";
  reason: string;
  scoreDetails?: Record<string, unknown>;
}

export interface ForecastPointResult {
  date: string;
  cash: number;
  projected?: number | null;
  lower?: number | null;
  upper?: number | null;
}

export interface ForecastAnalytics {
  netDailyDrift: number;
  historicalVolatility: number;
  historicalDataPoints: number;
}
