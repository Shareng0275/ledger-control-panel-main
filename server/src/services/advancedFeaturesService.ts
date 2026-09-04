import { prisma } from "../config/database.js";
import { AppError } from "../middleware/errorHandler.js";

export class AdvancedFeaturesService {
  /**
   * 1. CUSTOM DASHBOARDS: Get or initialize user preferences
   */
  static async getUserPreferences(userId: string, organizationId: string) {
    let pref = await prisma.userPreference.findUnique({
      where: { userId },
    });

    if (!pref) {
      pref = await prisma.userPreference.create({
        data: {
          userId,
          organizationId,
          theme: "light",
          defaultHorizon: "30d",
          visibleKpis: JSON.stringify(["matched_rate", "total_value", "exception_count", "volatility"]),
          dashboardCards: JSON.stringify(["summary_donut", "confidence_histogram", "forecast_line", "recent_exceptions"]),
          emailAlerts: true,
        },
      });
    }

    return {
      user_id: pref.userId,
      theme: pref.theme,
      default_horizon: pref.defaultHorizon,
      visible_kpis: JSON.parse(pref.visibleKpis),
      dashboard_cards: JSON.parse(pref.dashboardCards),
      email_alerts: pref.emailAlerts,
    };
  }

  /**
   * 1. CUSTOM DASHBOARDS: Update user dashboard preferences
   */
  static async updateUserPreferences(params: {
    userId: string;
    organizationId: string;
    theme?: string;
    defaultHorizon?: string;
    visibleKpis?: string[];
    dashboardCards?: string[];
    emailAlerts?: boolean;
  }) {
    const updated = await prisma.userPreference.upsert({
      where: { userId: params.userId },
      create: {
        userId: params.userId,
        organizationId: params.organizationId,
        theme: params.theme || "light",
        defaultHorizon: params.defaultHorizon || "30d",
        visibleKpis: JSON.stringify(params.visibleKpis || ["matched_rate", "total_value", "exception_count"]),
        dashboardCards: JSON.stringify(params.dashboardCards || ["summary_donut", "forecast_line"]),
        emailAlerts: params.emailAlerts ?? true,
      },
      update: {
        theme: params.theme,
        defaultHorizon: params.defaultHorizon,
        visibleKpis: params.visibleKpis ? JSON.stringify(params.visibleKpis) : undefined,
        dashboardCards: params.dashboardCards ? JSON.stringify(params.dashboardCards) : undefined,
        emailAlerts: params.emailAlerts,
      },
    });

    await prisma.auditLog.create({
      data: {
        organizationId: params.organizationId,
        actorId: params.userId,
        action: "preferences.update",
        entityType: "UserPreference",
        entityId: updated.id,
        details: JSON.stringify({ default_horizon: updated.defaultHorizon, theme: updated.theme }),
      },
    });

    return {
      user_id: updated.userId,
      theme: updated.theme,
      default_horizon: updated.defaultHorizon,
      visible_kpis: JSON.parse(updated.visibleKpis),
      dashboard_cards: JSON.parse(updated.dashboardCards),
      email_alerts: updated.emailAlerts,
    };
  }

