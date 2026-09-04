import { Router } from "express";
import fs from "fs";
import multer from "multer";
import path from "path";
import { config } from "../config/index.js";
import { AuthController } from "../controllers/authController.js";
import { OAuthController } from "../controllers/oauthController.js";
import { ExceptionController } from "../controllers/exceptionController.js";
import {
  AiController,
  AuditController,
  ForecastController,
  HealthController,
} from "../controllers/miscControllers.js";
import { ReconciliationController } from "../controllers/reconciliationController.js";
import { TransactionController } from "../controllers/transactionController.js";
import { UploadController } from "../controllers/uploadController.js";
import { DocumentController } from "../controllers/documentController.js";
import { DraftController } from "../controllers/draftController.js";
import { ManagerController } from "../controllers/managerController.js";
import { AdminController } from "../controllers/adminController.js";
import { AdvancedFeaturesController } from "../controllers/advancedFeaturesController.js";
import { PaySimController } from "../controllers/paysimController.js";
import { requireAuth, requireOrg, requireRole, requirePermission } from "../middleware/auth.js";
import { authRateLimiter } from "../middleware/rateLimiter.js";
import { asyncHandler } from "../utils/asyncHandler.js";

// Ensure storage directory exists
const uploadDir = path.resolve(config.STORAGE_DIR);
if (!fs.existsSync(uploadDir)) {
  fs.mkdirSync(uploadDir, { recursive: true });
}

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, uploadDir),
  filename: (_req, file, cb) => {
    const unique = `${Date.now()}-${Math.round(Math.random() * 1e9)}`;
    cb(null, `${unique}-${file.originalname}`);
  },
});

const upload = multer({
  storage,
  limits: { fileSize: config.MAX_UPLOAD_SIZE_MB * 1024 * 1024 },
});

export const apiRouter = Router();

// ─── Health ──────────────────────────────────────────────────────────────────
apiRouter.get("/health", asyncHandler(HealthController.getHealth));

// ─── Authentication & OAuth 2.0 ──────────────────────────────────────────────
apiRouter.post("/auth/register", authRateLimiter, asyncHandler(AuthController.register));
apiRouter.post("/auth/login", authRateLimiter, asyncHandler(AuthController.login));
apiRouter.post("/auth/refresh", authRateLimiter, asyncHandler(AuthController.refresh));
apiRouter.post("/auth/logout", asyncHandler(AuthController.logout));
apiRouter.get("/auth/me", requireAuth, asyncHandler(AuthController.getMe));

// Google OAuth
apiRouter.get("/auth/google", OAuthController.googleRedirect);
apiRouter.get("/auth/google/callback", asyncHandler(OAuthController.googleCallback));

// GitHub OAuth
apiRouter.get("/auth/github", OAuthController.githubRedirect);
apiRouter.get("/auth/github/callback", asyncHandler(OAuthController.githubCallback));

// ─── Uploads ─────────────────────────────────────────────────────────────────
apiRouter.post(
  "/uploads/statement",
  requireAuth,
  requireOrg,
  requirePermission("documents.create"),
  upload.single("file"),
  asyncHandler(UploadController.uploadStatement),
);
apiRouter.post(
  "/uploads/ledger",
  requireAuth,
  requireOrg,
  requirePermission("documents.create"),
  upload.single("file"),
  asyncHandler(UploadController.uploadLedger),
);
apiRouter.post(
  "/uploads/documents",
  requireAuth,
  requireOrg,
  requirePermission("documents.create"),
  upload.single("file"),
  asyncHandler(DocumentController.uploadDocument),
);
apiRouter.post(
  "/uploads/pdf-statements",
  requireAuth,
  requireOrg,
  requirePermission("documents.create"),
  upload.single("file"),
  asyncHandler(DocumentController.uploadDocument),
);

