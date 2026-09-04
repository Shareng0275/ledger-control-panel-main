import { Request, Response } from "express";
import { PaySimService } from "../services/paysimService.js";

export class PaySimController {
  static getSummary(_req: Request, res: Response) {
    try {
      const summary = PaySimService.getSummary();
      res.status(200).json({
        success: true,
        data: summary,
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to query PaySim summary";
      res.status(500).json({
        success: false,
        error: message,
      });
    }
  }

  static getTransactions(req: Request, res: Response) {
    try {
      const page = req.query.page ? parseInt(String(req.query.page), 10) : 1;
      const limit = req.query.limit ? parseInt(String(req.query.limit), 10) : 20;
      const type = req.query.type ? String(req.query.type) : undefined;
      const isFraud = req.query.isFraud !== undefined ? req.query.isFraud === "true" : undefined;
      const minAmount = req.query.minAmount ? parseFloat(String(req.query.minAmount)) : undefined;
      const maxAmount = req.query.maxAmount ? parseFloat(String(req.query.maxAmount)) : undefined;
      const search = req.query.search ? String(req.query.search) : undefined;

      const result = PaySimService.getTransactions({
        page,
        limit,
        type,
        isFraud,
        minAmount,
        maxAmount,
        search,
      });

      res.status(200).json({
        success: true,
        data: result.data,
        meta: result.meta,
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to query PaySim transactions";
      res.status(500).json({
        success: false,
        error: message,
      });
    }
  }

  static getFraudAnalysis(_req: Request, res: Response) {
    try {
      const analysis = PaySimService.getFraudAnalysis();
      res.status(200).json({
        success: true,
        data: analysis,
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to analyze PaySim fraud dataset";
      res.status(500).json({
        success: false,
        error: message,
      });
    }
  }
}
