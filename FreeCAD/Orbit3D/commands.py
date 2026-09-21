"""FreeCAD commands exposed by the Orbit3D workbench."""

from __future__ import annotations

import os

from . import controller

try:
    import FreeCADGui as Gui

    import FreeCAD as App
except ImportError:  # pragma: no cover - unavailable outside FreeCAD
    App = None
    Gui = None

_FILE_PATH = globals().get("__file__")
if not _FILE_PATH:
    _FILE_PATH = os.path.join(os.getcwd(), "commands.py")
MODULE_DIR = os.path.dirname(os.path.abspath(_FILE_PATH))
ICON_PATH = os.path.join(MODULE_DIR, "resources", "icons", "Orbit3D.svg")


def _print_message(message: str) -> None:
    if App is not None:
        App.Console.PrintMessage(f"{message}\n")


def _print_error(message: str) -> None:
    if App is not None:
        App.Console.PrintError(f"{message}\n")


class OrbitToggleNativeInputCommand:
    def GetResources(self):
        running = controller.get_controller().running
        label = "Stop Orbit3D Input" if running else "Start Orbit3D Input"
        tip = "Toggle Orbit3D input for the active FreeCAD 3D view"
        return {
            "Pixmap": ICON_PATH,
            "MenuText": label,
            "ToolTip": tip,
        }

    def IsActive(self):
        return Gui is not None

    def Activated(self):
        current = controller.get_controller()
        try:
            running = current.toggle()
            suffix = f" (status: {current.status})"
            _print_message(
                ("Orbit3D input started" if running else "Orbit3D input stopped") + suffix
            )
        except Exception as exc:
            _print_error(f"Orbit3D toggle failed: {exc}")


class OrbitFitViewCommand:
    def GetResources(self):
        return {
            "Pixmap": ICON_PATH,
            "MenuText": "Orbit3D Fit View",
            "ToolTip": "Fit all objects in the active 3D view",
        }

    def IsActive(self):
        return Gui is not None and Gui.ActiveDocument is not None

    def Activated(self):
        if Gui is not None and Gui.ActiveDocument is not None:
            Gui.ActiveDocument.ActiveView.fitAll()
            _print_message("Orbit3D fit view")


def register_commands():
    if Gui is None:
        return
    Gui.addCommand("Orbit3D_ToggleNativeInput", OrbitToggleNativeInputCommand())
    Gui.addCommand("Orbit3D_FitView", OrbitFitViewCommand())
