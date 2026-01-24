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

## 3. Upgrade pip, setuptools, wheel, numpy

```
pip install --upgrade pip setuptools wheel
pip install numpy
```

## 4. Install requirements

``
pip install -r ~/r2d2/requirements.txt
``