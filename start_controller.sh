#!/bin/bash

echo "[R2D2] Starting Xbox controller"

cd ~/r2d2 || exit 1
source .venv-3.12/bin/activate

python -m apps.controller.gamepad_main
