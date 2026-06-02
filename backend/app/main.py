"""FastAPI application entry point for careerOS."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.errors import register_exception_handlers
from app.api.routes import applications, documents, health, job_url_extraction, pipeline

APP_NAME = "careerOS"
APP_VERSION = __version__
LOCAL_FRONTEND_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def create_app() -> FastAPI:
    """Create the FastAPI application and register v1 HTTP adapters."""
    application = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        description="AI-powered career operating system backend.",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=LOCAL_FRONTEND_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(application)
    application.include_router(health.router)
    application.include_router(pipeline.router)
    application.include_router(job_url_extraction.router)
    application.include_router(documents.router)
    application.include_router(applications.router)
    return application


app = create_app()
