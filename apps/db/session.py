from __future__ import annotations

import logging
from contextlib import contextmanager
from threading import Lock
from typing import Any, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from apps.db.config import DatabaseConfig

logger = logging.getLogger(__name__)

NOT_CONFIGURED = "DATABASE_URL is not set"


def normalise_url(url: str) -> URL:
    """Force the psycopg (v3) driver, whatever dialect the .env asked for.

    A bare ``postgresql://`` URL makes SQLAlchemy reach for psycopg2, which has
    no 32-bit ARM wheels and would have to be compiled on the Pi.
    """
    parsed = make_url(url)
    if parsed.drivername in {"postgres", "postgresql"}:
        parsed = parsed.set(drivername="postgresql+psycopg")
    return parsed


class Database:
    """Owns the engine and hands out sessions.

    Nothing here raises at import time: with no ``DATABASE_URL`` the vehicle
    runs exactly as it did before, and every database-backed route answers 503.
    """

    def __init__(self, config: DatabaseConfig | None = None) -> None:
        self.config = config or DatabaseConfig()
        self._url = normalise_url(self.config.url) if self.config.url else None
        self._engine: Engine | None = None
        self._session_factory: sessionmaker[Session] | None = None
        self._lock = Lock()

    @property
    def configured(self) -> bool:
        return self._url is not None

    @property
    def url(self) -> URL | None:
        return self._url

    @property
    def safe_url(self) -> str | None:
        """The URL with the password masked, safe to put in an API response."""
        return self._url.render_as_string(hide_password=True) if self._url else None

    def _connect_args(self) -> dict[str, Any]:
        args: dict[str, Any] = {
            "connect_timeout": self.config.connect_timeout,
            "application_name": "r2d2-vehicle-api",
        }
        if self.config.sslmode:
            args["sslmode"] = self.config.sslmode
        if self.config.sslrootcert:
            args["sslrootcert"] = self.config.sslrootcert
        if self.config.statement_timeout_ms:
            args["options"] = f"-c statement_timeout={self.config.statement_timeout_ms}"
        return args

    @property
    def engine(self) -> Engine:
        if not self._url:
            raise RuntimeError(NOT_CONFIGURED)
        with self._lock:
            if self._engine is None:
                self._engine = create_engine(
                    self._url,
                    echo=self.config.echo,
                    pool_size=self.config.pool_size,
                    max_overflow=self.config.max_overflow,
                    pool_recycle=self.config.pool_recycle,
                    # Wi-Fi drops and RDS failovers leave dead sockets in the
                    # pool; pre_ping trades one round trip for a clear error.
                    pool_pre_ping=True,
                    connect_args=self._connect_args(),
                )
                self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)
            return self._engine

    def session(self) -> Session:
        self.engine  # build the factory on first use
        assert self._session_factory is not None
        return self._session_factory()

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        session = self.session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def check(self) -> tuple[bool, str]:
        """``SELECT 1`` against the database. Blocks - call it off the request path.

        The returned detail carries the exception class only. Driver errors name
        the RDS endpoint and the database user, and this ends up in an
        unauthenticated ``/health`` response, so the full text goes to the log.
        """
        if not self.configured:
            return False, NOT_CONFIGURED
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError as error:
            logger.warning("Database probe failed", exc_info=error)
            return False, f"Unreachable ({type(error).__name__}); see API logs"
        return True, "Connected"

    def dispose(self) -> None:
        with self._lock:
            if self._engine is not None:
                self._engine.dispose()
                self._engine = None
                self._session_factory = None


database = Database()
