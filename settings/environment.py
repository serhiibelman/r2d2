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

# Postgres on AWS (RDS). Empty DATABASE_URL disables the database entirely so
# the vehicle keeps driving with no connectivity.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_SSLMODE = os.getenv("DB_SSLMODE", "require").strip()
DB_SSLROOTCERT = os.getenv("DB_SSLROOTCERT", "").strip()
DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))
DB_STATEMENT_TIMEOUT_MS = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "5000"))
# One core and 512 MB on the Pi 1: a couple of connections is plenty.
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "2"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "0"))
DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "300"))
DB_ECHO = os.getenv("DB_ECHO", "false").strip().lower() in {"1", "true", "yes"}
