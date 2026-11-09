"""
SYNQ Security & Performance Middleware.

Provides:
- In-memory sliding-window Rate Limiter preventing DoS and brute-force attacks.
- OWASP Security Headers (CSP, HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy).
"""

from collections import defaultdict
import logging
import time
from typing import Dict, List, Tuple
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Sliding Window Rate Limiter ───────────────────────────────────────────────

class RateLimiter:
    """
    Sliding-window rate limiter per client IP.
    Tracks timestamps in 60-second windows with automatic memory garbage collection.
    """

    def __init__(self):
        # ip -> list of float timestamps
        self.history: Dict[str, List[float]] = defaultdict(list)
        self.last_cleanup = time.time()

    def _cleanup_stale_records(self, now: float) -> None:
        """Purge records older than 120 seconds to prevent memory unbounded growth."""
        if now - self.last_cleanup < 30.0:
            return
        self.last_cleanup = now
        stale_threshold = now - 120.0
        keys_to_delete = []
        for ip, timestamps in self.history.items():
            valid_ts = [t for t in timestamps if t > stale_threshold]
            if valid_ts:
                self.history[ip] = valid_ts
            else:
                keys_to_delete.append(ip)
        for k in keys_to_delete:
            del self.history[k]

    def check(self, key: str, max_requests: int, window_seconds: float = 60.0) -> Tuple[bool, int, int]:
        """
        Check if request is allowed.
        Returns: (is_allowed, remaining, retry_after_seconds)
        """
        now = time.time()
        self._cleanup_stale_records(now)

        cutoff = now - window_seconds
        records = [t for t in self.history[key] if t > cutoff]
        self.history[key] = records

        count = len(records)
        if count >= max_requests:
            oldest_in_window = records[0]
            retry_after = max(1, int(window_seconds - (now - oldest_in_window)))
            return False, 0, retry_after

        self.history[key].append(now)
        remaining = max_requests - (count + 1)
        return True, remaining, 0

    def reset_for_tests(self) -> None:
        self.history.clear()


rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not settings.rate_limit_enabled:
            return await call_next(request)

        # Skip rate limiting for static options/preflights or health check polling
        path = request.url.path
        if request.method == "OPTIONS" or path in ("/health", "/api/v1/health"):
            return await call_next(request)

        # Resolve client IP securely to prevent IP spoofing
        # When trust_proxy_headers is disabled (safe default), rely strictly on direct socket IP
        client_ip = request.client.host if request.client else "127.0.0.1"
        if settings.trust_proxy_headers:
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                # Rightmost IP in X-Forwarded-For is appended by the nearest trusted reverse proxy
                client_ip = forwarded.split(",")[-1].strip()
            elif request.headers.get("cf-connecting-ip"):
                client_ip = request.headers.get("cf-connecting-ip").strip()

        # Determine rate limit quota based on endpoint sensitivity
        if "/api/v1/auth" in path:
            limit = settings.rate_limit_auth_per_minute
            key = f"auth:{client_ip}"
        elif "/plan" in path or "/execute" in path:
            limit = settings.rate_limit_ai_per_minute
            key = f"ai:{client_ip}"
        else:
            limit = settings.rate_limit_requests_per_minute
            key = f"gen:{client_ip}"

        allowed, remaining, retry_after = rate_limiter.check(key, limit, window_seconds=60.0)

        if not allowed:
            logger.warning("Rate limit exceeded for %s on %s %s", client_ip, request.method, path)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please slow down.",
                    "retry_after_seconds": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response: Response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


# ── Security Headers Middleware ───────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        if not settings.security_headers_enabled:
            return response

        # Standard OWASP defensive headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"

        # HSTS only on HTTPS or production
        if request.url.scheme == "https" or settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        # Content-Security-Policy defense in depth
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data: https:; "
            "connect-src 'self' ws: wss: http: https:; "
            "frame-ancestors 'none';"
        )
        response.headers["Content-Security-Policy"] = csp

        return response
