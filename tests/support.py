"""Shared test infrastructure for database-backed tests."""

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base


def create_test_engine() -> Engine:
    """Create a reusable in-memory SQLite engine with foreign keys enabled."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine


def create_test_session(engine: Engine) -> Session:
    """Create a test session bound to an isolated engine."""
    return sessionmaker(bind=engine, expire_on_commit=False)()
