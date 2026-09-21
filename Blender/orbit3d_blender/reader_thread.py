"""Background OrbitHub reader. Viewport sampling happens on the UI thread."""

from __future__ import annotations

import os
import socket
import threading

from .sdk import hub


class OrbitReaderThread:
    def __init__(self, reconnect_delay_s: float = 1.0, hub_port: int = 43120):
        self._reconnect_delay_s = reconnect_delay_s
        self._hub_port = hub_port
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._state_lock = threading.Lock()
        self._connection_lock = threading.Lock()
        self._connected = False
        self._status = "Stopped"
        self._hub_client = None
        self.device_identity = os.environ.get("ORBIT3D_DEVICE", "")
        self.input_state = hub.InputState()

    @property
    def connected(self) -> bool:
        with self._state_lock:
            return self._connected

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def status(self) -> str:
        with self._state_lock:
            return self._status

    def start(self) -> None:
        if self.running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="Orbit3DBlenderReader", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._close_connection()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            if not self._thread.is_alive():
                self._thread = None
        self.input_state.reset()
        self._set_state(False, "Stopped")

    def force_reconnect(self) -> None:
        self._close_connection()
        self.input_state.reset()
        self._set_state(False, "Reconnecting")

    def _close_connection(self) -> None:
        with self._connection_lock:
            client = self._hub_client
            self._hub_client = None
        if client is not None:
            client.close()

    def _set_state(self, connected: bool, status: str) -> None:
        with self._state_lock:
            self._connected = connected
            self._status = status

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._run_hub_session()
            self._stop_event.wait(self._reconnect_delay_s)
        self._close_connection()
        self._set_state(False, "Stopped")

    def _run_hub_session(self) -> None:
        client = None
        try:
            self._set_state(False, "Connecting to OrbitHub")
            client = hub.Client(port=self._hub_port, timeout=0.5)
            with self._connection_lock:
                self._hub_client = client
            client.subscribe(hub.MOTION | hub.BUTTONS | hub.DEVICES)
            device = hub.select_device(client.list_devices(), self.device_identity)
            if device is None:
                self._set_state(False, "OrbitHub: Select a connected device")
                return
            self.input_state.reset()
            self._set_state(True, "OrbitHub Connected")
            while not self._stop_event.is_set():
                try:
                    event = client.poll(timeout=0.2)
                except socket.timeout:
                    continue
                if event.device_id != device.device_id:
                    continue
                self.input_state.accept(event)
                if isinstance(event, hub.DeviceEvent) and not event.connected:
                    self._set_state(False, "OrbitHub: Device Disconnected")
                    return
        except (ConnectionError, OSError, RuntimeError, ValueError):
            if not self._stop_event.is_set():
                self._set_state(False, "OrbitHub Unavailable")
        finally:
            self.input_state.reset()
            with self._connection_lock:
                if self._hub_client is client:
                    self._hub_client = None
            if client is not None:
                client.close()
