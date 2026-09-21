from __future__ import annotations

import socket
import struct
import time
from collections import deque
from dataclasses import dataclass
from typing import TypeAlias

from .protocol import Decoder, Message, MessageReader, MessageType, send_message

MOTION = 1 << 0
BUTTONS = 1 << 1
DEVICES = 1 << 2


class OrbitHubError(RuntimeError):
    pass


@dataclass(frozen=True)
class DeviceInfo:
    device_id: int
    capabilities: int
    connected: bool
    button_count: int
    vendor: str
    product: str
    serial: str


@dataclass(frozen=True)
class MotionEvent:
    device_id: int
    timestamp_us: int
    tx: int
    ty: int
    tz: int
    rx: int
    ry: int
    rz: int


@dataclass(frozen=True)
class ButtonEvent:
    device_id: int
    timestamp_us: int
    button_id: int
    pressed: bool


@dataclass(frozen=True)
class DeviceEvent:
    device_id: int
    connected: bool


@dataclass(frozen=True)
class ButtonStateEvent:
    device_id: int
    buttons: int


Event: TypeAlias = MotionEvent | ButtonEvent | DeviceEvent | ButtonStateEvent


class Client:
    def __init__(self, host: str = "127.0.0.1", port: int = 43120, timeout: float = 2.0):
        self._socket = socket.create_connection((host, port), timeout=timeout)
        self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._socket.settimeout(timeout)
        self._reader = MessageReader()
        self._timeout = timeout
        self._next_request_id = 1
        self._pending_events: deque[Event] = deque()
        response = self._request(MessageType.HELLO_REQUEST, b"", MessageType.HELLO_RESPONSE)
        decoder = Decoder(response.payload)
        if decoder.text() != "OrbitHub":
            self.close()
            raise OrbitHubError("Unexpected Orbit3D service identity")
        self.server_capabilities = decoder.u32()
        if not decoder.empty:
            self.close()
            raise OrbitHubError("Invalid OrbitHub hello response")

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close()
            finally:
                self._socket = None

    def _request(
        self,
        request_type: MessageType,
        payload: bytes,
        response_type: MessageType,
    ) -> Message:
        connection = self._socket
        if connection is None:
            raise OrbitHubError("Client is closed")
        request_id = self._next_request_id
        self._next_request_id += 1
        send_message(connection, request_type, request_id, payload)
        # Input arriving before the response must not renew the request timeout.
        deadline = time.monotonic() + self._timeout
        while True:
            try:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise socket.timeout("OrbitHub request deadline expired")
                response = self._reader.receive(connection, remaining)
            except (OSError, ValueError, ConnectionError):
                self.close()
                raise
            if response.request_id == 0:
                self._pending_events.append(self._decode_event(response))
                if len(self._pending_events) > 1024:
                    self.close()
                    raise OrbitHubError("Consumer event queue overflow")
                continue
            break
        if response.request_id != request_id:
            raise OrbitHubError("Unexpected OrbitHub response ID")
        if response.message_type == MessageType.ERROR:
            raise OrbitHubError(Decoder(response.payload).text())
        if response.message_type != response_type:
            raise OrbitHubError("Unexpected OrbitHub response type")
        return response

    def list_devices(self) -> list[DeviceInfo]:
        response = self._request(
            MessageType.LIST_DEVICES_REQUEST,
            b"",
            MessageType.DEVICE_LIST,
        )
        decoder = Decoder(response.payload)
        devices = []
        for _ in range(decoder.u16()):
            device_id = decoder.u32()
            capabilities = decoder.u32()
            connected = bool(decoder.u8())
            button_count = decoder.u8()
            decoder.u16()
            devices.append(
                DeviceInfo(
                    device_id=device_id,
                    capabilities=capabilities,
                    connected=connected,
                    button_count=button_count,
                    vendor=decoder.text(),
                    product=decoder.text(),
                    serial=decoder.text(),
                )
            )
        if not decoder.empty:
            raise OrbitHubError("Invalid OrbitHub device list")
        return devices

    def subscribe(self, subscriptions: int) -> None:
        response = self._request(
            MessageType.SUBSCRIBE_REQUEST,
            struct.pack(">I", subscriptions),
            MessageType.SUBSCRIBE_RESPONSE,
        )
        decoder = Decoder(response.payload)
        accepted = decoder.u32()
        if accepted != subscriptions or not decoder.empty:
            raise OrbitHubError("OrbitHub rejected a subscription")

    def poll(self, timeout: float | None = None) -> Event:
        connection = self._socket
        if connection is None:
            raise OrbitHubError("Client is closed")
        if self._pending_events:
            return self._pending_events.popleft()
        previous_timeout = connection.gettimeout()
        connection.settimeout(timeout)
        try:
            message = self._reader.receive(connection, timeout)
        finally:
            try:
                connection.settimeout(previous_timeout)
            except OSError:
                pass
        if message.request_id != 0:
            raise OrbitHubError("Unexpected OrbitHub response while polling")
        return self._decode_event(message)

    @staticmethod
    def _decode_event(message: Message) -> Event:
        decoder = Decoder(message.payload)
        if message.message_type == MessageType.MOTION_EVENT:
            event: Event = MotionEvent(
                device_id=decoder.u32(),
                timestamp_us=decoder.u64(),
                tx=decoder.i32(),
                ty=decoder.i32(),
                tz=decoder.i32(),
                rx=decoder.i32(),
                ry=decoder.i32(),
                rz=decoder.i32(),
            )
        elif message.message_type == MessageType.BUTTON_EVENT:
            event = ButtonEvent(
                device_id=decoder.u32(),
                timestamp_us=decoder.u64(),
                button_id=decoder.u16(),
                pressed=bool(decoder.u8()),
            )
            decoder.u8()
        elif message.message_type == MessageType.BUTTON_STATE:
            event = ButtonStateEvent(device_id=decoder.u32(), buttons=decoder.u32())
        elif message.message_type == MessageType.DEVICE_EVENT:
            event = DeviceEvent(
                device_id=decoder.u32(),
                connected=bool(decoder.u8()),
            )
        else:
            raise OrbitHubError("Unexpected OrbitHub event type")
        if not decoder.empty:
            raise OrbitHubError("Invalid OrbitHub event")
        return event
