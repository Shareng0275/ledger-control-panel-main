import rateLimit from "express-rate-limit";

export const standardRateLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute window
  max: 500, // Generous limit for high-density local dashboard polling
  standardHeaders: true,
  legacyHeaders: false,
  message: {
    error: "TooManyRequests",
    detail: "API rate limit exceeded. Please retry after some time.",
    status_code: 429,
  },
});

export const authRateLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 500, // Permissive for local testing
  standardHeaders: true,
  legacyHeaders: false,
  message: {
    error: "TooManyRequests",
    detail: "Too many authentication attempts. Please try again later.",
    status_code: 429,
  },
});
