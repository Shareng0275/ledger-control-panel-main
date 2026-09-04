import type { Request, Response } from "express";
import { DocumentExtractionService } from "../services/documentExtractionService.js";

interface AuthenticatedRequest extends Request {
  organizationId?: string;
  user?: {
    id: string;
    email: string;
  };
}

export class DocumentController {
  static async uploadDocument(req: AuthenticatedRequest, res: Response): Promise<void> {
    if (!req.file) {
      res.status(400).json({
        success: false,
        error: {
          code: "MISSING_FILE",
          message: "No file was attached to the multipart/form-data upload request.",
        },
      });
      return;
    }

    const organizationId = req.organizationId!;
    const userId = req.user!.id;

    const result = await DocumentExtractionService.extractDocument({
      filePath: req.file.path,
      filename: req.file.originalname,
      mimeType: req.file.mimetype,
      organizationId,
      userId,
    });

    if (!result.success) {
      const statusCode = result.error?.code === "FILE_TOO_LARGE" ? 413 : 422;
      res.status(statusCode).json(result);
      return;
    }

    res.status(201).json(result);
  }
}
