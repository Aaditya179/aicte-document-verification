"""
Rate limiting (§15.8) for login, OTP, AI and public token endpoints.

A FastAPI dependency over the `limits` library, so a whole router or a single route can be
limited without changing handler signatures. Counters are in memory, per process; a
multi-instance deployment would point `limits` at Redis instead.
"""
from fastapi import HTTPException, Request
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

_limiter = MovingWindowRateLimiter(MemoryStorage())


def _client_key(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


def rate_limit(limit: str, scope: str):
    """Dependency allowing `limit` (for example "10/minute") requests per client IP within `scope`."""
    item = parse(limit)

    async def check(request: Request) -> None:
        if not _limiter.hit(item, scope, _client_key(request)):
            raise HTTPException(status_code=429, detail="Too many requests, try again shortly",
                                headers={"Retry-After": str(item.get_expiry())})
    return check


def reset() -> None:
    """Clear all counters (tests)."""
    _limiter.storage.reset()