// ─── Reconciliation ──────────────────────────────────────────────────────────
apiRouter.post(
  "/reconcile/run",
  requireAuth,
  requireOrg,
  requirePermission("reconciliation.execute"),
  asyncHandler(ReconciliationController.startRun),
);
apiRouter.get("/reconcile/:run_id", requireAuth, requireOrg, requirePermission("reconciliation.read"), asyncHandler(ReconciliationController.getRun));
apiRouter.get("/reconcile/runs/:run_id", requireAuth, requireOrg, requirePermission("reconciliation.read"), asyncHandler(ReconciliationController.getRun));
apiRouter.get("/reconcile/:run_id/summary", requireAuth, requireOrg, requirePermission("reconciliation.read"), asyncHandler(ReconciliationController.getRunSummary));

// ─── Transactions ────────────────────────────────────────────────────────────
apiRouter.get("/transactions", requireAuth, requireOrg, requirePermission("reconciliation.read"), asyncHandler(TransactionController.list));
apiRouter.get("/transactions/export", requireAuth, requireOrg, requirePermission("records.read"), asyncHandler(TransactionController.export));
apiRouter.get("/transactions/:id", requireAuth, requireOrg, requirePermission("reconciliation.read"), asyncHandler(TransactionController.getById));

// ─── Exceptions ──────────────────────────────────────────────────────────────
apiRouter.get("/exceptions", requireAuth, requireOrg, requirePermission("reconciliation.read"), asyncHandler(ExceptionController.list));
apiRouter.get("/exceptions/:id", requireAuth, requireOrg, requirePermission("reconciliation.read"), asyncHandler(ExceptionController.getById));
apiRouter.post(
  "/exceptions/:id/resolve",
  requireAuth,
  requireOrg,
  requirePermission("reconciliation.resolve"),
  asyncHandler(ExceptionController.resolve),
);
apiRouter.post(
  "/exceptions/bulk-resolve",
  requireAuth,
  requireOrg,
  requirePermission("reconciliation.resolve"),
  asyncHandler(ExceptionController.bulkResolve),
);

// ─── Record Drafts & Adjustments (Editor Workflow) ──────────────────────────
apiRouter.post(
  "/records/drafts",
  requireAuth,
  requireOrg,
  requirePermission("records.create"),
  asyncHandler(DraftController.create),
);
apiRouter.get(
  "/records/drafts",
  requireAuth,
  requireOrg,
  requirePermission("records.read"),
  asyncHandler(DraftController.list),
);
apiRouter.get(
  "/records/drafts/:id",
  requireAuth,
  requireOrg,
  requirePermission("records.read"),
  asyncHandler(DraftController.getById),
);
apiRouter.put(
  "/records/drafts/:id",
  requireAuth,
  requireOrg,
  requirePermission("records.update"),
  asyncHandler(DraftController.update),
);
apiRouter.post(
  "/records/drafts/:id/submit",
  requireAuth,
  requireOrg,
  requirePermission("records.update"),
  asyncHandler(DraftController.submit),
);
apiRouter.post(
  "/records/drafts/:id/approve",
  requireAuth,
  requireOrg,
  requirePermission("workflow.approve"),
  asyncHandler(DraftController.approve),
);

// ─── Manager Workflow, Approvals & Team Control ─────────────────────────────
apiRouter.get(
  "/manager/team",
  requireAuth,
  requireOrg,
  requirePermission("users.read"),
  asyncHandler(ManagerController.getTeam),
);
apiRouter.get(
  "/manager/approval-queue",
  requireAuth,
  requireOrg,
  requirePermission("workflow.approve"),
  asyncHandler(ManagerController.getApprovalQueue),
);
apiRouter.post(
  "/manager/workflows/:id/approve",
  requireAuth,
  requireOrg,
  requirePermission("workflow.approve"),
  asyncHandler(ManagerController.approve),
);
apiRouter.post(
  "/manager/workflows/:id/reject",
  requireAuth,
  requireOrg,
  requirePermission("workflow.approve"),
  asyncHandler(ManagerController.reject),
);
apiRouter.post(
  "/manager/tasks/assign",
  requireAuth,
  requireOrg,
  requirePermission("workflow.assign"),
  asyncHandler(ManagerController.assign),
);
apiRouter.post(
  "/manager/tasks/delegate",
  requireAuth,
  requireOrg,
  requirePermission("workflow.assign"),
  asyncHandler(ManagerController.delegate),
);

