import type { Request, Response } from "express";
import { AiService } from "../services/aiService.js";
import { AuditService } from "../services/auditService.js";
import { ForecastService } from "../services/forecastService.js";
import type { AuthenticatedRequest } from "../types/index.js";

export class ForecastController {
  static async getForecast(req: AuthenticatedRequest, res: Response): Promise<void> {
    let raw = String(req.query.horizon || req.query.days || "30d").toLowerCase();
    let horizon: "7d" | "30d" | "90d" = "30d";
    if (raw.includes("7")) horizon = "7d";
    else if (raw.includes("90")) horizon = "90d";
    else horizon = "30d";

    const result = await ForecastService.getCashForecast({
      organizationId: req.organizationId!,
      horizon,
    });
    res.status(200).json(result);
  }
}

export class AiController {
  static async ask(req: AuthenticatedRequest, res: Response): Promise<void> {
    const question = req.body?.question;
    if (!question) {
      res.status(422).json({ error: "ValidationError", detail: "Field 'question' is required." });
      return;
    }

    const result = await AiService.askQuestion({
      question,
      organizationId: req.organizationId!,
      userId: req.user!.id,
    });

    res.status(200).json(result);
  }

  static async getInsights(req: AuthenticatedRequest, res: Response): Promise<void> {
    const { severity, run_id } = req.query;
    const result = await AiService.getInsights({
      organizationId: req.organizationId!,
      severity: severity ? String(severity) : undefined,
      runId: run_id ? String(run_id) : undefined,
    });
    res.status(200).json(result);
  }
}

export class AuditController {
  static async list(req: AuthenticatedRequest, res: Response): Promise<void> {
    const { run_id, action, entity_type, start_date, end_date, page, page_size } = req.query;

    const result = await AuditService.listAuditLogs({
      organizationId: req.organizationId!,
      runId: run_id ? String(run_id) : undefined,
      action: action ? String(action) : undefined,
      entityType: entity_type ? String(entity_type) : undefined,
      startDate: start_date ? new Date(String(start_date)) : undefined,
      endDate: end_date ? new Date(String(end_date)) : undefined,
      page: page ? parseInt(String(page), 10) : undefined,
      pageSize: page_size ? parseInt(String(page_size), 10) : undefined,
    });

    res.status(200).json(result);
  }
}

export class HealthController {
  static async getHealth(req: Request, res: Response): Promise<void> {
    res.status(200).json({
      status: "healthy",
      app: "Ledger Control API (Node/Express)",
      version: "1.0.0",
      database: "connected",
    });
  }
}
