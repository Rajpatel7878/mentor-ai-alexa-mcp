"""
limiter.py — Per-IP in-process rate limiter for Mentor AI.

Uses a plain Python dict protected by a threading.Lock — no external store.
State is lost on server restart, which is acceptable for a hackathon.

Configuration (read from environment on import):
  RATE_LIMIT_REQUESTS        (default: 10)  — max requests per window per IP
  RATE_LIMIT_WINDOW_SECONDS  (default: 60)  — rolling window length in seconds
"""

from __future__ import annotations

import os
import time
import threading
from collections import deque
from typing import Deque

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "10"))
RATE_LIMIT_WINDOW: float = float(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
TRUST_PROXY_HEADERS: bool = os.getenv("TRUST_PROXY_HEADERS", "false").lower() in {
    "1", "true", "yes", "on"
}

# ─────────────────────────────────────────────────────────────────────────────
# State
# ─────────────────────────────────────────────────────────────────────────────

# Map of IP → deque of request timestamps within the current window
_buckets: dict[str, Deque[float]] = {}
_lock = threading.Lock()
_last_cleanup = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

class RateLimitExceeded(Exception):
    """Raised when an IP exceeds the allowed request rate."""

    def __init__(self, ip: str, limit: int, window: float) -> None:
        self.ip = ip
        self.limit = limit
        self.window = window
        super().__init__(
            f"Rate limit exceeded for {ip}: {limit} requests per {window}s."
        )


def check_rate_limit(ip: str) -> None:
    """
    Check whether *ip* is within the rate limit.

    Raises RateLimitExceeded if the IP has exceeded RATE_LIMIT_REQUESTS
    in the last RATE_LIMIT_WINDOW seconds.

    This function is thread-safe.
    """
    now = time.monotonic()
    cutoff = now - RATE_LIMIT_WINDOW

    global _last_cleanup

    with _lock:
        # Remove stale IP buckets periodically so rotating client addresses
        # cannot grow this in-process store without bound.
        if now - _last_cleanup >= RATE_LIMIT_WINDOW:
            stale_ips = [
                bucket_ip
                for bucket_ip, bucket in _buckets.items()
                if not bucket or bucket[-1] < cutoff
            ]
            for stale_ip in stale_ips:
                del _buckets[stale_ip]
            _last_cleanup = now

        if ip not in _buckets:
            _buckets[ip] = deque()

        bucket = _buckets[ip]

        # Evict timestamps outside the window for the current IP.
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) >= RATE_LIMIT_REQUESTS:
            raise RateLimitExceeded(ip, RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW)

        bucket.append(now)


def reset_rate_limits() -> None:
    """Clear all buckets; intended for isolated tests and local diagnostics."""
    global _last_cleanup
    with _lock:
        _buckets.clear()
        _last_cleanup = time.monotonic()


def get_client_ip(request) -> str:
    """
    Extract the best available IP from a Starlette Request.

    Uses X-Forwarded-For only when TRUST_PROXY_HEADERS=true and the request
    came through a trusted reverse proxy. It is disabled by default because
    clients can otherwise spoof the header to bypass rate limiting.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if TRUST_PROXY_HEADERS and forwarded_for:
        # Take the leftmost (originating) address. The proxy must sanitize this
        # header before enabling TRUST_PROXY_HEADERS in production.
        candidate = forwarded_for.split(",")[0].strip()
        if candidate and len(candidate) <= 128:
            return candidate
    if request.client:
        return request.client.host
    return "unknown"
