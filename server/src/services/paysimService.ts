import { openSqliteDb } from "../utils/sqliteDb.js";

export interface PaySimQueryOptions {
  page?: number;
  limit?: number;
  type?: string;
  isFraud?: boolean;
  minAmount?: number;
  maxAmount?: number;
  search?: string;
}

export class PaySimService {
  /**
   * Retrieves high-level dataset summary metrics and metrics by transaction type.
   */
  static getSummary() {
    const db = openSqliteDb();
    try {
      const overall = db.queryGet(
        `SELECT 
          COUNT(*) as totalTransactions,
          SUM(amount) as totalVolume,
          AVG(amount) as avgAmount,
          MAX(amount) as maxAmount,
          SUM(isFraud) as totalFraud,
          SUM(isFlaggedFraud) as totalFlaggedFraud
        FROM paysim_transactions`
      );

      const typeBreakdown = db.queryAll(
        `SELECT 
          type,
          COUNT(*) as count,
          SUM(amount) as volume,
          SUM(isFraud) as fraudCount
        FROM paysim_transactions
        GROUP BY type
        ORDER BY volume DESC`
      );

      const stepDistribution = db.queryAll(
        `SELECT 
          step,
          COUNT(*) as count,
          SUM(amount) as volume,
          SUM(isFraud) as fraudCount
        FROM paysim_transactions
        GROUP BY step
        ORDER BY step ASC
        LIMIT 24`
      );

      return {
        dataset: "PaySim Synthetic Mobile Money Transactions",
        source: "Kaggle (PaySim / PS_20174392719_1491204439457_log.csv)",
        totalTransactions: Number(overall.totalTransactions || 0),
        totalVolume: Number(overall.totalVolume || 0),
        avgAmount: Number(overall.avgAmount || 0),
        maxAmount: Number(overall.maxAmount || 0),
        totalFraudIncidents: Number(overall.totalFraud || 0),
        totalFlaggedFraudIncidents: Number(overall.totalFlaggedFraud || 0),
        fraudRatePercent: Number(
          ((overall.totalFraud / (overall.totalTransactions || 1)) * 100).toFixed(4)
        ),
        typeBreakdown: typeBreakdown.map((t) => ({
          type: t.type,
          count: Number(t.count),
          volume: Number(t.volume),
          fraudCount: Number(t.fraudCount),
        })),
        stepDistribution: stepDistribution.map((s) => ({
          step: Number(s.step),
          count: Number(s.count),
          volume: Number(s.volume),
          fraudCount: Number(s.fraudCount),
        })),
      };
    } finally {
      db.close();
    }
  }

  /**
   * Returns paginated, filtered transaction feed from the ingested PaySim dataset.
   */
  static getTransactions(options: PaySimQueryOptions = {}) {
    const db = openSqliteDb();
    try {
      const page = Math.max(1, options.page || 1);
      const limit = Math.min(100, Math.max(1, options.limit || 20));
      const offset = (page - 1) * limit;

      const conditions: string[] = [];
      const params: any[] = [];

      if (options.type) {
        conditions.push("type = ?");
        params.push(options.type.toUpperCase());
      }

      if (typeof options.isFraud === "boolean") {
        conditions.push("isFraud = ?");
        params.push(options.isFraud ? 1 : 0);
      }

      if (options.minAmount !== undefined && !isNaN(options.minAmount)) {
        conditions.push("amount >= ?");
        params.push(options.minAmount);
      }

      if (options.maxAmount !== undefined && !isNaN(options.maxAmount)) {
        conditions.push("amount <= ?");
        params.push(options.maxAmount);
      }

      if (options.search && options.search.trim()) {
        conditions.push("(nameOrig LIKE ? OR nameDest LIKE ?)");
        const term = `%${options.search.trim()}%`;
        params.push(term, term);
      }

      const whereClause = conditions.length ? `WHERE ${conditions.join(" AND ")}` : "";

      const countSql = `SELECT COUNT(*) as total FROM paysim_transactions ${whereClause}`;
      const countResult = db.queryGet(countSql, params);
      const total = Number(countResult?.total || 0);

      const dataSql = `
        SELECT 
          id,
          step,
          type,
          amount,
          nameOrig,
          oldbalanceOrg,
          newbalanceOrig,
          nameDest,
          oldbalanceDest,
          newbalanceDest,
          isFraud,
          isFlaggedFraud
        FROM paysim_transactions
        ${whereClause}
        ORDER BY id DESC
        LIMIT ? OFFSET ?
      `;

      const rows = db.queryAll(dataSql, [...params, limit, offset]);

      return {
        data: rows.map((r) => ({
          id: r.id,
          step: r.step,
          type: r.type,
          amount: Number(r.amount),
          originAccount: r.nameOrig,
          originOldBalance: Number(r.oldbalanceOrg),
          originNewBalance: Number(r.newbalanceOrig),
          destinationAccount: r.nameDest,
          destinationOldBalance: Number(r.oldbalanceDest),
          destinationNewBalance: Number(r.newbalanceDest),
          isFraud: Boolean(r.isFraud),
          isFlaggedFraud: Boolean(r.isFlaggedFraud),
          discrepancyFlag:
            r.isFraud || r.oldbalanceOrg - r.amount !== r.newbalanceOrig
              ? "ANOMALOUS_BALANCE_DELTA"
              : "MATCHED",
        })),
        meta: {
          page,
          limit,
          total,
          totalPages: Math.ceil(total / limit),
        },
      };
    } finally {
      db.close();
    }
  }

  /**
   * Isolation analysis of fraud incidents and origin balance breaks.
   */
  static getFraudAnalysis() {
    const db = openSqliteDb();
    try {
      const fraudRows = db.queryAll(
        `SELECT 
          id,
          step,
          type,
          amount,
          nameOrig,
          oldbalanceOrg,
          newbalanceOrig,
          nameDest,
          isFraud,
          isFlaggedFraud
        FROM paysim_transactions
        WHERE isFraud = 1
        ORDER BY amount DESC
        LIMIT 50`
      );

      const totalFraudVolume = fraudRows.reduce((acc, r) => acc + Number(r.amount), 0);

      return {
        totalFraudSampled: fraudRows.length,
        totalFraudVolume,
        topHighRiskTransactions: fraudRows.map((r) => ({
          id: r.id,
          step: r.step,
          type: r.type,
          amount: Number(r.amount),
          originAccount: r.nameOrig,
          destinationAccount: r.nameDest,
          drainedBalance: Number(r.oldbalanceOrg),
          remainingBalance: Number(r.newbalanceOrig),
          riskScore: 0.99,
          classification: "SYNTHETIC_CASH_DRAIN_FRAUD",
        })),
      };
    } finally {
      db.close();
    }
  }
}
