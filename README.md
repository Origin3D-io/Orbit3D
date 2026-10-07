# Orbit3D

Open 6-DOF input for CAD and 3D applications.

Orbit3D gives CAD and 3D applications a common interface for motion, buttons,
and device discovery. Hardware manufacturers implement a provider; application
developers integrate the SDK.

**OrbitHub** distributes input locally to connected applications. Providers own
device communication; applications own navigation and commands.

```text
Hardware -> provider -> OrbitHub -> application SDK -> viewport
```

## Capabilities

- Six normalized motion axes in a defined coordinate frame.
- Device discovery and selection across multiple providers.
- Ordered button events and held-button state synchronization.
- Independent application connections with bounded input queues.
- C, C++, and Python consumer SDKs; a Python provider SDK.
- Blender and FreeCAD example integrations.

## Host integration

Application developers add native viewport navigation through the C, C++, or
Python SDK. The host maps six-axis input to pan, zoom, and rotation, chooses the
pivot, and handles focus and button commands. Device providers and OrbitHub run
separately; the host needs no USB driver or device-specific code.

Integration requires camera control and UI-thread scheduling through a supported
extension API or native application code.
See [Application integration](docs/integration.md) for the implementation sequence.

## Downloads

[Download v0.2.1](https://github.com/Origin3D-io/Orbit3D/releases/tag/v0.2.1)
for the OrbitHub runtime and Blender/FreeCAD addon archives. See
[Build and run](docs/quickstart.md) for installation and a hardware-free demo.

## Documentation

| Document | Purpose |
| --- | --- |
| [Build and run](docs/quickstart.md) | Build the runtime and test without hardware |
| [Application integration](docs/integration.md) | Discovery, input handling, and viewport updates |
| [Input contract](OrbitHub/docs/input-contract.md) | Axes, units, timing, buttons, and focus |
| [Wire protocol](OrbitHub/docs/ipc-protocol.md) | Message formats and transport |
| [Validation](docs/validation.md) | Automated tests and provider evaluation |
| [Compatibility](docs/compatibility.md) | API availability and deployment requirements |
| [Security](SECURITY.md) | Local transport trust boundary |

## Repository

| Path | Contents |
| --- | --- |
| `OrbitHub/` | Broker, SDKs, examples, and protocol tests |
| `Blender/` | Blender example integration |
| `FreeCAD/` | FreeCAD example integration |

See [Design](docs/design.md) for implementation choices and
[Limitations](docs/limitations.md) for scope and platform constraints.

The protocol is independent of a hardware vendor's USB identity, firmware, and
control application. The broker opens no hardware itself; providers publish
through the protocol using their own device interfaces.

## License

MIT. See [LICENSE](LICENSE) and [dependencies](docs/licensing.md).
