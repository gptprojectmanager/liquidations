"""
Rate limiting middleware for FastAPI.

Implements simple in-memory rate limiting using sliding window algorithm.
For production, consider using Redis-based rate limiting.
"""

import time
from collections import defaultdict
from typing import Dict, Tuple

from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.validation.logger import logger
from src.validation.security_config import get_security_settings


class RateLimiter:
    """
    Simple in-memory rate limiter using sliding window algorithm.

    Note: This is suitable for single-server deployments.
    For multi-server deployments, use Redis-based rate limiting.
    """

    def __init__(self, requests_per_minute: int = 60, burst: int = 10):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests per minute per IP
            burst: Maximum burst requests allowed
        """
        self.requests_per_minute = requests_per_minute
        self.burst = burst
        self.window_size = 60  # 1 minute in seconds

        # Storage: {ip: [(timestamp, count), ...]}
        self.requests: Dict[str, list[Tuple[float, int]]] = defaultdict(list)

    def _cleanup_old_requests(self, ip: str, current_time: float):
        """Remove requests older than window size."""
        cutoff_time = current_time - self.window_size

        self.requests[ip] = [
            (timestamp, count) for timestamp, count in self.requests[ip] if timestamp > cutoff_time
        ]

    def is_allowed(self, ip: str) -> Tuple[bool, dict]:
        """
        Check if request from IP is allowed.

        Args:
            ip: Client IP address

        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        current_time = time.time()

        # Cleanup old requests
        self._cleanup_old_requests(ip, current_time)

        # Calculate total requests in window
        total_requests = sum(count for _, count in self.requests[ip])

        # Check if within limit
        allowed = total_requests < self.requests_per_minute

        # Add current request to window
        if allowed:
            self.requests[ip].append((current_time, 1))
            total_requests += 1

        # Calculate remaining requests
        remaining = max(0, self.requests_per_minute - total_requests)

        # Calculate reset time (end of current window)
        reset_time = int(current_time + self.window_size)

        rate_limit_info = {
            "limit": self.requests_per_minute,
            "remaining": remaining,
            "reset": reset_time,
            "retry_after": self.window_size if not allowed else 0,
        }

        return allowed, rate_limit_info


# Global rate limiter instance
_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Get rate limiter singleton."""
    global _rate_limiter
    if _rate_limiter is None:
        settings = get_security_settings()
        _rate_limiter = RateLimiter(
            requests_per_minute=settings.rate_limit_requests_per_minute,
            burst=settings.rate_limit_burst,
        )
    return _rate_limiter


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce rate limiting on API requests.

    Returns 429 Too Many Requests if rate limit exceeded.
    Adds rate limit headers to all responses.
    """

    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        settings = get_security_settings()

        # Skip rate limiting if disabled
        if not settings.rate_limit_enabled:
            return await call_next(request)

        # Get client IP
        client_ip = request.client.host if request.client else "unknown"

        # Check rate limit
        rate_limiter = get_rate_limiter()
        allowed, rate_info = rate_limiter.is_allowed(client_ip)

        # Log rate limit violations
        if not allowed:
            logger.warning(
                f"Rate limit exceeded for IP {client_ip}: {rate_info['limit']} requests/minute"
            )

            # Return 429 Too Many Requests
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Too Many Requests",
                    "message": f"Rate limit exceeded. Try again in {rate_info['retry_after']} seconds.",
                    "retry_after": rate_info["retry_after"],
                },
                headers={
                    "Retry-After": str(rate_info["retry_after"]),
                    "X-RateLimit-Limit": str(rate_info["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(rate_info["reset"]),
                },
            )

        # Process request
        response: Response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(rate_info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(rate_info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(rate_info["reset"])

        return response
