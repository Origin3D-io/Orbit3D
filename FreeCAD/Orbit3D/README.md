# Orbit3D for FreeCAD

Reference integration for FreeCAD pan, orbit, zoom, and fit-to-view using OrbitHub.
Input starts automatically and remains available across workbench changes.

## Install

Build from the repository root:

```sh
python FreeCAD/build_workbench.py
```

Extract the `Orbit3D` folder from `FreeCAD/dist/Orbit3D-FreeCAD.zip` into the
active FreeCAD user-data directory's `Mod` folder. FreeCAD's Python console
reports that base directory with `App.getUserAppDataDir()`.

Start OrbitHub and a hardware provider, then restart FreeCAD. The archive
includes the Python SDK. The Orbit3D workbench exposes input controls.

## Input behavior

Input comes from **OrbitHub**. Automatic selection requires exactly
one connected device. For explicit selection, set `DeviceIdentity` under
`User parameter:BaseApp/Preferences/Orbit3D` to `vendor/product/serial`, then
restart input.

Motion expires after 250 ms without fresh input. Button transitions are retained
separately; held-button snapshots do not execute commands. Button 1 invokes
`Fit View`. Inactive FreeCAD windows do not execute input.

Rotation uses a visible surface near the view center, falling back to the camera
focal point when no surface is found. The dot marks that rotation center, which
stays attached to that scene point during pan, zoom, and rotation. It disappears
at rest and is selected again after a pause.

Perspective zoom follows the camera's viewing direction and focal distance;
it does not zoom toward an off-center rotation pivot. Orthographic zoom changes
the view height.

See [validation](../../docs/validation.md) for recorded test coverage.
