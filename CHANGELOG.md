# Changelog

## 0.2.1 — 2026-10-06

- Broker and Python SDK: 0.2.1. Blender addon: 0.2.4. FreeCAD workbench: 0.3.4.
- FreeCAD selects a surface pivot and keeps its marker attached during pan, zoom, and rotation.
- Improved FreeCAD reconnection after a delayed reader shutdown.
- Reference addons use OrbitHub with fractional motion and independent button handling.
- Added explicit input-reset events to the Python SDK.
- Broker supports graceful SIGINT/SIGTERM shutdown on Unix and Ctrl+C/Break on Windows.
- Added broker version reporting and stricter command-line port validation.
- Wire protocol remains 0.2.

## Initial SDK distribution

- Protocol 0.2, local broker, C/C++ consumer SDK, and Python consumer/provider SDK.
- Blender and FreeCAD reference integrations and automated platform tests.
