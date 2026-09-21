from __future__ import annotations

import enum
import select
import socket
import struct
import time
from dataclasses import dataclass

MAGIC = b"O3DH"
VERSION_MAJOR = 0
VERSION_MINOR = 2
HEADER = struct.Struct(">4sBBHII")
MAX_PAYLOAD_SIZE = 64 * 1024


class MessageType(enum.IntEnum):
    HELLO_REQUEST = 1
    HELLO_RESPONSE = 2
    LIST_DEVICES_REQUEST = 3
    DEVICE_LIST = 4
    SUBSCRIBE_REQUEST = 5
    SUBSCRIBE_RESPONSE = 6
    MOTION_EVENT = 7
    BUTTON_EVENT = 8
    DEVICE_EVENT = 9
    PING = 10
    PONG = 11
    PROVIDER_REGISTER_REQUEST = 12
    PROVIDER_REGISTER_RESPONSE = 13
    PROVIDER_UNREGISTER_REQUEST = 14
    PROVIDER_UNREGISTER_RESPONSE = 15
    PROVIDER_MOTION = 16
    PROVIDER_BUTTON = 17
    BUTTON_STATE = 18
    ERROR = 255


@dataclass(frozen=True)
class Message:
    message_type: MessageType
    request_id: int
    payload: bytes


class Decoder:
    def __init__(self, payload: bytes):
        self._payload = payload
        self._offset = 0

    def _read(self, size: int) -> bytes:
        end = self._offset + size
        if end > len(self._payload):
            raise ValueError("Orbit3D message is truncated")
        value = self._payload[self._offset : end]
        self._offset = end
        return value

    def u8(self) -> int:
        return self._read(1)[0]

    def u16(self) -> int:
        return struct.unpack(">H", self._read(2))[0]

    def u32(self) -> int:
        return struct.unpack(">I", self._read(4))[0]

    def u64(self) -> int:
        return struct.unpack(">Q", self._read(8))[0]

    def i32(self) -> int:
        return struct.unpack(">i", self._read(4))[0]

    def text(self) -> str:
        return self._read(self.u16()).decode("utf-8")

    @property
    def empty(self) -> bool:
        return self._offset == len(self._payload)


def text(value: str) -> bytes:
    encoded = value.encode("utf-8")
    if len(encoded) > 0xFFFF:
        raise ValueError("Orbit3D text field is too long")
    return struct.pack(">H", len(encoded)) + encoded


def send_message(
    connection: socket.socket,
    message_type: MessageType,
    request_id: int,
    payload: bytes = b"",
) -> None:
    if len(payload) > MAX_PAYLOAD_SIZE:
        raise ValueError("Orbit3D payload exceeds the protocol limit")
    header = HEADER.pack(
        MAGIC,
        VERSION_MAJOR,
        VERSION_MINOR,
        int(message_type),
        len(payload),
        request_id,
    )
    connection.sendall(header + payload)


def receive_exact(connection: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    received = 0
    while received < size:
        chunk = connection.recv(size - received)
        if not chunk:
            raise ConnectionError("OrbitHub disconnected")
        chunks.append(chunk)
        received += len(chunk)
    return b"".join(chunks)


def receive_message(connection: socket.socket) -> Message:
    magic, major, minor, raw_type, payload_size, request_id = HEADER.unpack(
        receive_exact(connection, HEADER.size)
    )
    if magic != MAGIC:
        raise ValueError("Invalid Orbit3D message magic")
    if major != VERSION_MAJOR or minor != VERSION_MINOR:
        raise ValueError("Unsupported Orbit3D protocol version")
    if payload_size > MAX_PAYLOAD_SIZE:
        raise ValueError("Orbit3D payload exceeds the protocol limit")
    return Message(
        message_type=MessageType(raw_type),
        request_id=request_id,
        payload=receive_exact(connection, payload_size) if payload_size else b"",
    )


class MessageReader:
    """Retains partial packets across poll deadlines. One reader per connection."""

    def __init__(self):
        self._buffer = bytearray()

    def receive(self, connection: socket.socket, timeout: float | None) -> Message:
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            required = HEADER.size
            if len(self._buffer) >= HEADER.size:
                magic, major, minor, raw_type, size, request_id = HEADER.unpack(
                    self._buffer[: HEADER.size]
                )
                if magic != MAGIC or (major, minor) != (VERSION_MAJOR, VERSION_MINOR):
                    raise ValueError("Invalid or incompatible Orbit3D header")
                if size > MAX_PAYLOAD_SIZE:
                    raise ValueError("Orbit3D payload exceeds the protocol limit")
                required += size
                if len(self._buffer) == required:
                    message = Message(
                        MessageType(raw_type), request_id, bytes(self._buffer[HEADER.size :])
                    )
                    self._buffer.clear()
                    return message
            remaining = None if deadline is None else max(0, deadline - time.monotonic())
            if not select.select([connection], [], [], remaining)[0]:
                raise socket.timeout("OrbitHub read deadline expired")
            chunk = connection.recv(required - len(self._buffer))
            if not chunk:
                raise ConnectionError("OrbitHub disconnected")
            self._buffer.extend(chunk)
