#!/bin/bash

echo "[R2D2] Starting vehicle status API"

cd ~/r2d2 || exit 1
source .venv-3.12/bin/activate

uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
