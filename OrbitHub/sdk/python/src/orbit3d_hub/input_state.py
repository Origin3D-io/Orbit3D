"""Thread-safe application input state. Motion expires; button edges stay ordered."""

import threading
import time
from collections import deque
from dataclasses import dataclass

from .client import ButtonEvent, ButtonStateEvent, MotionEvent


@dataclass(frozen=True)
class InputReset:
    """Local state reset, not a device event or a button command."""


class InputState:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._motion = None
        self._received = 0
        self._buttons = deque()

    def reset(self):
        with self._lock:
            self._motion = None
            self._buttons.clear()
            self._buttons.append(InputReset())

    def accept(self, event):
        with self._lock:
            if isinstance(event, MotionEvent):
                self._motion = event
                self._received = self._clock()
            elif isinstance(event, (ButtonEvent, ButtonStateEvent)):
                if len(self._buttons) >= 256:
                    raise RuntimeError("Application button queue overflow")
                self._buttons.append(event)

    def sample(self):
        with self._lock:
            if self._motion is None or self._clock() - self._received >= 0.25:
                return None
            return self._motion

    def take_buttons(self):
        with self._lock:
            result = list(self._buttons)
            self._buttons.clear()
            return result


def select_device(devices, identity=""):
    """An explicit serial identity never silently falls back to another device."""
    connected = [device for device in devices if device.connected]
    if identity:
        matches = [
            device
            for device in connected
            if f"{device.vendor}/{device.product}/{device.serial}" == identity
        ]
        return matches[0] if len(matches) == 1 else None
    return connected[0] if len(connected) == 1 else None
