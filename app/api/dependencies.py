"""FastAPI dependency providers for database sessions and application services."""

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db import create_database_engine, create_session_factory
from app.features.document_generation import DocumentGenerationService
from app.services import (
    ApplicationPipelineService,
    ApplicationTrackerService,
    JobUrlPipelineService,
)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Create a cached runtime session factory from `DATABASE_URL`."""
    database_url = Settings.from_env().database_url
    if not database_url:
        raise RuntimeError("DATABASE_URL is required to use database-backed API endpoints")
    engine = create_database_engine(database_url)
    return create_session_factory(engine)


def get_db() -> Iterator[Session]:
    """Yield one request-scoped SQLAlchemy session."""
    with get_session_factory()() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise


DatabaseSession = Annotated[Session, Depends(get_db)]


def get_application_pipeline_service(db: DatabaseSession) -> ApplicationPipelineService:
    """Provide the manual end-to-end pipeline service."""
    return ApplicationPipelineService(db)


def get_job_url_pipeline_service(db: DatabaseSession) -> JobUrlPipelineService:
    """Provide the Playwright URL extraction pipeline service."""
    return JobUrlPipelineService(db)


def get_document_generation_service(db: DatabaseSession) -> DocumentGenerationService:
    """Provide generated-document metadata access."""
    return DocumentGenerationService(db)


def get_application_tracker_service(db: DatabaseSession) -> ApplicationTrackerService:
    """Provide lightweight application tracking operations."""
    return ApplicationTrackerService(db)
