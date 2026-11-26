"""Cost guard (tiêu chí 8) — theo dõi chi phí LLM trong Redis."""
from datetime import datetime, timezone
from fastapi import HTTPException
from app.config import settings
from app.redis_client import r

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def _budget_keys() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    return f"budget:daily:{now:%Y-%m-%d}", f"budget:monthly:{now:%Y-%m}"


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Vượt budget ngày hoặc tháng → HTTP 402."""
    if r is None:
        return
    daily_key, monthly_key = _budget_keys()
    try:
        daily_spent = float(r.get(daily_key) or 0.0)
        monthly_spent = float(r.get(monthly_key) or 0.0)
    except Exception:
        return

    if daily_spent >= settings.daily_budget_usd or monthly_spent >= settings.monthly_budget_usd:
        raise HTTPException(
            status_code=402,
            detail="LLM budget exceeded",
        )


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí request vào Redis và trả về chi phí."""
    cost = (input_tokens / 1000.0) * PRICE_INPUT_PER_1K + (
        output_tokens / 1000.0
    ) * PRICE_OUTPUT_PER_1K

    if r is not None:
        daily_key, monthly_key = _budget_keys()
        try:
            pipe = r.pipeline()
            pipe.incrbyfloat(daily_key, cost)
            pipe.expire(daily_key, 2 * 24 * 3600)
            pipe.incrbyfloat(monthly_key, cost)
            pipe.expire(monthly_key, 32 * 24 * 3600)
            pipe.execute()
        except Exception:
            pass

    return cost
