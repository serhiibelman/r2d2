from __future__ import annotations

from dataclasses import dataclass

from settings import (
    DATABASE_URL,
    DB_CONNECT_TIMEOUT,
    DB_ECHO,
    DB_MAX_OVERFLOW,
    DB_POOL_RECYCLE,
    DB_POOL_SIZE,
    DB_SSLMODE,
    DB_SSLROOTCERT,
    DB_STATEMENT_TIMEOUT_MS,
)


@dataclass(frozen=True)
class DatabaseConfig:
    """Everything one database connection needs, in one place.

    The defaults come from ``.env``; a second database, a read replica or a
    test container is expressed by building another config, never by changing
    the environment of the whole process.
    """

    url: str = DATABASE_URL
    sslmode: str = DB_SSLMODE
    sslrootcert: str = DB_SSLROOTCERT
    connect_timeout: int = DB_CONNECT_TIMEOUT
    statement_timeout_ms: int = DB_STATEMENT_TIMEOUT_MS
    pool_size: int = DB_POOL_SIZE
    max_overflow: int = DB_MAX_OVERFLOW
    pool_recycle: int = DB_POOL_RECYCLE
    echo: bool = DB_ECHO
