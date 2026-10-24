"""~/.config/hyperx-linux/config.json"""
from __future__ import annotations

import copy
import json
import os
import threading

CONFIG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "hyperx-linux")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULTS = {
    "notifications": True,
    "notify_mic": True,
    "low_battery": 20,
    "allow_experimental": False,  # let experimental drivers write to devices
    "devices": {},  # driver id -> {control id: value} for persisted controls (+ "eq_preset")
}


class Config:
    def __init__(self, path: str = CONFIG_PATH):
        self.path = path
        self._lock = threading.Lock()
        self.data = copy.deepcopy(DEFAULTS)
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path) as f:
                self.data.update(json.load(f))
        except (OSError, ValueError):
            pass

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        with self._lock:
            self.data[key] = value
        self.save()

    def device(self, driver_id: str) -> dict:
        return self.data["devices"].setdefault(driver_id, {})

    def set_device_value(self, driver_id: str, key: str, value) -> None:
        with self._lock:
            self.data["devices"].setdefault(driver_id, {})[key] = value
        self.save()

    def save(self) -> None:
        with self._lock:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self.data, f, indent=2)
            os.replace(tmp, self.path)
