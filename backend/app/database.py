from __future__ import annotations

from contextlib import contextmanager
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings


_settings = get_settings()
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None
_connection_url: str = _settings.sqlalchemy_database_uri


def _create_engine(url: str) -> Engine:
    return create_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


def configure_engine(url: str) -> Engine:
    global _engine, _SessionLocal, _connection_url
    _connection_url = url
    if _engine is not None:
        _engine.dispose()
    _engine = _create_engine(url)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        configure_engine(_connection_url)
    return _engine


@contextmanager
def session_scope() -> Session:
    engine = get_engine()
    if _SessionLocal is None:
        raise RuntimeError("Session factory not initialised")
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db():
    with session_scope() as session:
        yield session
