from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Event, Lock, Thread

from apps.db.session import NOT_CONFIGURED, Database


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class DatabaseHealth:
    configured: bool
    connected: bool
    detail: str
    checked_at: datetime


class DatabaseHealthMonitor:
    """Probes the database on a background thread so /health never blocks.

    ``/health`` is what an operator polls when things are already broken, so it
    must not wait on an unreachable RDS: readers get the last completed probe
    and the timestamp of that probe, never a fresh timestamp on a stale result.
    """

    def __init__(self, db: Database, interval_seconds: float | None = None) -> None:
        self._db = db
        self._interval = (
            interval_seconds if interval_seconds is not None else db.config.health_interval_seconds
        )
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._lock = Lock()
        self._health = DatabaseHealth(
            configured=db.configured,
            connected=False,
            detail="Probe has not run yet" if db.configured else NOT_CONFIGURED,
            checked_at=utc_now(),
        )

    def start(self) -> None:
        if not self._db.configured:
            return
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = Thread(target=self._probe_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            # The loop waits on the event, so the only delay left is a probe
            # already in flight - bounded by the connect timeout.
            self._thread.join(timeout=self._db.config.connect_timeout + 1)
            self._thread = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def snapshot(self) -> DatabaseHealth:
        with self._lock:
            return self._health

    def _probe_loop(self) -> None:
        while not self._stop_event.is_set():
            connected, detail = self._db.check()
            with self._lock:
                self._health = DatabaseHealth(
                    configured=True,
                    connected=connected,
                    detail=detail,
                    checked_at=utc_now(),
                )
            self._stop_event.wait(self._interval)
