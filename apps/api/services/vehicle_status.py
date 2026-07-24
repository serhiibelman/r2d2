from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Event, Lock, Thread
from typing import Any

from pymavlink import mavutil
from serial import SerialException

from apps.ddsm115 import DDS115
from settings import DEVICE, FC_BAUDRATE, FC_DEVICE, LEFT_SIDE, RIGHT_SIDE


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ComponentSnapshot:
    configured: bool
    connected: bool
    detail: str
    checked_at: datetime


class VehicleStatusService:
    def __init__(
        self,
        *,
        motor_device: str | None = DEVICE,
        fc_device: str | None = FC_DEVICE,
        fc_baudrate: int = FC_BAUDRATE,
        probe_interval_seconds: float = 2.0,
    ):
        self.motor_device = motor_device
        self.fc_device = fc_device
        self.fc_baudrate = fc_baudrate
        self.probe_interval_seconds = probe_interval_seconds
        self._stop_event = Event()
        self._lock = Lock()
        self._thread: Thread | None = None
        self._components = {
            "motor_bus": ComponentSnapshot(
                configured=bool(self.motor_device),
                connected=False,
                detail="Probe has not run yet",
                checked_at=utc_now(),
            ),
            "flight_controller": ComponentSnapshot(
                configured=bool(self.fc_device),
                connected=False,
                detail="Probe has not run yet",
                checked_at=utc_now(),
            ),
        }
        self._motor_feedback = [
            {"motor_id": motor_id, "rpm": None, "current_raw": None}
            for motor_id in LEFT_SIDE + RIGHT_SIDE
        ]

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = Thread(target=self._probe_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.probe_interval_seconds + 1.0)
            self._thread = None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            components = {
                name: asdict(component) for name, component in self._components.items()
            }
            motor_feedback = list(self._motor_feedback)

        return {
            "service": "r2d2-vehicle-api",
            "overall_status": self._overall_status(components),
            "timestamp": utc_now(),
            "motor_device": self.motor_device,
            "fc_device": self.fc_device,
            "motor_ids": {
                "left": list(LEFT_SIDE),
                "right": list(RIGHT_SIDE),
            },
            "components": components,
            "motor_feedback": motor_feedback,
        }

    def _probe_loop(self) -> None:
        while not self._stop_event.is_set():
            motor_bus = self._probe_motor_bus()
            flight_controller = self._probe_flight_controller()

            with self._lock:
                self._components["motor_bus"] = motor_bus
                self._components["flight_controller"] = flight_controller

            self._stop_event.wait(self.probe_interval_seconds)

    def _probe_motor_bus(self) -> ComponentSnapshot:
        checked_at = utc_now()
        if not self.motor_device:
            return ComponentSnapshot(
                configured=False,
                connected=False,
                detail="DEVICE is not configured",
                checked_at=checked_at,
            )

        motor = None
        try:
            motor = DDS115(device=self.motor_device)
        except (RuntimeError, SerialException, ValueError) as exc:
            return ComponentSnapshot(
                configured=True,
                connected=False,
                detail=str(exc),
                checked_at=checked_at,
            )
        finally:
            if motor is not None:
                motor.close()

        return ComponentSnapshot(
            configured=True,
            connected=True,
            detail="Serial device opened successfully; live motor telemetry is not wired yet",
            checked_at=checked_at,
        )

    def _probe_flight_controller(self) -> ComponentSnapshot:
        checked_at = utc_now()
        if not self.fc_device:
            return ComponentSnapshot(
                configured=False,
                connected=False,
                detail="FC_DEVICE is not configured",
                checked_at=checked_at,
            )

        link = None
        try:
            link = mavutil.mavlink_connection(self.fc_device, baud=self.fc_baudrate)
            heartbeat = link.wait_heartbeat(timeout=1)
        except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
            return ComponentSnapshot(
                configured=True,
                connected=False,
                detail=str(exc),
                checked_at=checked_at,
            )
        finally:
            if link is not None and hasattr(link, "close"):
                link.close()

        system_id = getattr(heartbeat, "get_srcSystem", lambda: None)()
        return ComponentSnapshot(
            configured=True,
            connected=True,
            detail=f"Heartbeat received from system {system_id}",
            checked_at=checked_at,
        )

    @staticmethod
    def _overall_status(components: dict[str, dict[str, Any]]) -> str:
        if all(component["configured"] and component["connected"] for component in components.values()):
            return "ok"
        return "degraded"
