from datetime import datetime, timezone

from fastapi.testclient import TestClient

from apps.api.main import create_app


class FakeVehicleStatusService:
    def __init__(self) -> None:
        self.started_rpms: list[int] = []
        self.stop_calls = 0

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def start_motors(self, rpm: int) -> dict:
        self.started_rpms.append(rpm)
        now = datetime.now(timezone.utc)
        return {
            "service": "r2d2-vehicle-api",
            "action": "start",
            "target_rpm": rpm,
            "current_rpm": rpm,
            "detail": f"All motors ramped to {rpm} rpm",
            "timestamp": now,
        }

    def stop_motors(self) -> dict:
        self.stop_calls += 1
        now = datetime.now(timezone.utc)
        return {
            "service": "r2d2-vehicle-api",
            "action": "stop",
            "target_rpm": 0,
            "current_rpm": 0,
            "detail": "All motors ramped down to 0 rpm",
            "timestamp": now,
        }

    def snapshot(self) -> dict:
        now = datetime.now(timezone.utc)
        components = {
            "motor_bus": {
                "configured": True,
                "connected": True,
                "detail": "ok",
                "checked_at": now,
            },
            "flight_controller": {
                "configured": True,
                "connected": False,
                "detail": "timeout",
                "checked_at": now,
            },
        }
        return {
            "service": "r2d2-vehicle-api",
            "overall_status": "degraded",
            "timestamp": now,
            "motor_device": "/dev/ttyACM0",
            "fc_device": "/dev/serial0",
            "motor_ids": {"left": [3, 4], "right": [1, 2]},
            "components": components,
            "motor_feedback": [
                {"motor_id": 1, "rpm": None, "current_raw": None},
                {"motor_id": 2, "rpm": None, "current_raw": None},
            ],
        }


def test_health_endpoint() -> None:
    app = create_app(FakeVehicleStatusService())

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "r2d2-vehicle-api"
    assert payload["status"] == "degraded"
    assert "motor_bus" in payload["components"]


def test_status_endpoint() -> None:
    app = create_app(FakeVehicleStatusService())

    with TestClient(app) as client:
        response = client.get("/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["motor_ids"]["left"] == [3, 4]
    assert payload["motor_ids"]["right"] == [1, 2]
    assert payload["motor_feedback"][0]["motor_id"] == 1
    assert payload["motor_feedback"][0]["rpm"] is None


def test_start_motors_endpoint() -> None:
    service = FakeVehicleStatusService()
    app = create_app(service)

    with TestClient(app) as client:
        response = client.post("/motors/start", json={"rpm": 120})

    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "start"
    assert payload["target_rpm"] == 120
    assert service.started_rpms == [120]


def test_stop_motors_endpoint() -> None:
    service = FakeVehicleStatusService()
    app = create_app(service)

    with TestClient(app) as client:
        response = client.post("/motors/stop")

    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "stop"
    assert payload["current_rpm"] == 0
    assert service.stop_calls == 1
