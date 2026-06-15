"""Consistent JSON error responses for the careerOS API."""

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.services import (
    ApplicationRecordNotFoundError,
    DuplicateUserError,
    GeneratedDocumentNotFoundError,
    InvalidCredentialsError,
    JobAnalysisNotFoundError,
    JobDescriptionNotFoundError,
    PipelineExecutionError,
    ProfileNotFoundError,
    ResumeAnalysisNotFoundError,
    ResumeDraftNotFoundError,
)

NOT_FOUND_EXCEPTIONS = (
    ApplicationRecordNotFoundError,
    GeneratedDocumentNotFoundError,
    JobAnalysisNotFoundError,
    JobDescriptionNotFoundError,
    ProfileNotFoundError,
    ResumeAnalysisNotFoundError,
    ResumeDraftNotFoundError,
)


def register_exception_handlers(app: FastAPI) -> None:
    """Register stable API error envelopes."""
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(PipelineExecutionError, pipeline_error_handler)
    for exception_type in NOT_FOUND_EXCEPTIONS:
        app.add_exception_handler(exception_type, not_found_error_handler)
    app.add_exception_handler(DuplicateUserError, duplicate_user_error_handler)
    app.add_exception_handler(InvalidCredentialsError, invalid_credentials_error_handler)


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Return validation failures with field-level details."""
    return _error_response(
        422,
        code="validation_error",
        message="Request validation failed.",
        details=jsonable_encoder(exc.errors()),
    )


async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    """Wrap explicit HTTP errors in the API error envelope."""
    detail = exc.detail
    message = detail if isinstance(detail, str) else "Request failed."
    return _error_response(
        exc.status_code,
        code="http_error",
        message=message,
        details=None if isinstance(detail, str) else detail,
    )


async def pipeline_error_handler(_: Request, exc: PipelineExecutionError) -> JSONResponse:
    """Return stage-aware pipeline failures."""
    return _error_response(
        500,
        code="pipeline_execution_error",
        message=str(exc),
        details={"stage": str(exc.stage)},
    )


async def not_found_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """Return service-level missing-record failures."""
    return _error_response(404, code="not_found", message=str(exc))


async def duplicate_user_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """Return a client-safe duplicate registration response."""
    return _error_response(400, code="duplicate_user", message=str(exc))


async def invalid_credentials_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """Return a generic authentication failure without account enumeration."""
    return _error_response(401, code="invalid_credentials", message=str(exc))


def _error_response(
    status_code: int,
    *,
    code: str,
    message: str,
    details: Any | None = None,
) -> JSONResponse:
    """Build one consistent error response body."""
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JSONResponse(status_code=status_code, content={"error": error})
