from __future__ import annotations

import socket
import struct
import threading
import time
from dataclasses import dataclass

from .client import OrbitHubError
from .protocol import Decoder, MessageReader, MessageType, send_message, text

MOTION_6DOF = 1 << 0
BUTTONS = 1 << 1
NORMALIZED_MIN = -1_000_000
NORMALIZED_MAX = 1_000_000
SERVER_CAPABILITY_PROVIDER = 1 << 1


@dataclass(frozen=True)
class ProviderDevice:
    device_id: int
    button_count: int


class Provider:
    """Publishes normalized device input to OrbitHub."""

    def __init__(self, host: str = "127.0.0.1", port: int = 43120, timeout: float = 2.0):
        self._socket = socket.create_connection((host, port), timeout=timeout)
        self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._socket.settimeout(timeout)
        self._reader = MessageReader()
        self._timeout = timeout
        self._next_request_id = 1
        self._send_lock = threading.Lock()
        response = self._request(
            MessageType.HELLO_REQUEST,
            b"",
            MessageType.HELLO_RESPONSE,
        )
        decoder = Decoder(response)
        if decoder.text() != "OrbitHub":
            self.close()
            raise OrbitHubError("Unexpected Orbit3D service identity")
        server_capabilities = decoder.u32()
        if not decoder.empty:
            self.close()
            raise OrbitHubError("Invalid OrbitHub hello response")
        if not server_capabilities & SERVER_CAPABILITY_PROVIDER:
            self.close()
            raise OrbitHubError("OrbitHub does not support input providers")

    def __enter__(self) -> "Provider":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        connection = self._socket
        self._socket = None
        if connection is not None:
            connection.close()

    def register_device(
        self,
        vendor: str,
        product: str,
        serial: str = "",
        button_count: int = 0,
    ) -> ProviderDevice:
        if not vendor or not product:
            raise ValueError("vendor and product are required")
        for value in (vendor, product, serial):
            if len(value.encode("utf-8")) > 95 or any(ord(c) < 32 or ord(c) == 127 for c in value):
                raise ValueError(
                    "identity fields must contain at most 95 UTF-8 bytes without control characters"
                )
        if button_count < 0 or button_count > 32:
            raise ValueError("button_count must be between 0 and 32")
        capabilities = MOTION_6DOF | (BUTTONS if button_count else 0)
        payload = struct.pack(">IB3x", capabilities, button_count)
        payload += text(vendor) + text(product) + text(serial)
        response = self._request(
            MessageType.PROVIDER_REGISTER_REQUEST,
            payload,
            MessageType.PROVIDER_REGISTER_RESPONSE,
        )
        decoder = Decoder(response)
        device_id = decoder.u32()
        if not decoder.empty:
            raise OrbitHubError("Invalid provider registration response")
        return ProviderDevice(device_id=device_id, button_count=button_count)

    def unregister_device(self, device: ProviderDevice | int) -> None:
        device_id = device.device_id if isinstance(device, ProviderDevice) else int(device)
        response = self._request(
            MessageType.PROVIDER_UNREGISTER_REQUEST,
            struct.pack(">I", device_id),
            MessageType.PROVIDER_UNREGISTER_RESPONSE,
        )
        if response:
            raise OrbitHubError("Invalid provider unregister response")

    def ping(self) -> None:
        self._request(MessageType.PING, b"", MessageType.PONG)

    def publish_motion(
        self,
        device: ProviderDevice | int,
        tx: int,
        ty: int,
        tz: int,
        rx: int,
        ry: int,
        rz: int,
        timestamp_us: int | None = None,
    ) -> None:
        device_id = device.device_id if isinstance(device, ProviderDevice) else int(device)
        axes = tuple(int(value) for value in (tx, ty, tz, rx, ry, rz))
        if any(value < NORMALIZED_MIN or value > NORMALIZED_MAX for value in axes):
            raise ValueError("motion values must be between -1000000 and 1000000")
        timestamp = self._timestamp(timestamp_us)
        payload = struct.pack(">IQ6i", device_id, timestamp, *axes)
        self._send_one_way(MessageType.PROVIDER_MOTION, payload)

    def publish_button(
        self,
        device: ProviderDevice | int,
        button_id: int,
        pressed: bool,
        timestamp_us: int | None = None,
    ) -> None:
        device_id = device.device_id if isinstance(device, ProviderDevice) else int(device)
        if button_id < 1 or button_id > 32:
            raise ValueError("button_id must be between 1 and 32")
        if isinstance(device, ProviderDevice) and button_id > device.button_count:
            raise ValueError("button_id exceeds the registered button count")
        timestamp = self._timestamp(timestamp_us)
        payload = struct.pack(">IQHBB", device_id, timestamp, button_id, bool(pressed), 0)
        self._send_one_way(MessageType.PROVIDER_BUTTON, payload)

    @staticmethod
    def _timestamp(value: int | None) -> int:
        timestamp = time.monotonic_ns() // 1000 if value is None else int(value)
        if timestamp < 0 or timestamp > 0xFFFFFFFFFFFFFFFF:
            raise ValueError("timestamp_us is outside the unsigned 64-bit range")
        return timestamp

    def _request(
        self,
        request_type: MessageType,
        payload: bytes,
        response_type: MessageType,
    ) -> bytes:
        connection = self._socket
        if connection is None:
            raise OrbitHubError("Provider is closed")
        with self._send_lock:
            request_id = self._next_request_id
            self._next_request_id += 1
            try:
                send_message(connection, request_type, request_id, payload)
                response = self._reader.receive(connection, self._timeout)
            except (OSError, ValueError, ConnectionError):
                self.close()
                raise
        if response.request_id != request_id:
            raise OrbitHubError("Unexpected OrbitHub response ID")
        if response.message_type == MessageType.ERROR:
            raise OrbitHubError(Decoder(response.payload).text())
        if response.message_type != response_type:
            raise OrbitHubError("Unexpected OrbitHub response type")
        return response.payload

    def _send_one_way(self, message_type: MessageType, payload: bytes) -> None:
        connection = self._socket
        if connection is None:
            raise OrbitHubError("Provider is closed")
        with self._send_lock:
            send_message(connection, message_type, 0, payload)
