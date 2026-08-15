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


## 6. Vehicle control with gamepad

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
