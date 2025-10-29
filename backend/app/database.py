from __future__ import annotations

from contextlib import contextmanager
from typing import Optional, Tuple, Union

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings


_settings = get_settings()
_primary_engine: Optional[Engine] = None
_secondary_engine: Optional[Engine] = None
_PrimarySession: Optional[sessionmaker] = None
_SecondarySession: Optional[sessionmaker] = None
_primary_url: Optional[str] = _settings.sqlalchemy_database_uri
_secondary_url: Optional[str] = None
_configured: bool = _settings.environment != "development"


def _create_engine(url: str) -> Engine:
    return create_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


def configure_engines(primary_url: str, secondary_url: Optional[str] = None) -> Engine:
    global _primary_engine, _secondary_engine, _PrimarySession, _SecondarySession, _primary_url, _secondary_url, _configured
    _primary_url = primary_url
    _secondary_url = secondary_url

    if _primary_engine is not None:
        _primary_engine.dispose()
    _primary_engine = _create_engine(primary_url)
    _PrimarySession = sessionmaker(bind=_primary_engine, autoflush=False, expire_on_commit=False)

    if secondary_url:
        if _secondary_engine is not None:
            _secondary_engine.dispose()
        _secondary_engine = _create_engine(secondary_url)
        _SecondarySession = sessionmaker(bind=_secondary_engine, autoflush=False, expire_on_commit=False)
    else:
        if _secondary_engine is not None:
            _secondary_engine.dispose()
        _secondary_engine = None
        _SecondarySession = None

    _configured = True
    return _primary_engine


def get_engine() -> Engine:
    global _primary_engine
    if _primary_engine is None:
        if not _primary_url or not _configured:
            raise RuntimeError("Primary database URL is not configured. Please configure it via settings before use.")
        configure_engines(_primary_url, _secondary_url)
    return _primary_engine


def get_secondary_engine() -> Optional[Engine]:
    return _secondary_engine


def _replicate_changes(source_session: Session, target_session: Session) -> None:
    # Merge new and dirty objects
    merged: set[type] = set()
    for collection in (source_session.new, source_session.dirty):
        for obj in collection:
            state = inspect(obj)
            if not state.identity:
                continue
            target_session.merge(obj, load=False)
            merged.add(type(obj))

    # Handle deletes
    for obj in source_session.deleted:
        state = inspect(obj)
        identity = state.identity
        if not identity:
            continue
        identity_key: Union[Tuple, object]
        if len(identity) == 1:
            identity_key = identity[0]
        else:
            identity_key = identity
        target_obj = target_session.get(type(obj), identity_key)
        if target_obj:
            target_session.delete(target_obj)

    target_session.flush()


@contextmanager
def session_scope() -> Session:
    if _PrimarySession is None:
        if not _primary_url:
            raise RuntimeError("Primary database URL is not configured")
        configure_engines(_primary_url, _secondary_url)

    if _PrimarySession is None:
        raise RuntimeError("Primary session factory not initialised")

    primary_session = _PrimarySession()
    secondary_session: Optional[Session] = _SecondarySession() if _SecondarySession else None

    try:
        yield primary_session
        primary_session.flush()
        if secondary_session:
            _replicate_changes(primary_session, secondary_session)
            secondary_session.commit()
        primary_session.commit()
    except Exception:
        primary_session.rollback()
        if secondary_session:
            secondary_session.rollback()
        raise
    finally:
        primary_session.close()
        if secondary_session:
            secondary_session.close()


def get_db():
    with session_scope() as session:
        yield session
