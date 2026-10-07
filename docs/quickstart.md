# Build and run

## Prebuilt runtime

Download OrbitHub from the [v0.2.1 release](https://github.com/Origin3D-io/Orbit3D/releases/tag/v0.2.1):

- `orbithub-windows-x64.zip` for Windows x64.
- `orbithub-macos-arm64.zip` for macOS on Apple Silicon.
- `orbithub-linux-x64.zip` for Linux x64.

Extract the archive matching your OS and architecture. These are unsigned
evaluation binaries. The release includes SHA-256 checksums in `SHA256SUMS.txt`.

Run `.\orbithub.exe --simulate` on Windows or `./orbithub --simulate` on
macOS/Linux. If needed on macOS/Linux, run `chmod +x orbithub`
after extraction. The simulator needs no hardware provider. Install the Python
SDK and run the monitor below, or connect an application integration.

## Build from source

Requirements: CMake 3.20+, a C++17 compiler, and Python 3.10+. On Windows, use
Visual Studio Build Tools with the C++ workload. Run these from the repo root.

```sh
cmake -S OrbitHub -B OrbitHub/build -DCMAKE_BUILD_TYPE=Debug
cmake --build OrbitHub/build --config Debug
ctest --test-dir OrbitHub/build -C Debug --output-on-failure
python -m pip install ./OrbitHub/sdk/python
```

Start a simulated device without hardware:

```sh
# macOS / Linux, single-configuration generator
./OrbitHub/build/orbithub --simulate
```

```powershell
# Windows, Visual Studio generator
.\OrbitHub\build\Debug\orbithub.exe --simulate
```

In another terminal:

```sh
python OrbitHub/examples/monitor.py
```

To test a provider instead, start the broker without `--simulate`, then run
`python OrbitHub/examples/provider_demo.py` in a separate terminal. Do not run
two brokers on the same port. Port 43120 is the default; `--port` selects another.

For physical input, start the device manufacturer's provider. Keep it running
alongside the broker. OrbitHub does not read hardware directly.

## Application addons

Download `Orbit3D-Blender.zip` or `Orbit3D-FreeCAD.zip` from the
[v0.2.1 release](https://github.com/Origin3D-io/Orbit3D/releases/tag/v0.2.1).
To build the same archives from source instead:

```sh
python Blender/build_addon.py
python FreeCAD/build_workbench.py
```

Install `Orbit3D-Blender.zip` through Blender's addon manager.
For FreeCAD, extract `Orbit3D-FreeCAD.zip` into the active user
`Mod` directory. FreeCAD's Python console reports the base with
`App.getUserAppDataDir()`. Restart the application after installing its addon.

Each archive includes the Python SDK and license. For source development,
install the SDK with `python -m pip install -e ./OrbitHub/sdk/python`.

Run `orbithub --version` to identify a runtime build. Stop it with Ctrl+C;
Unix hosts can also send SIGTERM. Windows process termination and forced kills
do not run shutdown handlers.
