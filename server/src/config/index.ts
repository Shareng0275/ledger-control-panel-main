import dotenv from "dotenv";
import path from "path";
import { z } from "zod";

dotenv.config();

const envSchema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  PORT: z.coerce.number().default(8000),
  CORS_ORIGIN: z.string().default("http://localhost:5173"),
  DATABASE_URL: z.string().default("postgresql://postgres:postgres@localhost:5432/ledger_control?schema=public"),
  REDIS_URL: z.string().default("redis://localhost:6379"),
  JWT_SECRET: z.string().default("insecure_jwt_access_secret_replace_with_64_char_random_hex_key"),
  JWT_REFRESH_SECRET: z.string().default("insecure_jwt_refresh_secret_replace_with_64_char_random_hex_key"),
  JWT_ACCESS_EXPIRES_IN: z.string().default("15m"),
  FRONTEND_URL: z.string().default("http://localhost:5173"),
  GOOGLE_CLIENT_ID: z.string().optional().default(""),
  GOOGLE_CLIENT_SECRET: z.string().optional().default(""),
  GOOGLE_CALLBACK_URL: z.string().default("http://localhost:8000/api/v1/auth/google/callback"),
  GITHUB_CLIENT_ID: z.string().optional().default(""),
  GITHUB_CLIENT_SECRET: z.string().optional().default(""),
  GITHUB_CALLBACK_URL: z.string().default("http://localhost:8000/api/v1/auth/github/callback"),
  LLM_API_KEY: z.string().optional().default(""),
  LLM_MODEL: z.string().default("gpt-4o-mini"),
  STORAGE_DIR: z.string().default("storage/uploads"),
  MAX_UPLOAD_SIZE_MB: z.coerce.number().default(25),
  FUZZY_AUTO_MATCH_THRESHOLD: z.coerce.number().default(0.88),
  FUZZY_REVIEW_THRESHOLD: z.coerce.number().default(0.65),
  FUZZY_WEIGHT_AMOUNT: z.coerce.number().default(0.35),
  FUZZY_WEIGHT_DESCRIPTION: z.coerce.number().default(0.30),
  FUZZY_WEIGHT_DATE: z.coerce.number().default(0.25),
  FUZZY_WEIGHT_REFERENCE: z.coerce.number().default(0.10),
  FUZZY_MAX_DATE_DIFF_DAYS: z.coerce.number().default(7),
  FUZZY_MAX_AMOUNT_DIFF_PERCENT: z.coerce.number().default(0.05),
});

const parsed = envSchema.safeParse(process.env);

if (!parsed.success) {
  console.error("❌ Invalid environment variables:", parsed.error.format());
  process.exit(1);
}

export const config = parsed.data;
