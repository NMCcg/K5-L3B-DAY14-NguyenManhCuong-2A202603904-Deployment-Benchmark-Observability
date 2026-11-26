"""Production AI Agent — Part 6 Final Project."""
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import redis_healthy
from utils.mock_llm import ask as llm_ask


class JsonFormatter(logging.Formatter):
    """Định dạng mỗi dòng log thành một JSON object hợp lệ."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lvl": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        return json.dumps(payload, ensure_ascii=False)


def _setup_logging() -> logging.Logger:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("agent")
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    root.propagate = False
    return root


logger = _setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(json.dumps({"event": "startup", "env": settings.environment, "port": settings.port}))
    yield
    logger.info(json.dumps({"event": "shutdown"}))


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(json.dumps({"event": "unhandled_error", "path": request.url.path}))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = None


@app.get("/health")
def health():
    """Liveness probe: luôn trả 200 khi process còn chạy."""
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Readiness probe: 200 khi Redis sẵn sàng, 503 khi mất kết nối Redis."""
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis unavailable")
    return {"ready": True}


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    start = time.perf_counter()
    check_rate_limit(api_key)
    check_budget()

    answer = llm_ask(body.question)
    input_tokens = max(10, len(body.question.split()) * 2)
    output_tokens = max(10, len(answer.split()) * 2)
    cost = record_cost(input_tokens, output_tokens)

    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        json.dumps(
            {
                "event": "request",
                "path": "/ask",
                "status": 200,
                "ms": elapsed_ms,
                "cost_usd": round(cost, 6),
            }
        )
    )
    return {"question": body.question, "answer": answer}
