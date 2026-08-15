from __future__ import annotations

import io
from threading import Condition, RLock
from typing import Any, Callable

from apps.api.services.vehicle_status import ComponentSnapshot, utc_now
from settings import (
    CAMERA_ENABLED,
    CAMERA_FRAMERATE,
    CAMERA_HEIGHT,
    CAMERA_JPEG_QUALITY,
    CAMERA_MAX_CLIENTS,
    CAMERA_WIDTH,
)

BACKEND_ERRORS = (ImportError, OSError, RuntimeError, ValueError)


class _FrameSink(io.BufferedIOBase):
    """File-like object picamera2 writes each encoded JPEG into."""

    def __init__(self, on_frame: Callable[[bytes], None]):
        self._on_frame = on_frame

    def writable(self) -> bool:
        return True

    def write(self, buffer: Any) -> int:
        frame = bytes(buffer)
        self._on_frame(frame)
        return len(frame)


class Picamera2Backend:
    """MJPEG capture from the RPi Camera (B) (OV5647) through picamera2/libcamera."""

    def __init__(self, *, width: int, height: int, framerate: int, jpeg_quality: int):
        self.width = width
        self.height = height
        self.framerate = framerate
        self.jpeg_quality = jpeg_quality
        self._camera = None

    def start(self, on_frame: Callable[[bytes], None]) -> None:
        # Imported lazily so the API still boots on machines without libcamera.
        from picamera2 import Picamera2
        from picamera2.encoders import JpegEncoder
        from picamera2.outputs import FileOutput

        frame_duration = int(1_000_000 / self.framerate)
        camera = Picamera2()
        camera.configure(
            camera.create_video_configuration(
                main={"size": (self.width, self.height)},
                controls={"FrameDurationLimits": (frame_duration, frame_duration)},
            )
        )
        try:
            camera.start_recording(
                JpegEncoder(q=self.jpeg_quality),
                FileOutput(_FrameSink(on_frame)),
            )
        except BACKEND_ERRORS:
            camera.close()
            raise
        self._camera = camera

    def stop(self) -> None:
        camera, self._camera = self._camera, None
        if camera is None:
            return
        try:
            camera.stop_recording()
        finally:
            camera.close()


