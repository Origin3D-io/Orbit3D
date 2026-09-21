"""OrbitHub reader and FreeCAD UI-thread viewport bridge."""

from __future__ import annotations

import os
import socket
import threading
import time

from .sdk import hub
from .viewport_driver import OrbitViewportDriver

try:
    from PySide import QtCore
except ImportError:
    try:
        from PySide2 import QtCore
    except ImportError:
        from PySide6 import QtCore

try:
    import FreeCAD as App
except ImportError:
    App = None

HUB_PORT = 43120


def _log_error(message: str) -> None:
    if App is not None:
        App.Console.PrintError(f"[Orbit3D] {message}\n")


class OrbitFreeCADController:
    def __init__(self):
        self._hub_client = None
        self.input_state = hub.InputState()
        self._last_tick = time.monotonic()
        self._connection_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._timer = QtCore.QTimer()
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._viewport = OrbitViewportDriver()
        self._running = False
        self._restart_pending = False
        self._status = "Stopped"
        self._device_identity = ""

    @property
    def running(self) -> bool:
        return self._running

    @property
    def status(self) -> str:
        return self._status

    def start(self) -> None:
        if self._running:
            return
        if self._thread is not None and self._thread.is_alive():
            self._restart_pending = True
            self._running = True
            self._status = "Waiting for previous connection to close"
            self._timer.start()
            return
        self._device_identity = os.environ.get("ORBIT3D_DEVICE", "")
        if App is not None:
            self._device_identity = App.ParamGet(
                "User parameter:BaseApp/Preferences/Orbit3D"
            ).GetString("DeviceIdentity", self._device_identity)
        self._running = True
        self._status = "Starting"
        self._last_tick = time.monotonic()
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._reader_loop, name="Orbit3DFreeCADReader", daemon=True
        )
        self._thread.start()
        self._timer.start()

    def stop(self) -> None:
        self._running = False
        self._restart_pending = False
        self._stop_event.set()
        self._timer.stop()
        self._viewport.clear_feedback()
        self._close_connection()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            if not self._thread.is_alive():
                self._thread = None
        self.input_state.reset()
        self._status = "Stopped"

    def toggle(self) -> bool:
        if self._running:
            self.stop()
        else:
            self.start()
        return self._running

    def _close_connection(self) -> None:
        with self._connection_lock:
            client = self._hub_client
            self._hub_client = None
        if client is not None:
            client.close()

    def _reader_loop(self) -> None:
        while not self._stop_event.is_set():
            self._run_hub_session()
            self._stop_event.wait(1.0)
        self._close_connection()

    def _run_hub_session(self) -> None:
        client = None
        try:
            self._status = "Connecting to OrbitHub"
            client = hub.Client(port=HUB_PORT, timeout=0.5)
            with self._connection_lock:
                self._hub_client = client
            client.subscribe(hub.MOTION | hub.BUTTONS | hub.DEVICES)
            device = hub.select_device(client.list_devices(), self._device_identity)
            if device is None:
                self._status = "OrbitHub: Select a connected device"
                return
            self.input_state.reset()
            self._status = "OrbitHub Connected"
            while not self._stop_event.is_set():
                try:
                    event = client.poll(timeout=0.2)
                except socket.timeout:
                    continue
                if event.device_id != device.device_id:
                    continue
                self.input_state.accept(event)
                if isinstance(event, hub.DeviceEvent) and not event.connected:
                    self._status = "OrbitHub: Device Disconnected"
                    return
        except (ConnectionError, OSError, RuntimeError, ValueError) as exc:
            if not self._stop_event.is_set():
                self._status = "OrbitHub Unavailable"
                _log_error(f"OrbitHub connection error: {exc}")
        finally:
            self.input_state.reset()
            with self._connection_lock:
                if self._hub_client is client:
                    self._hub_client = None
            if client is not None:
                client.close()

    def _tick(self) -> None:
        if not self._running:
            return
        if self._restart_pending:
            # The UI timer waits for the old reader before reusing its stop event.
            if self._thread is not None and self._thread.is_alive():
                return
            self._restart_pending = False
            self._running = False
            self.start()
            return
        self._viewport.expire_feedback()
        now = time.monotonic()
        time_scale = min(0.05, max(0, now - self._last_tick)) / 0.016
        self._last_tick = now
        focused = True
        try:
            import FreeCADGui as Gui

            focused = Gui.getMainWindow().isActiveWindow()
        except ImportError:
            pass
        for event in self.input_state.take_buttons():
            self._viewport.apply_button_event(event, focused)
        if not focused:
            return
        sample = self.input_state.sample()
        if sample is None:
            return
        latest = hub.to_viewport_motion(sample)
        try:
            self._viewport.apply_motion(latest, time_scale)
        except Exception as exc:
            _log_error(f"viewport update error: {exc}")


_CONTROLLER: OrbitFreeCADController | None = None


def get_controller() -> OrbitFreeCADController:
    global _CONTROLLER
    if _CONTROLLER is None:
        _CONTROLLER = OrbitFreeCADController()
    return _CONTROLLER
