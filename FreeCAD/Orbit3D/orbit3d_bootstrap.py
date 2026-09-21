"""Isolate workbench modules from other FreeCAD addons' generic module names."""

import importlib
import sys
import types
from pathlib import Path

PACKAGE = "orbit3d_freecad"
ADDON_VERSION = "0.3.4"
if PACKAGE not in sys.modules:
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(Path(__file__).resolve().parent)]
    sys.modules[PACKAGE] = package


def controller():
    return importlib.import_module(PACKAGE + ".controller").get_controller()


def commands():
    return importlib.import_module(PACKAGE + ".commands")