class CameraService:
    """Owns the camera and fans the newest frame out to every viewer.

    A single capture thread inside the backend publishes frames here; readers
    always get the latest one and silently drop whatever they missed, so a slow
    viewer can never stall capture.
    """

    def __init__(
        self,
        *,
        enabled: bool = CAMERA_ENABLED,
        width: int = CAMERA_WIDTH,
        height: int = CAMERA_HEIGHT,
        framerate: int = CAMERA_FRAMERATE,
        jpeg_quality: int = CAMERA_JPEG_QUALITY,
        max_clients: int = CAMERA_MAX_CLIENTS,
        frame_timeout_seconds: float = 5.0,
        backend_factory: Callable[..., Picamera2Backend] = Picamera2Backend,
    ):
        self.enabled = enabled
        self.width = width
        self.height = height
        self.framerate = framerate
        self.jpeg_quality = jpeg_quality
        self.max_clients = max_clients
        self.frame_timeout_seconds = frame_timeout_seconds
        self._backend_factory = backend_factory
        self._backend: Picamera2Backend | None = None
        self._state_lock = RLock()
        self._frame_condition = Condition()
        self._frame: bytes | None = None
        self._frame_seq = 0
        self._frames_captured = 0
        self._last_frame_at = None
        self._clients = 0
        self._running = False
        self._component = ComponentSnapshot(
            configured=enabled,
            connected=False,
            detail="Camera has not been started yet",
            checked_at=utc_now(),
        )

    def start(self) -> dict[str, Any]:
        self.ensure_running()
        return self._command_response(action="start", detail="Camera capture is running")

    def stop(self) -> dict[str, Any]:
        with self._state_lock:
            backend, self._backend = self._backend, None
            self._running = False
            if backend is not None:
                try:
                    backend.stop()
                except BACKEND_ERRORS as exc:
                    self._set_component(connected=False, detail=str(exc))
                    raise RuntimeError(str(exc)) from exc

        # Wake every viewer so their generators notice the camera is gone.
        with self._frame_condition:
            self._frame = None
            self._frame_seq += 1
            self._frame_condition.notify_all()

        self._set_component(connected=False, detail="Camera capture stopped")
        return self._command_response(action="stop", detail="Camera capture stopped")

    def ensure_running(self) -> None:
        """Open the camera if it is not already streaming. Safe to call repeatedly."""
        if not self.enabled:
            raise RuntimeError("Camera is disabled by configuration (CAMERA_ENABLED)")

        with self._state_lock:
            if self._running:
                return

            backend = self._backend_factory(
                width=self.width,
                height=self.height,
                framerate=self.framerate,
                jpeg_quality=self.jpeg_quality,
            )
            try:
                backend.start(self._publish_frame)
            except BACKEND_ERRORS as exc:
                self._set_component(connected=False, detail=str(exc))
                raise RuntimeError(f"Camera is unavailable: {exc}") from exc

            self._backend = backend
            self._running = True
            self._set_component(
                connected=True,
                detail=f"Capturing {self.width}x{self.height} at {self.framerate} fps",
            )

    def acquire_client_slot(self) -> None:
        """Reserve a viewer slot, starting the camera if it is not running yet.

        Called before the response starts so a full camera or a dead sensor can
        still be answered with a status code instead of a truncated stream.
        """
        self.ensure_running()
        with self._state_lock:
            if self._clients >= self.max_clients:
                raise RuntimeError(
                    f"Camera stream already has {self._clients} of {self.max_clients} viewers"
                )
            self._clients += 1

    def release_client_slot(self) -> None:
        with self._state_lock:
            self._clients = max(0, self._clients - 1)

    def next_frame(self, last_seq: int) -> tuple[int, bytes] | None:
        """Block until a frame newer than ``last_seq`` arrives.

        Returns ``None`` once the camera has been stopped, which ends the stream.
        """
        with self._state_lock:
            if not self._running:
                return None

        with self._frame_condition:
            # `_running` is published before stop() notifies, so a stopped camera
            # always wins over waiting for a frame that will never arrive.
            if not self._frame_condition.wait_for(
                lambda: not self._running
                or (self._frame is not None and self._frame_seq != last_seq),
                timeout=self.frame_timeout_seconds,
            ):
                self._set_component(
                    connected=False,
                    detail=f"No frame received within {self.frame_timeout_seconds}s",
                )
                raise RuntimeError("Timed out waiting for a camera frame")
            if self._frame is None or not self._running:
                return None
            return self._frame_seq, self._frame

    def capture_frame(self) -> bytes:
        """Return the next freshly captured JPEG frame."""
        self.ensure_running()
        with self._frame_condition:
            last_seq = self._frame_seq
            if not self._frame_condition.wait_for(
                lambda: self._frame is not None and self._frame_seq != last_seq,
                timeout=self.frame_timeout_seconds,
            ):
                raise RuntimeError("Timed out waiting for a camera frame")
            return self._frame

    def snapshot(self) -> dict[str, Any]:
        with self._state_lock:
            component = self._component
            running = self._running
            clients = self._clients

        with self._frame_condition:
            frames_captured = self._frames_captured
            last_frame_at = self._last_frame_at

        return {
            "service": "r2d2-vehicle-api",
            "timestamp": utc_now(),
            "running": running,
            "clients": clients,
            "width": self.width,
            "height": self.height,
            "framerate": self.framerate,
            "jpeg_quality": self.jpeg_quality,
            "frames_captured": frames_captured,
            "last_frame_at": last_frame_at,
            "component": {
                "configured": component.configured,
                "connected": component.connected,
                "detail": component.detail,
                "checked_at": component.checked_at,
            },
        }

    def _publish_frame(self, frame: bytes) -> None:
        with self._frame_condition:
            self._frame = frame
            self._frame_seq += 1
            self._frames_captured += 1
            self._last_frame_at = utc_now()
            self._frame_condition.notify_all()

    def _command_response(self, *, action: str, detail: str) -> dict[str, Any]:
        with self._state_lock:
            running = self._running
        return {
            "service": "r2d2-vehicle-api",
            "action": action,
            "running": running,
            "detail": detail,
            "timestamp": utc_now(),
        }

    def _set_component(self, *, connected: bool, detail: str) -> None:
        with self._state_lock:
            self._component = ComponentSnapshot(
                configured=self.enabled,
                connected=connected,
                detail=detail,
                checked_at=utc_now(),
            )
