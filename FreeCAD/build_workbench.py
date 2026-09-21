#!/usr/bin/env python3
"""Build a self-contained Orbit3D FreeCAD workbench archive."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "FreeCAD" / "Orbit3D"
SDK = ROOT / "OrbitHub" / "sdk" / "python" / "src" / "orbit3d_hub"
DIST = ROOT / "FreeCAD" / "dist"
STAGE = ROOT / "FreeCAD" / "build" / "Orbit3D"


def ignore_generated(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name == "__pycache__" or name.endswith(".pyc")}


def main() -> None:
    if not SOURCE.is_dir() or not SDK.is_dir():
        raise SystemExit("Orbit3D workbench or OrbitHub Python SDK is missing")

    shutil.rmtree(STAGE.parent, ignore_errors=True)
    DIST.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE, STAGE, ignore=ignore_generated)
    shutil.copytree(SDK, STAGE / "orbit3d_hub", ignore=ignore_generated)
    shutil.copy2(ROOT / "LICENSE", STAGE / "LICENSE")

    archive = DIST / "Orbit3D-FreeCAD"
    output = Path(shutil.make_archive(str(archive), "zip", STAGE.parent, STAGE.name))
    print(output)


if __name__ == "__main__":
    main()
