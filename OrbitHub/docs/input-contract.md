# Input Contract 0.2

Orbit3D carries processed movement intent and button events. Providers own hardware processing. Applications own camera behavior and command bindings.

## Motion

All six axes are signed integers from `-1000000` to `1000000`. Zero means rest. Values are dimensionless velocity requests, not distances, angles, or absolute coordinates.

The reference frame is right-handed: positive X points right, positive Y points up, and positive Z points toward the viewer. Rotation uses the right-hand rule around each corresponding axis. Providers convert their device frame into this frame. Applications choose camera or object navigation and apply the appropriate camera transform.

Applications integrate the latest input using elapsed time. They must not multiply speed by the number of packets received. Clamp a viewport time step after a long pause, and stop motion after 250 ms without a fresh sample. Providers should send at least 20 samples per second during sustained movement and send zero when released.

The reference integrations use a 16 ms reference step for sensitivity scaling.
New integrations should define their own camera speeds while
preserving time-based integration. See [validation](../../docs/validation.md)
for implementation coverage.

## Buttons

A device declares zero to 32 buttons. IDs are one-based and remain stable for that device. Button transitions use an ordered queue separate from replaceable motion. A state snapshot initializes held buttons without executing commands. Disconnect clears state. A queue overflow requires reconnect and resynchronization.

The current Blender and FreeCAD reference command is button 1 for Fit View. Other button IDs reach the application and remain available for application-specific bindings.

## Focus

Applications consume input only while active. Background applications drain events without running commands. Re-activation must not replay background clicks. OrbitHub does not choose which CAD application owns focus.

FreeCAD checks its main window activity. Blender uses Windows foreground-process detection on Windows and window deactivation events on other systems. Test switching applications and multiple windows on each supported platform.

## Selection and Identity

An empty selection chooses a device only when exactly one is connected. With multiple devices, the application requests an explicit `vendor/product/serial` identity and does not silently fall back when that device disappears. Use a unique serial to distinguish otherwise identical devices. Runtime numeric IDs are valid only for the current registration.

Blender exposes Device Identity in its add-on preferences. FreeCAD uses `DeviceIdentity` in `User parameter:BaseApp/Preferences/Orbit3D`. The `ORBIT3D_DEVICE` environment variable can also supply the identity at launch. If a provider supplies no unique serial, otherwise identical devices cannot be selected unambiguously by identity.
