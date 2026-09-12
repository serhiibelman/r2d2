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

