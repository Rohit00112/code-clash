"""Database configuration and session management"""

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# PostgreSQL engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True,
    echo=settings.DEBUG
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()

# Import models after Base is defined so metadata is populated.
from app import models  # noqa: E402,F401


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for getting database session
    
    Yields:
        Session: Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database according to configured strategy.

    DB_INIT_MODE:
      - migrate: require alembic_version table (migration-first discipline)
      - create_all: legacy behavior for local/dev bootstrap
      - off: skip initialization check
    """
    mode = settings.DB_INIT_MODE.lower().strip()
    if mode == "off":
        logger.info("DB initialization check skipped (DB_INIT_MODE=off)")
        return

    if mode == "create_all":
        Base.metadata.create_all(bind=engine)
        logger.warning("Using create_all database initialization (recommended only for local development).")
        return

    if mode == "migrate":
        with engine.connect() as conn:
            if engine.dialect.name == "postgresql":
                version_table_exists = conn.execute(
                    text("SELECT to_regclass('public.alembic_version')")
                ).scalar()
                exists = bool(version_table_exists)
            elif engine.dialect.name == "sqlite":
                version_table_exists = conn.execute(
                    text(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'"
                    )
                ).fetchone()
                exists = bool(version_table_exists)
            else:
                exists = "alembic_version" in inspect(conn).get_table_names()
            if settings.DB_REQUIRE_HEAD and not exists:
                raise RuntimeError(
                    "Migration table missing. Run Alembic migrations before starting the API."
                )
        logger.info("Migration metadata detected.")
        return

    raise RuntimeError(f"Unknown DB_INIT_MODE: {settings.DB_INIT_MODE}")