  /**
   * 2 & 3. PREDICTIVE ANOMALY DETECTION & AI INSIGHTS
   * Grounded explainable pipeline: Real Historical Data -> Feature Extraction -> Statistical Anomaly Detection -> Risk Score -> Alert
   */
  static async runPredictiveAnomalyDetection(params: {
    organizationId: string;
    runId?: string;
  }) {
    const whereTx: any = { organizationId: params.organizationId };
    if (params.runId) whereTx.reconciliationRunId = params.runId;

    const transactions = await prisma.transaction.findMany({
      where: whereTx,
      orderBy: { transactionDate: "desc" },
      take: 200,
    });

    if (transactions.length === 0) {
      return {
        anomaly_count: 0,
        risk_score: 0.0,
        anomalies: [],
        summary: "No transactions available in current organization context.",
      };
    }

    // Feature extraction: Absolute amount distribution
    const amounts = transactions.map((t) => Math.abs(Number(t.amount)));
    const mean = amounts.reduce((a, b) => a + b, 0) / amounts.length;
    const variance = amounts.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / amounts.length;
    const stdDev = Math.sqrt(variance) || 1;

    const anomalies: any[] = [];

    for (const tx of transactions) {
      const absAmt = Math.abs(Number(tx.amount));
      const zScore = (absAmt - mean) / stdDev;

      // Anomaly trigger: Z-score > 2.0 (Top statistical deviation)
      if (zScore > 2.0) {
        const severity = zScore > 3.5 ? "CRITICAL" : zScore > 2.5 ? "HIGH" : "MEDIUM";
        const riskScore = Math.min(1.0, Math.round((zScore / 4.0) * 100) / 100);

        anomalies.push({
          id: `anomaly-${tx.id.slice(0, 8)}`,
          transaction_id: tx.id,
          date: tx.transactionDate.toISOString().slice(0, 10),
          amount: absAmt,
          description: tx.description,
          source: tx.source.toLowerCase(),
          status: tx.status.toLowerCase(),
          z_score: Math.round(zScore * 100) / 100,
          severity,
          risk_score: riskScore,
          explanation: `Statistical outlier detected: amount $${absAmt.toLocaleString()} is ${zScore.toFixed(1)} standard deviations from sample mean ($${mean.toFixed(2)}).`,
          suggested_action: severity === "CRITICAL" ? "Escalate to Manager for immediate review" : "Verify invoice attachment and reclassify",
          human_review_required: true,
        });
      }
    }

    const overallRisk = anomalies.length > 0 ? Math.max(...anomalies.map((a) => a.risk_score)) : 0.05;

    return {
      anomaly_count: anomalies.length,
      overall_risk_score: overallRisk,
      posture: overallRisk > 0.75 ? "CRITICAL_ATTENTION_REQUIRED" : overallRisk > 0.4 ? "ELEVATED_WATCH" : "STABLE",
      anomalies,
      sample_size: transactions.length,
      mean_amount: Math.round(mean * 100) / 100,
      std_dev: Math.round(stdDev * 100) / 100,
    };
  }

  /**
   * 4. AUTOMATED SCHEDULED REPORTING: List scheduled reports
   */
  static async listScheduledReports(organizationId: string) {
    return prisma.scheduledReport.findMany({
      where: { organizationId },
      orderBy: { createdAt: "desc" },
    });
  }

  /**
   * 4. AUTOMATED SCHEDULED REPORTING: Trigger report generation job
   */
  static async triggerReportGeneration(params: {
    organizationId: string;
    userId: string;
    reportType?: string;
    frequency?: string;
  }) {
    const reportType = params.reportType || "DAILY_RECONCILIATION";
    const title = `${reportType.replace(/_/g, " ")} Summary (${new Date().toISOString().slice(0, 10)})`;

    // Retrieve real scoped metrics
    const [totalCount, matchedCount, exceptionsCount] = await Promise.all([
      prisma.transaction.count({ where: { organizationId: params.organizationId } }),
      prisma.transaction.count({ where: { organizationId: params.organizationId, status: "MATCHED" } }),
      prisma.exception.count({ where: { organizationId: params.organizationId } }),
    ]);

    const payload = JSON.stringify({
      generated_at: new Date().toISOString(),
      organization_id: params.organizationId,
      total_transactions: totalCount,
      matched_count: matchedCount,
      exceptions_count: exceptionsCount,
      match_rate: totalCount > 0 ? `${((matchedCount / totalCount) * 100).toFixed(1)}%` : "N/A",
    });

    const report = await prisma.scheduledReport.create({
      data: {
        organizationId: params.organizationId,
        title,
        reportType,
        frequency: params.frequency || "DAILY",
        format: "JSON_CSV",
        status: "COMPLETED",
        payload,
        lastRunAt: new Date(),
        nextRunAt: new Date(Date.now() + 86400000), // Next run in 24 hours
      },
    });

    // Audit Report Generation
    await prisma.auditLog.create({
      data: {
        organizationId: params.organizationId,
        actorId: params.userId,
        action: "report.generated",
        entityType: "ScheduledReport",
        entityId: report.id,
        details: JSON.stringify({ title, report_type: reportType }),
      },
    });

    return report;
  }
}
