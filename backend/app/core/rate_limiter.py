import time
from collections import defaultdict
from typing import Dict, List, Optional
from fastapi import HTTPException, Request, status


class SlidingWindowRateLimiter:
    """
    In-memory Sliding Window Rate Limiter.
    Tracks request timestamps per client IP / user identifier to enforce fair use and prevent DoS.
    """

    def __init__(self, requests_per_minute: int = 60, burst_limit: int = 100):
        self.requests_per_minute = requests_per_minute
        self.burst_limit = burst_limit
        self.window_seconds = 60.0
        # Map of identifier -> list of request timestamps
        self._history: Dict[str, List[float]] = defaultdict(list)

    def is_rate_limited(self, identifier: str) -> tuple[bool, int]:
        """
        Check if request for identifier exceeds allowed rate limit.
        Returns: (is_limited: bool, retry_after_seconds: int)
        """
        now = time.time()
        window_start = now - self.window_seconds

        # Clean old timestamps outside current sliding window
        timestamps = [ts for ts in self._history[identifier] if ts > window_start]
        self._history[identifier] = timestamps

        if len(timestamps) >= self.requests_per_minute:
            oldest_timestamp = timestamps[0]
            retry_after = max(1, int(oldest_timestamp + self.window_seconds - now))
            return True, retry_after

        # Record this request
        self._history[identifier].append(now)
        return False, 0

    def reset(self) -> None:
        """Clear rate limit history."""
        self._history.clear()


# Global rate limit instances
general_limiter = SlidingWindowRateLimiter(requests_per_minute=120, burst_limit=150)
auth_limiter = SlidingWindowRateLimiter(requests_per_minute=20, burst_limit=30)
ai_limiter = SlidingWindowRateLimiter(requests_per_minute=30, burst_limit=40)


def rate_limit_dependency(limiter: SlidingWindowRateLimiter):
    """Factory creating a FastAPI dependency for endpoint rate limiting."""
    async def _check_rate_limit(request: Request) -> None:
        # Resolve identifier: client IP or X-Forwarded-For
        forwarded = request.headers.get("x-forwarded-for")
        client_ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
        identifier = f"{client_ip}:{request.url.path}"

        is_limited, retry_after = limiter.is_rate_limited(identifier)
        if is_limited:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please slow down and try again later.",
                headers={"Retry-After": str(retry_after)},
            )

    return _check_rate_limit
