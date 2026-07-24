from datetime import datetime, timezone

from fastapi.testclient import TestClient

from apps.api.main import create_app


class FakeVehicleStatusService:
    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

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
