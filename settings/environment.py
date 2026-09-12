from pathlib import Path
import os

from dotenv import load_dotenv

# Path to .env
env_path = Path(".env")

# Load .env into environment variables
load_dotenv(dotenv_path=env_path)

# Access values
DEVICE = os.getenv("DEVICE")
FC_DEVICE = os.getenv("FC_DEVICE", "/dev/serial0")
FC_BAUDRATE = int(os.getenv("FC_BAUDRATE", "115200"))

CAMERA_ENABLED = os.getenv("CAMERA_ENABLED", "true").strip().lower() in {"1", "true", "yes"}
CAMERA_WIDTH = int(os.getenv("CAMERA_WIDTH", "640"))
CAMERA_HEIGHT = int(os.getenv("CAMERA_HEIGHT", "480"))
CAMERA_FRAMERATE = int(os.getenv("CAMERA_FRAMERATE", "20"))
CAMERA_JPEG_QUALITY = int(os.getenv("CAMERA_JPEG_QUALITY", "80"))
CAMERA_MAX_CLIENTS = int(os.getenv("CAMERA_MAX_CLIENTS", "4"))
# auto = hardware JPEG if the board has one, software otherwise.
CAMERA_ENCODER = os.getenv("CAMERA_ENCODER", "auto").strip().lower()
CAMERA_BUFFER_COUNT = int(os.getenv("CAMERA_BUFFER_COUNT", "2"))

# AWS IoT Core telemetry. Empty IOT_ENDPOINT disables publishing entirely so
# the vehicle keeps driving with no connectivity and no credentials on board.
IOT_ENDPOINT = os.getenv("IOT_ENDPOINT", "").strip()
IOT_THING_NAME = os.getenv("IOT_THING_NAME", "rover-01").strip()
# IoT policies scope iot:Connect by client ID, so it must match the thing name.
IOT_CLIENT_ID = os.getenv("IOT_CLIENT_ID", IOT_THING_NAME).strip()
TELEMETRY_TOPIC = os.getenv("TELEMETRY_TOPIC", "rover/{thing}/telemetry").strip()
IOT_CERT_PATH = os.getenv("IOT_CERT_PATH", "").strip()
IOT_KEY_PATH = os.getenv("IOT_KEY_PATH", "").strip()
IOT_ROOT_CA_PATH = os.getenv("IOT_ROOT_CA_PATH", "").strip()
# 8883 is MQTT over TLS with a client certificate - the port AWS IoT expects.
IOT_PORT = int(os.getenv("IOT_PORT", "8883"))
IOT_KEEP_ALIVE_SECONDS = int(os.getenv("IOT_KEEP_ALIVE_SECONDS", "30"))
# Bounded so a dead uplink cannot pin the publisher thread.
TELEMETRY_PUBLISH_TIMEOUT_SECONDS = float(os.getenv("TELEMETRY_PUBLISH_TIMEOUT_SECONDS", "5.0"))
# One message per second is plenty for status telemetry and keeps IoT Core
# message costs and the uplink well inside what the Pi 1 can sustain.
TELEMETRY_INTERVAL_SECONDS = float(os.getenv("TELEMETRY_INTERVAL_SECONDS", "1.0"))
