#!/usr/bin/env python3
from __future__ import annotations

import argparse
import socket

from orbit3d_hub import (
    BUTTONS,
    DEVICES,
    MOTION,
    ButtonEvent,
    ButtonStateEvent,
    Client,
    DeviceEvent,
    MotionEvent,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor OrbitHub devices and events.")
    parser.add_argument("--port", type=int, default=43120)
    args = parser.parse_args()

    with Client(port=args.port) as client:
        devices = client.list_devices()
        if not devices:
            print("OrbitHub is running. No device is connected.")
        for device in devices:
            print(
                f"Connected: {device.vendor} {device.product} "
                f"id={device.device_id} buttons={device.button_count} "
                f"identity={device.vendor}/{device.product}/{device.serial}"
            )

        client.subscribe(MOTION | BUTTONS | DEVICES)
        while True:
            try:
                event = client.poll(timeout=1.0)
            except socket.timeout:
                continue

            if isinstance(event, MotionEvent):
                print(
                    "\r"
                    f"T {event.tx:8d} {event.ty:8d} {event.tz:8d}  "
                    f"R {event.rx:8d} {event.ry:8d} {event.rz:8d}",
                    end="",
                    flush=True,
                )
            elif isinstance(event, ButtonEvent):
                state = "pressed" if event.pressed else "released"
                print(f"\nButton {event.button_id} {state}")
            elif isinstance(event, ButtonStateEvent):
                print(f"\nDevice {event.device_id} initial buttons: 0x{event.buttons:08x}")
            elif isinstance(event, DeviceEvent):
                state = "connected" if event.connected else "disconnected"
                print(f"\nDevice {event.device_id} {state}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nStopped.")
