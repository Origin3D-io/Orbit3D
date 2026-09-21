# Hardware provider evaluation

Run this checklist for each provider and application combination. Record the OS,
application, SDK, provider, and device firmware versions with the results.

## Setup

1. Start one OrbitHub instance and the hardware provider.
2. Connect the device and run `examples/monitor.py` with the Python SDK installed.
3. Confirm device identity, capabilities, and button count.
4. Open an application consumer and verify its selected device.

## Motion and buttons

- Verify all six canonical axes in both directions before testing camera mappings.
- Test small, sustained, and combined movements; confirm zero on release.
- Check behavior at different provider rates and viewport frame rates.
- Verify every button's press and release, including quick clicks and held buttons.
- Subscribe while a button is held; its snapshot must not trigger a command.
- Confirm inactivity beyond 250 ms stops motion in the consumer.

## Recovery and concurrency

- Unplug during motion and while holding a button, then reconnect.
- Restart the provider and broker separately while applications remain open.
- Start applications with no device connected, then attach one.
- Switch foreground applications and confirm no background clicks replay.
- Test simultaneous consumers and explicit selection with multiple devices.
- Check sleep/wake and sustained idle behavior.

Record observed failures and untested cases separately. Device-specific USB
encoding is outside the application protocol.
