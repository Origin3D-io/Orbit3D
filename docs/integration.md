# Application integration

## Responsibilities

OrbitHub discovers devices and distributes input. It does not choose a pivot,
move a camera, set application sensitivity, or arbitrate foreground focus.
No firmware/configuration commands are part of the public protocol.

Connect on a worker thread. Use one thread per SDK connection; do not poll and
issue requests concurrently on the same consumer. Keep viewport operations on
the application's UI thread. The SDK does not start OrbitHub or reconnect for you.

## Consumer sequence

1. Connect to `127.0.0.1:43120` with the matching 0.2 SDK.
2. Subscribe to motion, buttons, and device events, then list devices.
3. Select the sole connected device or an explicit identity. Filter events by
   its runtime ID. Refresh discovery on device events; never reuse old IDs.
4. Store the latest motion and local receipt time. Queue button transitions
   separately. State snapshots initialize held buttons without running commands.
5. On each viewport tick, integrate current input using elapsed seconds, not
   packet count. Clamp long frame intervals. Expire motion after 250 ms.
6. While inactive, drain events without executing movement or button commands.
   Clear state on disconnect and never replay background clicks.
7. On transport failure or queue overflow, clear input, close the connection,
   and reconnect with bounded backoff. Repeat discovery and subscription.

## Camera mapping

To inspect canonical input with a running broker and one provider:

```python
import socket
from orbit3d_hub import Client, MOTION, MotionEvent, select_device

with Client() as client:
    client.subscribe(MOTION)
    device = select_device(client.list_devices())
    if device is None:
        raise RuntimeError("Connect one device or select an explicit identity")
    while True:
        try:
            event = client.poll(timeout=0.2)
        except socket.timeout:
            continue
        if isinstance(event, MotionEvent) and event.device_id == device.device_id:
            print(event.tx / 1_000_000, event.ty / 1_000_000, event.tz / 1_000_000)
```

This is a console example. An application uses the sequence above to handle
focus, reconnects, button commands, and UI-thread updates.

Normalize each axis by `1_000_000`. Values request velocity, not displacement.
Translation uses view-relative right, up, and toward-viewer axes. Rotation follows
the right-hand rule. Choose camera or object navigation and document the signs.

Scale pan by visible scene size and elapsed time. Orthographic zoom changes view
height; perspective zoom is an application choice. Apply a combined rotation
around the chosen pivot. OrbitHub does not transmit or calculate that pivot.

The example integrations use `to_viewport_motion` for their camera frame and scale.
This conversion keeps fractional values. New integrations should
consume canonical axes directly. Do not copy viewport-specific axis swaps into
a hardware provider.

`ViewportMotion` contains motion only; handle buttons through the event stream.

## APIs

| Language | Entry point | Role |
| --- | --- | --- |
| C | `OrbitHub/include/orbit3d/orbit3d.h` | Consumer |
| C++ | `OrbitHub/include/orbit3d/orbit3d.hpp` | Consumer wrapper |
| Python | `orbit3d_hub.Client`, `InputState` | Consumer |
| Python | `orbit3d_hub.Provider` | Hardware provider |

For C/C++, add `OrbitHub` with CMake `add_subdirectory` and link `orbit3d_sdk`.
The target includes its headers, static-build definition, and platform libraries.
The executable examples in `OrbitHub/tests/sdk_smoke.cpp` and `c_sdk_smoke.c`
exercise discovery, subscription, and polling; they are not camera controllers.

`InputState` holds one selected device's motion and ordered buttons. The caller
must filter device IDs, reset it on disconnect, and enforce focus. A local
`InputReset` clears held buttons without executing commands. Native clients
must implement equivalent state handling. Never integrate a stale sample.

## Hardware providers

Use your own hardware identity and device API. Register
vendor/product/serial and button count, then publish canonical motion. Use a
unique serial for multiple otherwise identical devices.

Send at least 20 samples/second during sustained movement and zero on release.
Send input or ping at least once per second, including while idle. Registration
expires after three seconds without a complete message. Reconnect and register
again after broker failure. The broker replaces provider timestamps at receipt.

See [provider_demo.py](../OrbitHub/examples/provider_demo.py) and the
[wire contract](../OrbitHub/docs/ipc-protocol.md) for non-Python providers.
