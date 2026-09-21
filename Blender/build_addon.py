#!/usr/bin/env python3
"""Build a self-contained Orbit3D Blender addon archive."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Blender" / "orbit3d_blender"
SDK = ROOT / "OrbitHub" / "sdk" / "python" / "src" / "orbit3d_hub"
DIST = ROOT / "Blender" / "dist"
STAGE = ROOT / "Blender" / "build" / "orbit3d_blender"


def ignore_generated(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name == "__pycache__" or name.endswith(".pyc")}


def main() -> None:
    if not SOURCE.is_dir() or not SDK.is_dir():
        raise SystemExit("Orbit3D addon or OrbitHub Python SDK is missing")

    shutil.rmtree(STAGE.parent, ignore_errors=True)
    DIST.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE, STAGE, ignore=ignore_generated)
    shutil.copytree(SDK, STAGE / "orbit3d_hub", ignore=ignore_generated)
    shutil.copy2(ROOT / "LICENSE", STAGE / "LICENSE")

    archive = DIST / "Orbit3D-Blender"
    output = Path(shutil.make_archive(str(archive), "zip", STAGE.parent, STAGE.name))
    print(output)


if __name__ == "__main__":
    main()
