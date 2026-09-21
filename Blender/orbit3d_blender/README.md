# Orbit3D for Blender

Reference integration for Blender viewport navigation using OrbitHub.

## Install

Build from the repository root:

```sh
python Blender/build_addon.py
```

Install `Blender/dist/Orbit3D-Blender.zip` through Blender's addon manager.
The archive includes the Python SDK. Start OrbitHub and a hardware provider,
then enable the addon.

## Input behavior

The addon selects a device automatically when exactly one is connected. For
explicit selection, set Device Identity to `vendor/product/serial` in preferences.

Motion expires after 250 ms without fresh input. Button transitions are queued
separately from motion; initial held-button snapshots do not execute commands.
Button 1 is mapped to `Frame All`. Navigation runs only while the application
is active.

See [validation](../../docs/validation.md) for recorded test coverage.
