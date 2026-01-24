from pathlib import Path
from dotenv import load_dotenv
import os

# Path to .env
env_path = Path(".env")

# Load .env into environment variables
load_dotenv(dotenv_path=env_path)

# Access values
DEVICE = os.getenv("DEVICE")
