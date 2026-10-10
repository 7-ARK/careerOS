"""FastAPI application entry point for careerOS."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.errors import register_exception_handlers
from app.api.routes import (
    applications,
    auth,
    candidates,
    career_analysis,
    documents,
    health,
    job_url_extraction,
    pipeline,
)
from app.core.config import Settings
from app.core.observability import log_http_request

APP_NAME = "careerOS"
APP_VERSION = __version__
def create_app() -> FastAPI:
    """Create the FastAPI application and register v1 HTTP adapters."""
    application = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        description="AI-powered career operating system backend.",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(Settings.from_env().cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.middleware("http")(log_http_request)
    register_exception_handlers(application)
    application.include_router(health.router)
    application.include_router(auth.router)
    application.include_router(pipeline.router)
    application.include_router(job_url_extraction.router)
    application.include_router(documents.router)
    application.include_router(candidates.router)
    application.include_router(applications.router)
    application.include_router(career_analysis.router)
    application.include_router(career_analysis.jobs_router)
    return application


app = create_app()
