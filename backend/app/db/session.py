"""Database engine and session lifecycle helpers."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_database_engine(database_url: str, *, echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine for the configured database."""
    engine = create_engine(database_url, echo=echo)
    if engine.dialect.name == "postgresql":
        from pgvector.psycopg import register_vector
        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def _register_pgvector(dbapi_connection: object, _connection_record: object) -> None:
            register_vector(dbapi_connection)

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create an injectable SQLAlchemy session factory."""
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Yield a session and guarantee transaction cleanup."""
    with factory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
