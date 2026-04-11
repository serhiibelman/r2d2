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

``
pip install -r ~/r2d2/requirements.txt
``


# Controller mode

1. connect to vehicle via ssh ``
sudo ssh pi@192.168.0.105
``
2. on laptop side run ./start_controller.sh
3. on raspberry side run ./start_vehicle.sh
