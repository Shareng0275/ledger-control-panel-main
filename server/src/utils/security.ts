import bcrypt from "bcryptjs";
import crypto from "crypto";
import jwt from "jsonwebtoken";
import { config } from "../config/index.js";

export async function hashPassword(plainText: string): Promise<string> {
  const salt = await bcrypt.genSalt(10);
  return bcrypt.hash(plainText, salt);
}

export async function verifyPassword(plainText: string, hash: string): Promise<boolean> {
  return bcrypt.compare(plainText, hash);
}

export function hashToken(token: string): string {
  return crypto.createHash("sha256").update(token).digest("hex");
}

export function generateAccessToken(payload: { userId: string; email: string; role?: string }): string {
  return jwt.sign(payload, config.JWT_SECRET, {
    expiresIn: "15m",
  });
}

export function generateRefreshToken(payload: { userId: string }): string {
  return jwt.sign(
    { ...payload, nonce: crypto.randomBytes(16).toString("hex") },
    config.JWT_REFRESH_SECRET,
    { expiresIn: "30d" },
  );
}

export function verifyAccessToken(token: string): { userId: string; email: string; role?: string } {
  return jwt.verify(token, config.JWT_SECRET) as { userId: string; email: string; role?: string };
}

export function verifyRefreshToken(token: string): { userId: string } {
  return jwt.verify(token, config.JWT_REFRESH_SECRET) as { userId: string };
}
