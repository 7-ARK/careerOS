"""FastAPI application entry point for careerOS."""

from fastapi import FastAPI

from app import __version__
from app.api.errors import register_exception_handlers
from app.api.routes import applications, documents, health, job_url_extraction, pipeline

APP_NAME = "careerOS"
APP_VERSION = __version__


def create_app() -> FastAPI:
    """Create the FastAPI application and register v1 HTTP adapters."""
    application = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        description="AI-powered career operating system backend.",
    )
    register_exception_handlers(application)
    application.include_router(health.router)
    application.include_router(pipeline.router)
    application.include_router(job_url_extraction.router)
    application.include_router(documents.router)
    application.include_router(applications.router)
    return application


app = create_app()
