from __future__ import annotations

from typing import Any, Sequence

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select

from apps.db import VehicleStatusEvent
from apps.db.session import Database

MAX_LIMIT = 500


class TelemetryService:
    """Writes and reads vehicle status history in Postgres."""

    def __init__(self, db: Database) -> None:
        self._db = db

    @property
    def configured(self) -> bool:
        return self._db.configured

    def record_snapshot(self, snapshot: dict[str, Any]) -> VehicleStatusEvent:
        event = VehicleStatusEvent(
            recorded_at=snapshot["timestamp"],
            service=snapshot["service"],
            overall_status=snapshot["overall_status"],
            motor_device=snapshot.get("motor_device"),
            fc_device=snapshot.get("fc_device"),
            # jsonable_encoder already flattens the dataclasses and turns
            # datetimes into ISO strings, which is what JSONB needs.
            components=jsonable_encoder(snapshot.get("components", {})),
            motor_feedback=jsonable_encoder(snapshot.get("motor_feedback", [])),
        )
        with self._db.session_scope() as session:
            session.add(event)
        return event

    def recent(self, limit: int = 50) -> Sequence[VehicleStatusEvent]:
        limit = max(1, min(limit, MAX_LIMIT))
        statement = (
            select(VehicleStatusEvent).order_by(VehicleStatusEvent.recorded_at.desc()).limit(limit)
        )
        with self._db.session_scope() as session:
            return list(session.scalars(statement))
