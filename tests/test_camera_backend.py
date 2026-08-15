"""Covers Picamera2Backend against a stubbed picamera2, so the encoder
negotiation is verified on machines without libcamera."""

import sys
import types

import pytest

from apps.api.services.camera import Picamera2Backend


class FakeMJPEGEncoder:
    def __init__(self, bitrate=None):
        self.bitrate = bitrate


class FakeJpegEncoder:
    def __init__(self, q=None):
        self.q = q


class FakeFileOutput:
    def __init__(self, sink):
        self.sink = sink


class FakePicamera2:
    instances: list["FakePicamera2"] = []
    hardware_fails = False

    def __init__(self):
        self.config = None
        self.encoder = None
        self.output = None
        self.closed = False
        self.recording = False
        FakePicamera2.instances.append(self)

    def create_video_configuration(self, **kwargs):
        return kwargs

    def configure(self, config):
        self.config = config

    def start_recording(self, encoder, output):
        if FakePicamera2.hardware_fails and isinstance(encoder, FakeMJPEGEncoder):
            raise RuntimeError("V4L2 JPEG encoder not available")
        self.encoder = encoder
        self.output = output
        self.recording = True

    def stop_recording(self):
        self.recording = False

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def fake_picamera2(monkeypatch):
    FakePicamera2.instances.clear()
    FakePicamera2.hardware_fails = False

    root = types.ModuleType("picamera2")
    root.Picamera2 = FakePicamera2
    encoders = types.ModuleType("picamera2.encoders")
    encoders.JpegEncoder = FakeJpegEncoder
    encoders.MJPEGEncoder = FakeMJPEGEncoder
    outputs = types.ModuleType("picamera2.outputs")
    outputs.FileOutput = FakeFileOutput

    monkeypatch.setitem(sys.modules, "picamera2", root)
    monkeypatch.setitem(sys.modules, "picamera2.encoders", encoders)
    monkeypatch.setitem(sys.modules, "picamera2.outputs", outputs)
    yield
    FakePicamera2.instances.clear()


def make_backend(**kwargs) -> Picamera2Backend:
    defaults = dict(width=320, height=240, framerate=10, jpeg_quality=80)
    return Picamera2Backend(**{**defaults, **kwargs})


def test_hardware_encoder_is_preferred_and_gets_yuv420() -> None:
    backend = make_backend()

    backend.start(lambda frame: None)

    assert backend.active_encoder == "hardware"
    camera = FakePicamera2.instances[0]
    assert isinstance(camera.encoder, FakeMJPEGEncoder)
    assert camera.config["main"]["format"] == "YUV420"
    assert camera.config["buffer_count"] == 2
    assert camera.config["controls"]["FrameDurationLimits"] == (100_000, 100_000)


def test_falls_back_to_software_when_there_is_no_hardware_encoder() -> None:
    FakePicamera2.hardware_fails = True
    backend = make_backend()

    backend.start(lambda frame: None)

    assert backend.active_encoder == "software"
    failed, used = FakePicamera2.instances
    assert failed.closed is True, "the failed attempt must release the camera"
    assert isinstance(used.encoder, FakeJpegEncoder)
    assert used.encoder.q == 80
    # Software JPEG takes the default format, matching the picamera2 example.
    assert "format" not in used.config["main"]


def test_software_can_be_forced() -> None:
    backend = make_backend(encoder="software")

    backend.start(lambda frame: None)

    assert backend.active_encoder == "software"
    assert len(FakePicamera2.instances) == 1


def test_forced_hardware_does_not_silently_fall_back() -> None:
    FakePicamera2.hardware_fails = True
    backend = make_backend(encoder="hardware")

    with pytest.raises(RuntimeError, match="V4L2 JPEG encoder not available"):
        backend.start(lambda frame: None)

    assert backend.active_encoder is None
    assert FakePicamera2.instances[0].closed is True


@pytest.mark.parametrize("hardware_fails", [False, True])
def test_encoded_frames_reach_the_callback(hardware_fails: bool) -> None:
    FakePicamera2.hardware_fails = hardware_fails
    received: list[bytes] = []
    backend = make_backend()
    backend.start(received.append)

    # picamera2 writes each encoded frame into the sink wrapped by FileOutput.
    sink = FakePicamera2.instances[-1].output.sink
    written = sink.write(bytearray(b"jpeg-frame"))

    assert received == [b"jpeg-frame"]
    assert written == len(b"jpeg-frame")


def test_stop_closes_the_camera() -> None:
    backend = make_backend()
    backend.start(lambda frame: None)

    backend.stop()

    camera = FakePicamera2.instances[0]
    assert camera.recording is False
    assert camera.closed is True
    backend.stop()  # idempotent


def test_bitrate_scales_with_resolution_and_quality() -> None:
    small = make_backend(width=320, height=240, framerate=10, jpeg_quality=80)
    large = make_backend(width=640, height=480, framerate=20, jpeg_quality=80)

    assert large._bitrate() > small._bitrate()
    assert small._bitrate() >= 500_000, "a floor keeps low resolutions watchable"
