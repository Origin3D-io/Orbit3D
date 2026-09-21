# Validation

Automated builds and protocol tests run on Windows, macOS, and Linux in
[GitHub Actions](../.github/workflows/test.yml). Coverage includes
message parsing, deadlines, device discovery, provider ownership, button ordering,
stale input, consumer isolation, SDKs, and addon packaging.

Run the suite from the repository root:

```sh
cmake -S OrbitHub -B OrbitHub/build -DCMAKE_BUILD_TYPE=Debug
cmake --build OrbitHub/build --config Debug
ctest --test-dir OrbitHub/build -C Debug --output-on-failure
```

Use the [provider evaluation checklist](../OrbitHub/docs/hardware-test.md) for
physical-device and application testing.

## Verified configurations

Physical-controller navigation checks, recorded 2026-09-20:

| OS | Application | Addon |
| --- | --- | --- |
| Windows 11 | Blender 5.0.1 | 0.2.4 |
| Windows 11 | FreeCAD 1.0.2 | 0.3.4 |
| Windows 10 | FreeCAD 1.1.3 | 0.3.2 |
| macOS 26.5, Apple Silicon | Blender 5.1.1 | 0.2.4 |
| macOS 26.5, Apple Silicon | FreeCAD 1.1.3 | 0.3.2 |

These results apply to the listed versions and navigation checks, not to every
hardware configuration or application feature.
