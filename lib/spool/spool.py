from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Callable, Sequence

logger = logging.getLogger(__name__)

# Bump on any change to `SCHEMA`. A spool file written by a different version
# is discarded rather than migrated - see `_apply_schema`.
SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS outbox (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    queued_at REAL NOT NULL,
    topic     TEXT NOT NULL,
    payload   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS outbox_queued_at ON outbox (queued_at);
"""


@dataclass(frozen=True)
class SpooledMessage:
    """One message waiting for the uplink, with the topic it was meant for."""

    id: int
    queued_at: float
    topic: str
    payload: str


class Spool:
    """A durable FIFO queue of MQTT messages, backed by one SQLite file.

    SQLite is in the standard library, needs no daemon, and commits
    transactionally - so a message that was accepted here is still here after
    the battery is pulled mid-drive, which is exactly when the uplink is down
    and the samples matter most.

    Delivered rows are deleted rather than flagged `sent`. A delivered message
    is already durable in Postgres, and the failure this guards against is a
    full SD card taking the whole vehicle down: what has to be bounded is the
    file, not the history.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        max_rows: int = 10_000,
        max_age_seconds: float = 7 * 24 * 3600,
        time_func: Callable[[], float] = time.time,
    ) -> None:
        self.path = str(path)
        self.max_rows = max_rows
        self.max_age_seconds = max_age_seconds
        self._now = time_func
        self._lock = Lock()
        self._connection: sqlite3.Connection | None = None
        self.dropped = 0

    # -- lifecycle ---------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Opened on first use so constructing a publisher touches no disk."""
        if self._connection is not None:
            return self._connection
        if self.path not in (":memory:", ""):
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        # The publisher thread writes and the API thread may flush; one
        # connection guarded by our own lock is simpler than one per thread.
        connection = sqlite3.connect(self.path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        # WAL survives a crash mid-write; synchronous=FULL means a commit has
        # reached the card before we call the message ours. At one message
        # every few seconds the extra fsync costs nothing worth counting.
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        self._apply_schema(connection)
        self._connection = connection
        return connection

    @staticmethod
    def _apply_schema(connection: sqlite3.Connection) -> None:
        """Create the table, discarding a spool written by another version.

        `CREATE TABLE IF NOT EXISTS` silently keeps an older table, so a
        changed schema would only surface as a failing INSERT on a rover that
        already had a spool - at the moment the spool matters most. The stored
        `user_version` is checked instead, and a mismatch drops the table.

        Throwing the backlog away on upgrade is the right trade here and not a
        compromise: the spool is a capped buffer of messages that are already
        in Postgres or a few minutes from it, so the cost is a small gap in
        history. Anything that has to survive a schema change does not belong
        in it.
        """
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version != SCHEMA_VERSION:
            if version != 0:
                logger.warning(
                    "Telemetry spool schema is v%d, expected v%d - discarding the backlog",
                    version,
                    SCHEMA_VERSION,
                )
            connection.execute("DROP TABLE IF EXISTS outbox")
        # `executescript` commits whatever is open, so this is not one
        # transaction. It does not need to be: the version is stamped last, so
        # a crash part-way leaves the old version and the next open repeats
        # the whole thing.
        connection.executescript(SCHEMA)
        # No placeholders in a PRAGMA; the value is our own constant.
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION:d}")
        connection.commit()

    def close(self) -> None:
        with self._lock:
            if self._connection is None:
                return
            self._connection.close()
            self._connection = None

    # -- queue -------------------------------------------------------------

    def append(self, topic: str, payload: str) -> int:
        """Store one message and return its id. Trims to the retention cap."""
        with self._lock:
            connection = self._connect()
            with connection:
                cursor = connection.execute(
                    "INSERT INTO outbox (queued_at, topic, payload) VALUES (?, ?, ?)",
                    (self._now(), topic, payload),
                )
                self._trim(connection)
            return int(cursor.lastrowid)

    def pending(self, limit: int) -> list[SpooledMessage]:
        """The oldest `limit` messages. Order is the order they were queued."""
        with self._lock:
            connection = self._connect()
            rows = connection.execute(
                "SELECT id, queued_at, topic, payload FROM outbox ORDER BY id LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            SpooledMessage(
                id=row["id"],
                queued_at=row["queued_at"],
                topic=row["topic"],
                payload=row["payload"],
            )
            for row in rows
        ]

    def discard(self, ids: Sequence[int]) -> None:
        """Forget messages the broker has acknowledged."""
        if not ids:
            return
        with self._lock:
            connection = self._connect()
            with connection:
                connection.executemany("DELETE FROM outbox WHERE id = ?", [(i,) for i in ids])

    def depth(self) -> int:
        """How many messages are still waiting."""
        with self._lock:
            connection = self._connect()
            return int(connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0])

    # -- retention ---------------------------------------------------------

    def _trim(self, connection: sqlite3.Connection) -> None:
        """Drop the oldest messages once the spool is too old or too long.

        Newest-wins: during a long outage the recent samples are the ones that
        explain what went wrong, and an unbounded spool fills the card.
        """
        dropped = 0
        if self.max_age_seconds > 0:
            cutoff = self._now() - self.max_age_seconds
            dropped += connection.execute(
                "DELETE FROM outbox WHERE queued_at < ?", (cutoff,)
            ).rowcount
        if self.max_rows > 0:
            dropped += connection.execute(
                "DELETE FROM outbox WHERE id NOT IN "
                "(SELECT id FROM outbox ORDER BY id DESC LIMIT ?)",
                (self.max_rows,),
            ).rowcount
        if dropped > 0:
            self.dropped += dropped
            logger.warning(
                "Telemetry spool full: dropped %d oldest message(s) (%d total)",
                dropped,
                self.dropped,
            )
