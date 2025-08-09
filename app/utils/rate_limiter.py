from typing import Optional
from redis import Redis, ConnectionPool
from app.core.config import settings

# Simple Redis-based rate limiter
_pool: Optional[ConnectionPool] = None
_client: Optional[Redis] = None


def get_client() -> Redis:
    global _pool, _client
    if _client is None:
        _pool = ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)
        _client = Redis(connection_pool=_pool)
    return _client


def allow(key: str, limit: int, window_seconds: int) -> bool:
    """Return True if action under key is allowed within window, else False.

    Uses INCR + EXPIRE (nx) for a rolling window per key.
    """
    r = get_client()
    with r.pipeline() as pipe:
        pipe.incr(key, 1)
        pipe.expire(key, window_seconds, nx=True)
        count, _ = pipe.execute()
    try:
        count_int = int(count)
    except Exception:
        count_int = limit  # be safe
    return count_int <= limit


def allow_for_email(action: str, email: str, limit: int, window_seconds: int = 60) -> bool:
    safe_email = (email or "").lower()
    key = f"otp:{action}:{safe_email}"
    return allow(key, limit, window_seconds)
