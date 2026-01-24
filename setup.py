import shutil

from pathlib import Path

from apps.common.formatting import print_success, print_error

env_example = Path(".env.example")
env_file = Path(".env")


if not env_example.exists():
    print_error("ERROR: .env.example not found!")
else:
    shutil.copy(env_example, env_file)
    print_success("✅ Created .env from .env.example")
