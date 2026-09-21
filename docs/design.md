# Design

## Local transport

We use loopback TCP so native and Python clients share one transport on Windows,
macOS, and Linux. Named pipes or Unix sockets would need platform-specific paths.
Port 43120 is a configurable default, not a security mechanism or a device ID.

## Input, not camera commands

The broker distributes six-axis velocity requests. Applications own camera scale,
focus, pivots, and commands. Sending camera transforms instead would tie providers
to a particular application's scene and navigation conventions.

## Numeric range

The wire uses signed integers with full-scale magnitude 1,000,000. This gives
providers a common scale without exposing their sensor resolution. The example
camera helper retains a scale of 511 because its sensitivities were tuned at that
range; it keeps fractional values. New applications can use normalized input
directly. Neither number sets the application's maximum camera speed.

## Freshness and liveness

We treat motion freshness separately from connection health. The 250 ms motion
expiry bounds continued movement if samples stop. The three-second provider
timeout tolerates missed one-second heartbeats before removing the device.
Two-second hello and partial-message limits prevent stalled clients from holding
resources indefinitely. These are operational bounds, not latency targets.

## Queue policy

New motion replaces older motion for the same device only within an uninterrupted
run of motion messages. A button transition, device event, or response is an
ordering boundary. Replaying every sample would make a slow application lag
behind the hand; dropping those boundaries could change button behavior.

## Resource bounds

The broker allows 32 devices, 64 connections, and 256 queued messages per client.
These are bounded desktop-workload budgets, not throughput benchmarks. A consumer
that fills its queue is disconnected rather than blocking other applications.
Each device's 32-button limit follows the protocol's button-state bitmask.

## Concurrency

Each connection has a reader and writer. Socket writes happen outside broker
state locks. An event lock serializes state changes with notifications; its
recursive form allows request handlers to use the same event methods as adapters.
Shutdown closes client sockets and waits for connection workers to finish.

## Local trust

We trust programs on the local computer. Loopback limits network exposure but
does not authenticate a publisher or isolate users on a shared machine. Adding
authentication would require a credential and installation policy, not just a
different port. See [Security](../SECURITY.md).
