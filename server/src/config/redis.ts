import { Redis } from "ioredis";
import { config } from "./index.js";

let redisClient: Redis | null = null;
let isRedisAvailable = false;

export function getRedisConnection(): Redis | null {
  if (redisClient) return isRedisAvailable ? redisClient : null;

  try {
    const client = new Redis(config.REDIS_URL, {
      maxRetriesPerRequest: 1,
      enableReadyCheck: false,
      lazyConnect: true,
      retryStrategy(times: number) {
        if (times > 1) {
          isRedisAvailable = false;
          return null; // Stop retrying immediately if Redis not running
        }
        return null;
      },
    });

    client.on("connect", () => {
      isRedisAvailable = true;
      console.log(" Connected to Redis queue server");
    });

    client.on("error", () => {
      isRedisAvailable = false;
    });

    // Attempt non-blocking connection
    client.connect().catch(() => {
      isRedisAvailable = false;
    });

    redisClient = client;
    return isRedisAvailable ? client : null;
  } catch {
    return null;
  }
}

export function checkRedisAvailable(): boolean {
  return isRedisAvailable;
}
