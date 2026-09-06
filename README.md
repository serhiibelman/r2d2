## 0. Project layout

```
apps/                  processes - each one is started by a start_*.sh
├── api/               FastAPI service on the vehicle
├── vehicle_control/   motor loop on the vehicle
└── controller/        gamepad reader on the laptop
lib/                   libraries - imported, never started
├── db/                SQLAlchemy engine, session, config
├── ddsm115/           motor driver
├── gamepad/           UDP control protocol shared by controller and vehicle
└── common/            formatting and conversion helpers
settings/              environment configuration
migrations/            Alembic revisions
tests/
```

The rule is one-directional: `apps/*` may import `lib/*`, and `lib/*` never
imports `apps/*`. A package under `apps/` owns a process; anything two
processes need lives in `lib/`.

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
5. `GET /camera/stream` - live MJPEG video from the RPi Camera (B).
6. `GET /camera/snapshot` - single JPEG frame.
7. `GET /camera/status` - camera state, resolution, framerate and viewer count.
8. `POST /camera/start` / `POST /camera/stop` - hold the camera open or release the sensor.

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


## 5. Camera stream

The RPi Camera (B) (OV5647) is driven through `picamera2`/`libcamera`. It ships with
Raspberry Pi OS Bookworm and is **not** installed from `requirements.txt`, because it
needs the system libcamera stack and is not usable on the laptop side:

```
sudo apt install -y python3-picamera2
```

The venv on the Pi must be able to see it:

```
python3 -m venv --system-site-packages ~/r2d2/venv
```

Check the camera is detected before starting the API: `rpicam-hello --list-cameras`.

Watch the stream in a browser, or embed it anywhere an image can go:

```html
<img src="http://<vehicle-host>:8000/camera/stream" alt="R2D2 camera">
```

```bash
curl http://<vehicle-host>:8000/camera/snapshot -o frame.jpg
curl http://<vehicle-host>:8000/camera/status
curl -X POST http://<vehicle-host>:8000/camera/stop
```

Notes:

1. The camera opens on the first `/camera/stream` or `/camera/snapshot` request, so the
   sensor stays powered down while nobody is watching. `POST /camera/start` warms it up
   ahead of time and `POST /camera/stop` releases it.
2. All viewers share one capture pipeline and always receive the newest frame; a slow
   viewer drops frames instead of holding up capture or the motor loop.
3. `CAMERA_MAX_CLIENTS` (default 4) caps concurrent viewers; extra ones get `503`.
4. Resolution, framerate and JPEG quality come from the `CAMERA_*` variables in `.env`.
5. MJPEG is deliberately simple - every browser plays it with no JavaScript and latency
   stays low on a LAN. It costs more bandwidth than H.264; if that becomes a problem the
   next step is WebRTC, which needs a signalling server and a JS client.

### Raspberry Pi 1 Model B+

The Pi 1 is the weakest board picamera2 supports, so the defaults in `.env.example` are
sized for it (320x240 at 10 fps):

1. **32-bit Raspberry Pi OS only.** ARMv6 cannot run the 64-bit images. Use the Lite
   image - 512 MB shared with the GPU leaves no room for a desktop.
2. **The hardware JPEG encoder matters here.** `CAMERA_ENCODER=auto` tries the VideoCore
   encoder first and only falls back to software. Software JPEG has no SIMD to use on
   ARMv6 and would eat the single core the motor loop runs on. `GET /camera/status`
   reports which encoder is actually in use.
3. **Camera buffers come from CMA**, not the legacy `gpu_mem` split. If the camera fails
   to allocate buffers, raise it in `/boot/firmware/config.txt`:
   `dtoverlay=vc4-kms-v3d,cma-128`. `CAMERA_BUFFER_COUNT=2` keeps the footprint small.
4. Raise resolution and framerate gradually while watching `top` and `/camera/status`.
   USB Wi-Fi is usually the next bottleneck after the CPU.


## 6. Database (Postgres on AWS)

A connection layer only: SQLAlchemy 2.0 + Alembic talking to RDS over the
`psycopg` (v3) driver. There is **no model and no migration yet** - the schema
is still undecided, so `lib/db` gives you an engine, sessions and configuration
and nothing that presumes a table. The API does not open a database connection
anywhere yet; wiring it into `create_app` comes with the first model.

