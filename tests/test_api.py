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


class FakeCameraService:
    def __init__(self, *, available: bool = True) -> None:
        self.available = available
        self.start_calls = 0
        self.stop_calls = 0
        self.slots = 0

    def _guard(self) -> None:
        if not self.available:
            raise RuntimeError("Camera is unavailable: no camera detected")

    def start(self) -> dict:
        self._guard()
        self.start_calls += 1
        return self._command("start", "Camera capture is running", running=True)

    def stop(self) -> dict:
        self.stop_calls += 1
        return self._command("stop", "Camera capture stopped", running=False)

    def acquire_client_slot(self) -> None:
        self._guard()
        self.slots += 1

    def release_client_slot(self) -> None:
        self.slots -= 1

    def next_frame(self, last_seq: int):
        frames = [b"first", b"second"]
        next_seq = last_seq + 1
        if next_seq >= len(frames):
            return None
        return next_seq, frames[next_seq]

    def capture_frame(self) -> bytes:
        self._guard()
        return b"jpeg-bytes"

    def snapshot(self) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "service": "r2d2-vehicle-api",
            "timestamp": now,
            "running": self.available,
            "clients": 0,
            "width": 640,
            "height": 480,
            "framerate": 20,
            "jpeg_quality": 80,
            "encoder": "hardware",
            "frames_captured": 12,
            "last_frame_at": now,
            "component": {
                "configured": True,
                "connected": self.available,
                "detail": "ok",
                "checked_at": now,
            },
        }

    @staticmethod
    def _command(action: str, detail: str, *, running: bool) -> dict:
        return {
            "service": "r2d2-vehicle-api",
            "action": action,
            "running": running,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc),
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


def test_camera_stream_endpoint() -> None:
    camera = FakeCameraService()
    app = create_app(FakeVehicleStatusService(), camera)

    with TestClient(app) as client:
        response = client.get("/camera/stream")

    assert response.status_code == 200
    assert camera.slots == 0, "the viewer slot must be released when the stream ends"
    assert response.headers["content-type"] == "multipart/x-mixed-replace; boundary=FRAME"
    body = response.content
    assert body.count(b"--FRAME") == 2
    assert b"Content-Type: image/jpeg" in body
    assert b"Content-Length: 5" in body
    assert body.endswith(b"second\r\n")


def test_camera_stream_returns_503_when_camera_is_unavailable() -> None:
    app = create_app(FakeVehicleStatusService(), FakeCameraService(available=False))

    with TestClient(app) as client:
        response = client.get("/camera/stream")

    assert response.status_code == 503
    assert "no camera detected" in response.json()["detail"]


def test_camera_snapshot_endpoint() -> None:
    app = create_app(FakeVehicleStatusService(), FakeCameraService())

    with TestClient(app) as client:
        response = client.get("/camera/snapshot")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content == b"jpeg-bytes"


def test_camera_status_endpoint() -> None:
    app = create_app(FakeVehicleStatusService(), FakeCameraService())

    with TestClient(app) as client:
        response = client.get("/camera/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["running"] is True
    assert payload["frames_captured"] == 12
    assert payload["component"]["connected"] is True


def test_camera_start_and_stop_endpoints() -> None:
    camera = FakeCameraService()
    app = create_app(FakeVehicleStatusService(), camera)

    with TestClient(app) as client:
        start_response = client.post("/camera/start")
        stop_response = client.post("/camera/stop")

    assert start_response.json()["running"] is True
    assert stop_response.json()["running"] is False
    assert camera.start_calls == 1
    # The app also stops the camera on shutdown.
    assert camera.stop_calls == 2
