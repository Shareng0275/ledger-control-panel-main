import type { NextFunction, Request, Response } from "express";
import { ZodError } from "zod";

export class AppError extends Error {
  statusCode: number;
  code: string;
  details?: unknown;

  constructor(message: string, statusCode: number = 400, code: string = "BAD_REQUEST", details?: unknown) {
    super(message);
    this.name = "AppError";
    this.statusCode = statusCode;
    this.code = code;
    this.details = details;
  }
}

export class BadRequestError extends AppError {
  constructor(message: string = "Bad Request", code: string = "BAD_REQUEST", details?: unknown) {
    super(message, 400, code, details);
    this.name = "BadRequestError";
  }
}

export class UnauthorizedError extends AppError {
  constructor(message: string = "Authentication required", code: string = "UNAUTHORIZED") {
    super(message, 401, code);
    this.name = "UnauthorizedError";
  }
}

export class ForbiddenError extends AppError {
  constructor(message: string = "Insufficient permissions", code: string = "FORBIDDEN") {
    super(message, 403, code);
    this.name = "ForbiddenError";
  }
}

export class NotFoundError extends AppError {
  constructor(message: string = "Requested resource not found", code: string = "NOT_FOUND") {
    super(message, 404, code);
    this.name = "NotFoundError";
  }
}

export class ConflictError extends AppError {
  constructor(message: string = "Resource conflict occurred", code: string = "RESOURCE_CONFLICT") {
    super(message, 409, code);
    this.name = "ConflictError";
  }
}

export class PayloadTooLargeError extends AppError {
  constructor(message: string = "File size exceeds maximum allowed limit", code: string = "FILE_TOO_LARGE") {
    super(message, 413, code);
    this.name = "PayloadTooLargeError";
  }
}

export class ValidationError extends AppError {
  constructor(message: string = "Validation failed for request data", code: string = "VALIDATION_FAILED", details?: unknown) {
    super(message, 422, code, details);
    this.name = "ValidationError";
  }
}

export class TooManyRequestsError extends AppError {
  constructor(message: string = "Rate limit exceeded. Please try again later.", code: string = "RATE_LIMIT_EXCEEDED") {
    super(message, 429, code);
    this.name = "TooManyRequestsError";
  }
}

export function errorHandler(
  err: any,
  req: Request,
  res: Response,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  next: NextFunction,
): void {
  const errMsg = err?.message || String(err);
  console.error(`[Centralized Error Handler] ${req.method} ${req.originalUrl}: ${errMsg}`);

  // 1. Zod Validation Errors (422)
  if (err instanceof ZodError) {
    res.status(422).json({
      error: "ValidationError",
      code: "VALIDATION_FAILED",
      detail: "Request payload validation failed.",
      status_code: 422,
      errors: err.errors.map((e) => ({
        field: e.path.join("."),
        message: e.message,
      })),
    });
    return;
  }

  // 2. Multer File Upload Errors (413 / 400)
  if (err.name === "MulterError") {
    if (err.code === "LIMIT_FILE_SIZE") {
      res.status(413).json({
        error: "PayloadTooLargeError",
        code: "FILE_TOO_LARGE",
        detail: "The uploaded file exceeds the maximum allowed size limit of 25MB.",
        status_code: 413,
      });
      return;
    }

    res.status(400).json({
      error: "BadRequestError",
      code: "FILE_UPLOAD_FAILED",
      detail: err.message || "File upload processing failed.",
      status_code: 400,
    });
    return;
  }

  // 3. Custom App Errors (400, 401, 403, 404, 409, 413, 422, 429)
  if (err instanceof AppError) {
    res.status(err.statusCode).json({
      error: err.name,
      code: err.code,
      detail: err.message,
      status_code: err.statusCode,
      details: err.details,
    });
    return;
  }

  // 4. Prisma Record Not Found (404)
  if (err.code === "P2025") {
    res.status(404).json({
      error: "NotFoundError",
      code: "NOT_FOUND",
      detail: "The requested entity or record was not found.",
      status_code: 404,
    });
    return;
  }

  // 5. Prisma Unique Constraint Violation (409)
  if (err.code === "P2002") {
    res.status(409).json({
      error: "ConflictError",
      code: "UNIQUE_CONSTRAINT_VIOLATION",
      detail: "A record with this unique identifier or reference already exists.",
      status_code: 409,
    });
    return;
  }

  // 6. JSON Syntax Parsing Errors (400)
  if (err instanceof SyntaxError && "body" in err) {
    res.status(400).json({
      error: "BadRequestError",
      code: "INVALID_JSON_SYNTAX",
      detail: "The request body contains invalid JSON syntax.",
      status_code: 400,
    });
    return;
  }

  // 7. Generic Internal Server Error (500) — Sanitized for production security
  const statusCode = err.status || err.statusCode || 500;
  res.status(statusCode).json({
    error: "InternalServerError",
    code: "INTERNAL_SERVER_ERROR",
    detail: statusCode === 500 ? "An unexpected server error occurred. Please contact support." : err.message,
    status_code: statusCode,
  });
}
