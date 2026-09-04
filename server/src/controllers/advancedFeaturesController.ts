import type { Response } from "express";
import { AdvancedFeaturesService } from "../services/advancedFeaturesService.js";
import type { AuthenticatedRequest } from "../types/index.js";

export class AdvancedFeaturesController {
  static async getPreferences(req: AuthenticatedRequest, res: Response): Promise<void> {
    const result = await AdvancedFeaturesService.getUserPreferences(req.user!.id, req.organizationId!);
    res.status(200).json(result);
  }

  static async updatePreferences(req: AuthenticatedRequest, res: Response): Promise<void> {
    const { theme, default_horizon, visible_kpis, dashboard_cards, email_alerts } = req.body || {};
    const result = await AdvancedFeaturesService.updateUserPreferences({
      userId: req.user!.id,
      organizationId: req.organizationId!,
      theme,
      defaultHorizon: default_horizon,
      visibleKpis: visible_kpis,
      dashboardCards: dashboard_cards,
      emailAlerts: email_alerts,
    });
    res.status(200).json(result);
  }

  static async getPredictiveAnomalies(req: AuthenticatedRequest, res: Response): Promise<void> {
    const { run_id } = req.query;
    const result = await AdvancedFeaturesService.runPredictiveAnomalyDetection({
      organizationId: req.organizationId!,
      runId: run_id ? String(run_id) : undefined,
    });
    res.status(200).json(result);
  }

  static async listScheduledReports(req: AuthenticatedRequest, res: Response): Promise<void> {
    const result = await AdvancedFeaturesService.listScheduledReports(req.organizationId!);
    res.status(200).json({ reports: result });
  }

  static async generateScheduledReport(req: AuthenticatedRequest, res: Response): Promise<void> {
    const { report_type, frequency } = req.body || {};
    const result = await AdvancedFeaturesService.triggerReportGeneration({
      organizationId: req.organizationId!,
      userId: req.user!.id,
      reportType: report_type,
      frequency,
    });
    res.status(201).json(result);
  }
}
