import type { Response } from "express";
import { AppError } from "../middleware/errorHandler.js";
import { UploadService } from "../services/uploadService.js";
import type { AuthenticatedRequest } from "../types/index.js";

export class UploadController {
  static async uploadStatement(req: AuthenticatedRequest, res: Response): Promise<void> {
    if (!req.file) {
      throw new AppError("No file uploaded. Please provide a CSV file under the 'file' key.", 400);
    }

    const result = await UploadService.processCsvUpload({
      filePath: req.file.path,
      filename: req.file.originalname,
      uploadType: "statement",
      organizationId: req.organizationId!,
      userId: req.user!.id,
    });

    res.status(201).json(result);
  }

  static async uploadLedger(req: AuthenticatedRequest, res: Response): Promise<void> {
    if (!req.file) {
      throw new AppError("No file uploaded. Please provide a CSV file under the 'file' key.", 400);
    }

    const result = await UploadService.processCsvUpload({
      filePath: req.file.path,
      filename: req.file.originalname,
      uploadType: "ledger",
      organizationId: req.organizationId!,
      userId: req.user!.id,
    });

    res.status(201).json(result);
  }
}
