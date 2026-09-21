# Orbit3D wire protocol 0.2

## Transport

- TCP on `127.0.0.1`
- Default port `43120`
- One ordered stream per connection
- Maximum payload size of 65,536 bytes

Consumer requests use a nonzero request ID. Events and one-way provider updates use request ID `0`.

## Header

All integers use big-endian byte order.

```text
byte 0-3    magic: O3DH
byte 4      protocol major
byte 5      protocol minor
byte 6-7    message type
byte 8-11   payload size
byte 12-15  request id
```

## Message Types

| Value | Message |
|---:|---|
| 1 | Hello request |
| 2 | Hello response |
| 3 | List devices request |
| 4 | Device list |
| 5 | Subscribe request |
| 6 | Subscribe response |
| 7 | Motion event |
| 8 | Button event |
| 9 | Device event |
| 10 | Ping |
| 11 | Pong |
| 12 | Provider register request |
| 13 | Provider register response |
| 14 | Provider unregister request |
| 15 | Provider unregister response |
| 16 | Provider motion |
| 17 | Provider button |
| 18 | Button state snapshot |
| 255 | Error |

## Device Capabilities

```text
bit 0  6-DOF motion
bit 1  buttons
```

## Provider Registration

Register request:

```text
u32 capabilities
u8  button_count
u8  reserved
u8  reserved
u8  reserved
string vendor
string product
string serial
```

Vendor and product are required. Identity fields contain at most 95 UTF-8 bytes each, without ASCII control characters. The broker accepts at most 32 devices and 64 concurrent connections. Button count ranges from `0` to `32`. A successful response contains the assigned `u32 device_id`.

Device IDs are assigned by OrbitHub and remain valid until the provider unregisters the device or disconnects. One provider connection may register multiple devices.

Motion capability is required in 0.2. Button capability must be set exactly when
button count is nonzero. Unknown capability bits are rejected. Device identity
strings are metadata, not authenticated identities; duplicates are not rejected
by the broker. Consumers must not silently select an ambiguous identity.

## Provider Motion

Provider motion is one-way and uses request ID `0`.

```text
u32 device_id
u64 timestamp_us
i32 tx
i32 ty
i32 tz
i32 rx
i32 ry
i32 rz
```

Every axis must be between `-1000000` and `1000000`. Zero is rest. Values express normalized movement intent, not absolute positions or per-packet displacements. See `input-contract.md` for directions, timing, focus, and selection.

## Provider Button

Provider button is one-way and uses request ID `0`.

```text
u32 device_id
u64 timestamp_us
u16 button_id
u8  pressed
u8  reserved
```

Button IDs are one-based and may not exceed the registered button count. Providers send transitions. OrbitHub ignores a repeated state for the same button.

## Provider Unregister

The request contains one `u32 device_id`. The response is empty. OrbitHub also unregisters every device owned by a provider when its connection closes. Held buttons are released before the device disconnect event.

## Button State Snapshot

When a consumer subscribes to buttons, OrbitHub sends message 18 for each registered device: `u32 device_id`, followed by `u32 buttons`. Bit 0 is button 1. Snapshots initialize state and must not execute commands. Subsequent button events carry ordered transitions.

## Consumer Device List

```text
u16 device_count
repeat device_count:
  u32 device_id
  u32 capabilities
  u8  connected
  u8  button_count
  u16 reserved
  string vendor
  string product
  string serial
```

## Consumer Events

Motion and button events use the same payloads as provider motion and provider button. A device event contains:

```text
u32 device_id
u8  connected
```

Subscriptions use bit 0 for motion, bit 1 for buttons, and bit 2 for device events.

## Delivery and Limits

Each consumer has a queue of at most 256 outbound messages. Pending motion for a device may be replaced within a run of motion events. Replies, button transitions, snapshots, and device events preserve their order. Queue overflow or a stalled write disconnects that consumer. Applications must reconnect and resynchronize state.

Hello must be the first request and complete within approximately two seconds of connection. Invalid requests do not extend this deadline. An incomplete packet times out after approximately two seconds. A provider must send a complete input message or ping at least once per second; three seconds of inactivity unregisters its devices and releases buttons. Consumer connections may remain idle.

Consumers use broker-assigned monotonic microsecond timestamps. Provider timestamps are informational; OrbitHub stamps accepted input at receipt. Consumers determine freshness with their local receive time, without subtracting clocks from different processes.

Hello has an empty request and returns a string `OrbitHub` followed by `u32` server capabilities: bit 0 consumers, bit 1 providers. Strings use a `u16` byte length followed by UTF-8 bytes. Subscribe sends a `u32` mask and returns the accepted mask. Ping and pong are empty. Errors contain a string.

Local programs are trusted to connect and publish input without authentication. The broker binds only to IPv4 loopback. See [Security](../../SECURITY.md) for the trust boundary and deployment constraints.

## Exclusions

This protocol does not carry device configuration, firmware, vendor commands, or emulation.

## Version Rules

- Version 0.2 requires an exact major/minor match. Older runtimes and SDKs must be upgraded together.
- Reserved provider fields must be zero; nonzero values are rejected.
- Unknown request types return an error.
