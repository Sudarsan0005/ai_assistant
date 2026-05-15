"""
app/database/connection.py
──────────────────────────
SQLAlchemy engine + session factory for the internal Postgres DB.
"""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from config.settings import get_settings

settings = get_settings()

engine = create_engine(
    settings.internal_db_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=settings.debug,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Context-manager variant for use outside FastAPI (e.g. sync jobs)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """Create all tables and rebuild legacy app schema when detected."""
    from app.models.tables import Base
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))

        inspector = inspect(conn)
        table_names = set(inspector.get_table_names())
        customer_columns = {col["name"] for col in inspector.get_columns("customers")} if "customers" in table_names else set()
        legacy_detected = (
            "data_sources" in table_names
            or "sync_jobs" in table_names
            or ("customers" in table_names and "customer_id" not in customer_columns)
        )

        if legacy_detected:
            Base.metadata.drop_all(bind=conn)
            conn.execute(text("DROP TABLE IF EXISTS data_sources CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS sync_jobs CASCADE"))

        conn.commit()
    Base.metadata.create_all(bind=engine)
