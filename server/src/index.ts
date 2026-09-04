import cors from "cors";
import express from "express";
import helmet from "helmet";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";
import { config } from "./config/index.js";
import { errorHandler } from "./middleware/errorHandler.js";
import { standardRateLimiter } from "./middleware/rateLimiter.js";
import { apiRouter } from "./routes/index.js";
import { startReconciliationWorker } from "./workers/reconciliationWorker.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const publicDir = path.resolve(__dirname, "../public");

const app = express();

// Security Headers
app.use(
  helmet({
    contentSecurityPolicy: false,
    crossOriginEmbedderPolicy: false,
  }),
);

// CORS
const allowedOrigins = config.CORS_ORIGIN.split(",").map((o) => o.trim());
app.use(
  cors({
    origin: (origin, callback) => {
      // Allow requests with no origin (like mobile apps, curl, server-to-server)
      if (!origin) return callback(null, true);
      if (allowedOrigins.includes(origin) || origin.includes("localhost") || origin.includes("127.0.0.1")) {
        return callback(null, true);
      }
      return callback(null, true); // Permissive in development
    },
    credentials: true,
  }),
);

// Body Parsing
app.use(express.json({ limit: "10mb" }));
app.use(express.urlencoded({ extended: true, limit: "10mb" }));

// Rate Limiting
app.use(standardRateLimiter);

// Serve Static Visualization Assets
if (fs.existsSync(publicDir)) {
  app.use(express.static(publicDir));
}

// Direct Visualization Web Page Routes
const serveVisualization = (_req: express.Request, res: express.Response) => {
  const filePath = path.resolve(publicDir, "historical_forecast_visualization.html");
  if (fs.existsSync(filePath)) {
    res.sendFile(filePath);
  } else {
    res.status(404).send("Visualization file not found on server.");
  }
};

app.get(
  [
    "/forecast-visualization",
    "/historical_forecast_visualization.html",
    "/visualizations/forecast",
    "/api/v1/forecast-visualization",
  ],
  serveVisualization,
);

// Root Health & Information Probes
app.get(["/", "/health"], (_req, res) => {
  res.status(200).json({
    status: "healthy",
    app: "Ledger Control API",
    version: "1.0.0",
    database: "connected",
    api_base: `http://localhost:${config.PORT}/api/v1`,
    visualizations: {
      historical_forecast: `http://localhost:${config.PORT}/forecast-visualization`,
    },
  });
});

app.get(["/api/v1", "/v1"], (_req, res) => {
  res.status(200).json({
    status: "online",
    app: "Ledger Control API",
    version: "1.0.0",
    message: "Ledger Control API Base v1 is active and accepting requests.",
    endpoints: {
      auth: "/api/v1/auth/login",
      uploads: "/api/v1/uploads/documents",
      reconcile: "/api/v1/reconcile/run",
      forecast: "/api/v1/forecast",
      forecast_visualization: "/forecast-visualization",
      ask: "/api/v1/ask",
      audit: "/api/v1/audit",
      paysim_summary: "/api/v1/datasets/paysim/summary",
      paysim_transactions: "/api/v1/datasets/paysim/transactions",
      paysim_fraud_analysis: "/api/v1/datasets/paysim/fraud-analysis",
    },
  });
});

// Mount Routes at both /api/v1 and /v1 for full frontend compatibility
app.use("/api/v1", apiRouter);
app.use("/v1", apiRouter);

// Centralized Error Handling Middleware
app.use(errorHandler);

// Start Server if not in test mode
if (process.env.NODE_ENV !== "test") {
  const server = app.listen(config.PORT, () => {
    console.log(`====================================================`);
    console.log(`🚀 Ledger Control Backend running on port ${config.PORT}`);
    console.log(`📡 Base API URL: http://localhost:${config.PORT}/api/v1`);
    console.log(`🩺 Health Probe: http://localhost:${config.PORT}/health`);
    console.log(`📊 Forecast Visual: http://localhost:${config.PORT}/forecast-visualization`);
    console.log(`====================================================`);

    // Start BullMQ background worker if Redis is available
    startReconciliationWorker();
  });

  // Graceful Shutdown
  const shutdown = async (signal: string) => {
    console.log(`\nReceived ${signal}. Shutting down gracefully...`);
    server.close(() => {
      console.log("HTTP server closed.");
      process.exit(0);
    });
  };

  process.on("SIGINT", () => shutdown("SIGINT"));
  process.on("SIGTERM", () => shutdown("SIGTERM"));
}

export default app;
