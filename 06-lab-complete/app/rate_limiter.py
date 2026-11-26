"""Rate limiting (tiêu chí 7) — sliding window lưu trong Redis."""
import secrets
import time
from fastapi import HTTPException
from app.config import settings
from app.redis_client import r

WINDOW_SECONDS = 60


def check_rate_limit(key: str) -> None:
    """Kiểm tra giới hạn request/phút theo API key; vượt mức trả HTTP 429."""
    if r is None:
        return

    now = time.time()
    window_start = now - WINDOW_SECONDS
    redis_key = f"ratelimit:{key}"
    limit = settings.rate_limit_per_minute

    try:
        pipe = r.pipeline()
        pipe.zremrangebyscore(redis_key, 0, window_start)
        pipe.zcard(redis_key)
        _, current_count = pipe.execute()

        if current_count >= limit:
            oldest = r.zrange(redis_key, 0, 0, withscores=True)
            retry_after = (
                max(1, int(oldest[0][1] + WINDOW_SECONDS - now) + 1)
                if oldest
                else WINDOW_SECONDS
            )
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )

        member = f"{now}:{secrets.token_hex(4)}"
        pipe = r.pipeline()
        pipe.zadd(redis_key, {member: now})
        pipe.expire(redis_key, WINDOW_SECONDS + 5)
        pipe.execute()
    except HTTPException:
        raise
    except Exception:
        # Không làm sập request nếu Redis tạm thời gián đoạn
        return
