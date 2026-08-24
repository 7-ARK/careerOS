"""Privacy-safe structured telemetry for HTTP requests and analysis stages."""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from time import perf_counter
from uuid import uuid4

from fastapi import Request, Response

logger = logging.getLogger("careeros.telemetry")


async def log_http_request(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Log request metadata without reading or recording private request bodies."""
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    started = perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        logger.info(
            json.dumps(
                {
                    "event": "http_request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "latency_ms": round((perf_counter() - started) * 1000),
                },
                separators=(",", ":"),
            )
        )


def log_analysis_stage(
    *,
    run_id: object,
    stage: object,
    status: str,
    provider: str,
    latency_ms: int,
    model: str | None = None,
    estimated_cost_usd: object = 0,
    error_type: str | None = None,
) -> None:
    """Record bounded stage telemetry without prompts, resumes, or contact data."""
    logger.info(
        json.dumps(
            {
                "event": "career_analysis_stage",
                "analysis_run_id": str(run_id),
                "stage": str(stage),
                "status": status,
                "provider": provider,
                "model": model,
                "latency_ms": latency_ms,
                "estimated_cost_usd": str(estimated_cost_usd),
                "error_type": error_type,
            },
            separators=(",", ":"),
        )
    )
