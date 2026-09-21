# OrbitHub

The local input broker for Orbit3D. Providers publish normalized motion and
button events; applications receive them through the SDK.

OrbitHub provides device discovery, subscriptions, held-button snapshots, and
independent consumer queues. It opens no hardware and assigns no camera behavior.

## Build

Run from this directory with CMake and a C++17 compiler:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build --config Debug
ctest --test-dir build -C Debug --output-on-failure
```

On macOS or Linux, `make` and `make test` are also available.

## Run

```sh
# macOS / Linux
./build/orbithub --port 43120
```

```powershell
# Windows with the Visual Studio generator
.\build\Debug\orbithub.exe --port 43120
```

Add `--simulate` to evaluate input without hardware. The service listens on
`127.0.0.1` only. See [Security](../SECURITY.md) for the local trust boundary.

## SDKs

| Interface | Location |
| --- | --- |
| C consumer API | `include/orbit3d/orbit3d.h` |
| C++ consumer wrapper | `include/orbit3d/orbit3d.hpp` |
| Python consumer and provider SDK | `sdk/python` |

Install the Python package with `python -m pip install ./sdk/python`, then run
`python examples/monitor.py` to inspect connected devices and events.
`examples/provider_demo.py` implements a hardware-free provider.

Providers send input or ping at least once per second. Applications integrate
motion with elapsed time and stop on stale input. See the
[input contract](docs/input-contract.md) for the complete behavior.

## Documentation

- [Application integration](../docs/integration.md)
- [Wire protocol](docs/ipc-protocol.md)
- [Service lifecycle](docs/service-lifecycle.md)
- [Hardware evaluation](docs/hardware-test.md)
- [Version and deployment](../docs/compatibility.md)