```python
from lib.db import Database

db = Database()                      # reads DATABASE_URL from .env
with db.session_scope() as session:  # commits on success, rolls back on error
    ...
```

`Database()` with an empty `DATABASE_URL` is switched off rather than broken:
`configured` is `False` and touching `engine` raises instead of silently
connecting somewhere.

### Install on the Pi 1 Model B+ (ARMv6)

PyPI has no 32-bit ARM wheels for any of the C-based Postgres drivers, so the Pi
uses the pure-Python psycopg build, which needs no compiler - only libpq:

```
sudo apt install libpq5
pip install -r requirements.txt
```

Nothing here is compiled on the Pi:

1. `SQLAlchemy` ships a `py3-none-any` wheel and only pulls `greenlet` on 64-bit
   platforms, so on ARMv6 pip takes the pure-Python path.
2. `alembic` is pure Python.
3. `requirements.txt` selects `psycopg[binary]` on laptops and CI, and plain
   `psycopg` (pure Python, uses the system libpq) on `armv6l`/`armv7l`.
4. `postgresql://` URLs are rewritten to `postgresql+psycopg://` at runtime, so
   SQLAlchemy never reaches for psycopg2 - which *would* have to be compiled.

The pure-Python driver is slower per query than the C one. For a few telemetry
rows on a single-core 700 MHz board that is not the bottleneck; the uplink is.

### Configure

Set in `.env`:

```
DATABASE_URL="postgresql+psycopg://r2d2:<password>@<instance>.<id>.<region>.rds.amazonaws.com:5432/r2d2"
DB_SSLMODE="require"
```

`DB_CONNECT_TIMEOUT`, `DB_STATEMENT_TIMEOUT_MS`, `DB_POOL_SIZE`,
`DB_MAX_OVERFLOW` and `DB_POOL_RECYCLE` are tuned in `.env.example` for a
vehicle on flaky Wi-Fi: small pool, short timeouts, `pool_pre_ping` on, and
connections recycled every 5 minutes so an RDS failover does not leave the API
holding dead sockets. All of them are fields of `DatabaseConfig`
(`lib/db/config.py`), which is what a `Database` instance actually reads - the
environment only supplies the defaults, so a second database or a test
container is a different config, not a different process environment.

For certificate verification, download the RDS CA bundle and point
`DB_SSLROOTCERT` at it, then set `DB_SSLMODE="verify-full"`.

`Database.check()` runs `SELECT 1` and returns `(connected, detail)`. It blocks
for up to `DB_CONNECT_TIMEOUT`, so keep it off a request path; the detail names
only the exception class, because driver errors carry the RDS endpoint and the
database user, and the full text goes to the log instead.

### Migrations

`alembic.ini` and `migrations/` are set up and hold no credentials -
`migrations/env.py` reads `DATABASE_URL` from `.env`, or takes
`alembic -x url=postgresql+psycopg://... upgrade head`. `migrations/versions/`
is empty until the first model lands in `lib/db`, so `alembic revision
--autogenerate` would currently produce an empty revision.

Run migrations from a laptop that can reach RDS, not from the vehicle:

```
alembic revision --autogenerate -m "what changed"
alembic upgrade head
alembic downgrade -1
```

### Tests

`tests/test_database.py` covers the connection layer without a database. To also
check a real connection:

```
docker run -d --name r2d2-pg -e POSTGRES_PASSWORD=devpass -e POSTGRES_DB=r2d2 -p 55432:5432 postgres:16-alpine
TEST_DATABASE_URL="postgresql+psycopg://postgres:devpass@127.0.0.1:55432/r2d2" pytest
```

Notes:

1. `psycopg` is LGPL-3.0 licensed (SQLAlchemy and Alembic are MIT). It is used
   as an unmodified library, which LGPL allows, but flag it if a client contract
   restricts copyleft dependencies.
2. RDS should not be reachable from the public internet. Put the vehicle on a
   VPN or a private uplink into the VPC rather than opening the security group.


## 7. Vehicle control with gamepad

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
