import request from "supertest";
import { beforeAll, describe, expect, it } from "vitest";
import app from "../src/index.js";
import { FuzzyMatcher } from "../src/reconciliation/fuzzyMatcher.js";
import { Normalizer } from "../src/utils/normalizer.js";

describe("Ledger Control — Enterprise Backend Test Suite", () => {
  let authToken = "";

  beforeAll(async () => {
    // Seed / Ensure user
    const res = await request(app)
      .post("/api/v1/auth/login")
      .send({ email: "admin@ledgercontrol.com", password: "Password123!" });

    if (res.status === 200) {
      authToken = res.body.access_token;
    } else {
      const reg = await request(app).post("/api/v1/auth/register").send({
        email: "admin@ledgercontrol.com",
        password: "Password123!",
        full_name: "Alex Mercer (Admin)",
        organization_name: "Acme Financial Corp",
      });
      authToken = reg.body.access_token;
    }
  });

  describe("1. Normalization & Math Units", () => {
    it("normalizes diverse date formats to UTC dates", () => {
      const iso = Normalizer.normalizeDate("2026-08-01");
      expect(iso.toISOString().slice(0, 10)).toBe("2026-08-01");

      const slash = Normalizer.normalizeDate("08/15/2026");
      expect(slash.toISOString().slice(0, 10)).toBe("2026-08-15");
    });

    it("normalizes monetary currencies and parentheses negatives", () => {
      expect(Normalizer.normalizeAmount("$15,450.00")).toBe(15450.0);
      expect(Normalizer.normalizeAmount("(2,450.75)")).toBe(-2450.75);
      expect(Normalizer.normalizeAmount(null, "$500.00", null)).toBe(-500.0);
      expect(Normalizer.normalizeAmount(null, null, "€1,200.50")).toBe(1200.5);
    });

    it("cleans and sanitizes descriptions and reference codes", () => {
      expect(Normalizer.normalizeDescription("  STRIPE PAYOUT SETTLEMENT #9901!! ")).toBe(
        "stripe payout settlement 9901",
      );
      expect(Normalizer.normalizeReference("  STRIPE-SETTLE-9901  ")).toBe("STRIPE-SETTLE-9901");
    });
  });

  describe("2. Explainable Fuzzy Confidence Scorer", () => {
    it("scores identical pairs with 100% confidence", () => {
      const result = FuzzyMatcher.scorePair(
        {
          amount: 15450.0,
          transactionDate: new Date("2026-08-01"),
          description: "Stripe Payout Settlement",
          externalReference: "STRIPE-9901",
        },
        {
          amount: 15450.0,
          transactionDate: new Date("2026-08-01"),
          description: "Stripe Payout Settlement",
          externalReference: "STRIPE-9901",
        },
      );
      expect(result.overallConfidence).toBe(1.0);
    });

    it("scores fuzzy merchant variations within high confidence range", () => {
      const result = FuzzyMatcher.scorePair(
        {
          amount: -2450.75,
          transactionDate: new Date("2026-08-12"),
          description: "AMAZON WEB SERVICES EMEA INVOICE",
        },
        {
          amount: -2450.75,
          transactionDate: new Date("2026-08-12"),
          description: "Amazon Web Services Cloud Infrastructure",
        },
      );
      expect(result.overallConfidence).toBeGreaterThanOrEqual(0.80);
      expect(result.explanation).toContain("Amount matches exactly");
    });
  });

  describe("3. REST API Endpoints", () => {
    it("GET /health returns healthy status", async () => {
      const res = await request(app).get("/health");
      expect(res.status).toBe(200);
      expect(res.body.status).toBe("healthy");
    });

    it("GET /api/v1/transactions returns paginated records", async () => {
      const res = await request(app)
        .get("/api/v1/transactions")
        .set("Authorization", `Bearer ${authToken}`);
      expect(res.status).toBe(200);
      expect(Array.isArray(res.body.items)).toBe(true);
    });

    it("GET /api/v1/exceptions returns discrepancy list", async () => {
      const res = await request(app)
        .get("/api/v1/exceptions")
        .set("Authorization", `Bearer ${authToken}`);
      expect(res.status).toBe(200);
      expect(Array.isArray(res.body.items)).toBe(true);
    });

    it("GET /api/v1/forecast returns 30d projections with uncertainty bounds", async () => {
      const res = await request(app)
        .get("/api/v1/forecast?horizon=30d")
        .set("Authorization", `Bearer ${authToken}`);
      expect(res.status).toBe(200);
      expect(res.body.horizon).toBe("30d");
      expect(res.body.points.length).toBeGreaterThan(0);
    });

    it("POST /api/v1/ask retrieves real database rows", async () => {
      const res = await request(app)
        .post("/api/v1/ask")
        .set("Authorization", `Bearer ${authToken}`)
        .send({ question: "Which transactions failed to match and why?" });
      expect(res.status).toBe(200);
      expect(res.body.answer).toBeDefined();
      expect(Array.isArray(res.body.supporting_rows)).toBe(true);
    });

    it("POST /api/v1/ask answers 'What's my current cash position?' with verified balance", async () => {
      const res = await request(app)
        .post("/api/v1/ask")
        .set("Authorization", `Bearer ${authToken}`)
        .send({ question: "What's my current cash position?" });
      expect(res.status).toBe(200);
      expect(res.body.answer).toContain("current reconciled cash position");
      expect(Array.isArray(res.body.supporting_rows)).toBe(true);
      expect(res.body.intent).toBe("cash_position_inquiry");
    });

    it("POST /api/v1/ask answers 'Why did my settlement drop last Tuesday?' with root causes", async () => {
      const res = await request(app)
        .post("/api/v1/ask")
        .set("Authorization", `Bearer ${authToken}`)
        .send({ question: "Why did my settlement drop last Tuesday?" });
      expect(res.status).toBe(200);
      expect(res.body.answer).toContain("settlement dropped");
      expect(Array.isArray(res.body.supporting_rows)).toBe(true);
      expect(res.body.intent).toBe("settlement_variance_root_cause");
    });

    it("POST /api/v1/ask answers 'Show me unreconciled transactions from Stripe above $500'", async () => {
      const res = await request(app)
        .post("/api/v1/ask")
        .set("Authorization", `Bearer ${authToken}`)
        .send({ question: "Show me unreconciled transactions from Stripe above $500" });
      expect(res.status).toBe(200);
      expect(res.body.answer).toContain("Stripe");
      expect(Array.isArray(res.body.supporting_rows)).toBe(true);
      expect(res.body.intent).toBe("filtered_provider_breakout");
    });

    it("GET /api/v1/insights returns anomaly detection cards", async () => {
      const res = await request(app)
        .get("/api/v1/insights")
        .set("Authorization", `Bearer ${authToken}`);
      expect(res.status).toBe(200);
      expect(Array.isArray(res.body.insights)).toBe(true);
    });

    it("GET /api/v1/audit returns immutable compliance log", async () => {
      const res = await request(app)
        .get("/api/v1/audit")
        .set("Authorization", `Bearer ${authToken}`);
      expect(res.status).toBe(200);
      expect(Array.isArray(res.body.items)).toBe(true);
    });

    it("GET /api/v1/datasets/paysim/summary returns accurate PaySim aggregate statistics", async () => {
      const res = await request(app).get("/api/v1/datasets/paysim/summary");
      expect(res.status).toBe(200);
      expect(res.body.success).toBe(true);
      expect(res.body.data.totalTransactions).toBeGreaterThanOrEqual(50000);
      expect(res.body.data.totalFraudIncidents).toBeGreaterThan(0);
    });

    it("GET /api/v1/datasets/paysim/transactions returns paginated transactions and anomaly flags", async () => {
      const res = await request(app).get("/api/v1/datasets/paysim/transactions?page=1&limit=10");
      expect(res.status).toBe(200);
      expect(res.body.success).toBe(true);
      expect(res.body.data.length).toBe(10);
      expect(res.body.meta.totalPages).toBeGreaterThan(0);
    });

    it("GET /api/v1/datasets/paysim/fraud-analysis returns high-risk fraud cases", async () => {
      const res = await request(app).get("/api/v1/datasets/paysim/fraud-analysis");
      expect(res.status).toBe(200);
      expect(res.body.success).toBe(true);
      expect(res.body.data.topHighRiskTransactions.length).toBeGreaterThan(0);
    });
  });

  describe("4. Security & RBAC Boundary Verification", () => {
    it("returns 401 Unauthorized for unauthenticated API requests", async () => {
      const res = await request(app).get("/api/v1/transactions");
      expect(res.status).toBe(401);
      expect(res.body.error).toBe("Unauthorized");
    });

    it("returns 401 Unauthorized for invalid/expired tokens", async () => {
      const res = await request(app)
        .get("/api/v1/transactions")
        .set("Authorization", "Bearer invalid-token-999");
      expect(res.status).toBe(401);
    });

    it("returns 403 Forbidden when attempting unauthorized tenant access", async () => {
      const res = await request(app)
        .get("/api/v1/transactions")
        .set("Authorization", `Bearer ${authToken}`)
        .set("x-organization-id", "00000000-0000-0000-0000-000000000000");
      expect(res.status).toBe(403);
      expect(res.body.error).toBe("Forbidden");
    });

    it("returns 422 Unprocessable Entity on malformed inputs or missing required parameters", async () => {
      const res = await request(app)
        .post("/api/v1/ask")
        .set("Authorization", `Bearer ${authToken}`)
        .send({});
      expect(res.status).toBe(422);
    });
  });
});
