## 1. Install system dependencies

```
sudo apt update
sudo apt install libopenblas-dev liblapack-dev gfortran -y
```

## 2. Create venv

```
python3.11 -m venv ~/r2d2/venv
source ~/r2d2/venv/bin/activate
```

## 3. Install requirements

```
pip install -r ~/r2d2/requirements.txt
```

## 4. Start vehicle API

Run on the vehicle:

```
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
```

Available endpoints:

1. `GET /health` - API and hardware probe health.
2. `GET /status` - current vehicle snapshot, including configured motor IDs and hardware probe status.
3. `POST /motors/start` - ramp all motors to a requested base RPM.
4. `POST /motors/stop` - ramp all motors down to zero.

Example:

```bash
curl -X POST http://<vehicle-host>:8000/motors/start \
  -H 'Content-Type: application/json' \
  -d '{"rpm": 120}'

curl -X POST http://<vehicle-host>:8000/motors/stop
```

Notes:

1. The API is intended to run on the vehicle itself so it can probe local hardware directly.
2. Motor start accepts values in the same range used by the controller logic: `-200` to `200`.
3. The motor endpoints ramp in controller-sized steps instead of jumping to the target immediately.
4. If another process already owns the motor or FC serial port, the API will report that component as unavailable and motor commands can fail with `503`.


## 5. Vehicle control with gamepad

See `docs/gamepad-control.md` for the operator flow and control mapping.

Quick start:

1. On the Raspberry Pi, run `./start_vehicle.sh`.
2. On the laptop with the gamepad connected, run `./start_controller.sh`.
3. Use the controls from the gamepad doc to enable drive and move the vehicle.


# Controller mode

1. connect to vehicle via ssh ``
sudo ssh pi@192.168.0.105
``
2. on laptop side run ./start_controller.sh
3. on raspberry side run ./start_vehicle.sh
