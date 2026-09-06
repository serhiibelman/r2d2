from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lib.db.base import Base


class VehicleStatusEvent(Base):
    """
    A stored copy of the snapshot ``/status`` returns.

    The vehicle keeps running when the database is unreachable, so this table
    is a history log, never the source of truth for the current state.
    """

    __tablename__ = "vehicle_status_events"
    __table_args__ = (Index("ix_vehicle_status_events_recorded_at", "recorded_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    service: Mapped[str] = mapped_column(String(64), nullable=False)
    overall_status: Mapped[str] = mapped_column(String(32), nullable=False)
    motor_device: Mapped[str | None] = mapped_column(String(255))
    fc_device: Mapped[str | None] = mapped_column(String(255))
    components: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    motor_feedback: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
