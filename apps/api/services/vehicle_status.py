from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from time import sleep
from threading import Event, Lock, Thread
from typing import Any, Callable

from pymavlink import mavutil
from serial import SerialException

from lib.ddsm115 import DDS115
from apps.vehicle_control.vehicle_controller import LOOP_INTERVAL, MAX_RPM, VehicleController
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
        motor_factory: Callable[..., DDS115] = DDS115,
        sleep_func: Callable[[float], None] = sleep,
    ):
        self.motor_device = motor_device
        self.fc_device = fc_device
        self.fc_baudrate = fc_baudrate
        self.probe_interval_seconds = probe_interval_seconds
        self._motor_factory = motor_factory
        self._sleep = sleep_func
        self._stop_event = Event()
        self._lock = Lock()
        self._motor_bus_lock = Lock()
        self._thread: Thread | None = None
        self._current_command_rpm = 0
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

    def start_motors(self, rpm: int) -> dict[str, Any]:
        self._validate_rpm(rpm)
        self._run_motor_ramp(target_rpm=rpm)
        return self._motor_command_response(
            action="start",
            target_rpm=rpm,
            detail=f"All motors ramped to {rpm} rpm",
        )

    def stop_motors(self) -> dict[str, Any]:
        self._run_motor_ramp(target_rpm=0)
        return self._motor_command_response(
            action="stop",
            target_rpm=0,
            detail="All motors ramped down to 0 rpm",
        )

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

        with self._motor_bus_lock:
            motor = None
            try:
                motor = self._motor_factory(device=self.motor_device)
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

    def _run_motor_ramp(self, *, target_rpm: int) -> None:
        if not self.motor_device:
            self._set_motor_component(connected=False, detail="DEVICE is not configured")
            raise RuntimeError("Motor device is not configured")

        with self._motor_bus_lock:
            motor = None
            try:
                motor = self._motor_factory(device=self.motor_device)
            except (RuntimeError, SerialException, ValueError) as exc:
                self._set_motor_component(connected=False, detail=str(exc))
                raise RuntimeError(str(exc)) from exc

            try:
                current_rpm = self._current_rpm()
                while current_rpm != target_rpm:
                    current_rpm = int(VehicleController._ramp_toward(current_rpm, target_rpm))
                    self._send_motor_commands(motor, current_rpm)
                    if current_rpm != target_rpm:
                        self._sleep(LOOP_INTERVAL)
            finally:
                motor.close()

        self._set_motor_component(
            connected=True,
            detail=f"Serial device opened successfully; last commanded base rpm is {target_rpm}",
        )

    def _send_motor_commands(self, motor: DDS115, base_rpm: int) -> None:
        for motor_id in LEFT_SIDE:
            motor.send_rpm(motor_id, rpm=base_rpm)
        for motor_id in RIGHT_SIDE:
            motor.send_rpm(motor_id, rpm=base_rpm * (-1))

        with self._lock:
            self._current_command_rpm = base_rpm
            self._motor_feedback = [
                {
                    "motor_id": motor_id,
                    "rpm": base_rpm if motor_id in LEFT_SIDE else base_rpm * (-1),
                    "current_raw": None,
                }
                for motor_id in LEFT_SIDE + RIGHT_SIDE
            ]

    def _motor_command_response(self, *, action: str, target_rpm: int, detail: str) -> dict[str, Any]:
        return {
            "service": "r2d2-vehicle-api",
            "action": action,
            "target_rpm": target_rpm,
            "current_rpm": self._current_rpm(),
            "detail": detail,
            "timestamp": utc_now(),
        }

    def _current_rpm(self) -> int:
        with self._lock:
            return self._current_command_rpm

    def _set_motor_component(self, *, connected: bool, detail: str) -> None:
        with self._lock:
            self._components["motor_bus"] = ComponentSnapshot(
                configured=bool(self.motor_device),
                connected=connected,
                detail=detail,
                checked_at=utc_now(),
            )

    @staticmethod
    def _validate_rpm(rpm: int) -> None:
        if not -MAX_RPM <= rpm <= MAX_RPM:
            raise ValueError(f"rpm must be between {-MAX_RPM} and {MAX_RPM}")