// ─── Forecasting ─────────────────────────────────────────────────────────────
apiRouter.get("/forecast", requireAuth, requireOrg, requirePermission("analytics.read"), asyncHandler(ForecastController.getForecast));

// ─── AI Intelligence & Predictive Anomaly Detection ──────────────────────────
apiRouter.post("/ask", requireAuth, requireOrg, requirePermission("analytics.read"), asyncHandler(AiController.ask));
apiRouter.get("/insights", requireAuth, requireOrg, requirePermission("analytics.read"), asyncHandler(AiController.getInsights));
apiRouter.get("/analytics/anomalies", requireAuth, requireOrg, requirePermission("analytics.read"), asyncHandler(AdvancedFeaturesController.getPredictiveAnomalies));

// ─── Custom Dashboards & User Preferences ───────────────────────────────────
apiRouter.get("/users/preferences", requireAuth, requireOrg, requirePermission("records.read"), asyncHandler(AdvancedFeaturesController.getPreferences));
apiRouter.put("/users/preferences", requireAuth, requireOrg, requirePermission("records.read"), asyncHandler(AdvancedFeaturesController.updatePreferences));

// ─── Automated Scheduled Reporting ──────────────────────────────────────────
apiRouter.get("/reports/scheduled", requireAuth, requireOrg, requirePermission("analytics.read"), asyncHandler(AdvancedFeaturesController.listScheduledReports));
apiRouter.post("/reports/scheduled/generate", requireAuth, requireOrg, requirePermission("analytics.export"), asyncHandler(AdvancedFeaturesController.generateScheduledReport));

// ─── Compliance Audit Log ────────────────────────────────────────────────────
apiRouter.get(
  "/audit",
  requireAuth,
  requireOrg,
  requireRole(["admin"]),
  asyncHandler(AuditController.list),
);

// ─── Master Administrator Controls ──────────────────────────────────────────
apiRouter.get(
  "/admin/users",
  requireAuth,
  requireOrg,
  requireRole(["admin"]),
  asyncHandler(AdminController.listUsers),
);
apiRouter.post(
  "/admin/users",
  requireAuth,
  requireOrg,
  requireRole(["admin"]),
  asyncHandler(AdminController.createUser),
);
apiRouter.put(
  "/admin/users/:id/role",
  requireAuth,
  requireOrg,
  requireRole(["admin"]),
  asyncHandler(AdminController.updateUserRole),
);
apiRouter.put(
  "/admin/users/:id/status",
  requireAuth,
  requireOrg,
  requireRole(["admin"]),
  asyncHandler(AdminController.setUserStatus),
);
apiRouter.get(
  "/admin/permissions",
  requireAuth,
  requireOrg,
  requireRole(["admin"]),
  asyncHandler(AdminController.getPermissions),
);
apiRouter.get(
  "/admin/security/metrics",
  requireAuth,
  requireOrg,
  requireRole(["admin"]),
  asyncHandler(AdminController.getSecurityMetrics),
);
apiRouter.get(
  "/admin/settings",
  requireAuth,
  requireOrg,
  requireRole(["admin"]),
  asyncHandler(AdminController.getSettings),
);
apiRouter.put(
  "/admin/settings",
  requireAuth,
  requireOrg,
  requireRole(["admin"]),
  asyncHandler(AdminController.updateSettings),
);

// ─── PaySim Synthetic Financial Transactions Dataset ─────────────────────────
apiRouter.get("/datasets/paysim/summary", PaySimController.getSummary);
apiRouter.get("/datasets/paysim/transactions", PaySimController.getTransactions);
apiRouter.get("/datasets/paysim/fraud-analysis", PaySimController.getFraudAnalysis);

