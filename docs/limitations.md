# Limitations

- OrbitHub listens on IPv4 loopback only. It is not a remote-input service.
- Local clients are trusted; publisher identity is not authenticated. See
  [Security](../SECURITY.md).
- Application support requires an integration. The SDK does not install a system
  input driver, start the broker, or choose application navigation behavior.
- FreeCAD perspective zoom uses camera focal distance, independently of the
  surface point selected for rotation.
- The Blender integration is a legacy-format addon, not an Extensions package.
- Linux has automated coverage but no recorded physical-device validation.
  Sleep/wake and end-to-end latency are not covered by the published validation.

Tested application versions are listed in [Validation](validation.md).
