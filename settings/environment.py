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
