"""FastAPI dependency providers for database sessions and application services."""

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.security import InvalidTokenError, decode_access_token
from app.db import create_database_engine, create_session_factory
from app.features.document_generation import DocumentGenerationService
from app.models import User
from app.repositories import UserRepository
from app.services import (
    ApplicationPipelineService,
    ApplicationTrackerService,
    AuthService,
    JobUrlPipelineService,
    KnowledgeBaseService,
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
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    db: DatabaseSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    """Authenticate a bearer token and load its current user."""
    settings = Settings.from_env()
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise credentials_error
    try:
        user_id = decode_access_token(
            credentials.credentials,
            secret_key=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
    except InvalidTokenError as exc:
        raise credentials_error from exc
    user = UserRepository(db).get(user_id)
    if user is None:
        raise credentials_error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_application_pipeline_service(db: DatabaseSession) -> ApplicationPipelineService:
    """Provide the manual end-to-end pipeline service."""
    return ApplicationPipelineService(db)


def get_auth_service(db: DatabaseSession) -> AuthService:
    """Provide account registration and login operations."""
    return AuthService(db)


def get_job_url_pipeline_service(db: DatabaseSession) -> JobUrlPipelineService:
    """Provide the Playwright URL extraction pipeline service."""
    return JobUrlPipelineService(db)


def get_document_generation_service(db: DatabaseSession) -> DocumentGenerationService:
    """Provide generated-document metadata access."""
    return DocumentGenerationService(db)


def get_application_tracker_service(db: DatabaseSession) -> ApplicationTrackerService:
    """Provide lightweight application tracking operations."""
    return ApplicationTrackerService(db)


def get_knowledge_base_service(db: DatabaseSession) -> KnowledgeBaseService:
    """Provide candidate knowledge-base profile management operations."""
    return KnowledgeBaseService(db)
