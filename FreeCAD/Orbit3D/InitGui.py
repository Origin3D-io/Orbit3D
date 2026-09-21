"""FreeCAD GUI bootstrap for the Orbit3D workbench."""

from __future__ import annotations

import FreeCADGui as Gui

try:
    from PySide import QtCore
except ImportError:
    try:
        from PySide2 import QtCore
    except ImportError:
        from PySide6 import QtCore


class Orbit3DWorkbench(Workbench):
    MenuText = "Orbit3D"
    ToolTip = "Orbit3D viewport control through OrbitHub"
    Icon = """
        /* XPM */
        static const char * orbit3d_icon[] = {
        "16 16 3 1",
        "  c None",
        ". c #2F80ED",
        "+ c #111827",
        "                ",
        "       ++       ",
        "       ++       ",
        "      ....      ",
        "   ..........   ",
        "   ...++++...   ",
        " ++...++++...++ ",
        " ++...++++...++ ",
        " ++...++++...++ ",
        "   ...++++...   ",
        "   ..........   ",
        "      ....      ",
        "       ++       ",
        "       ++       ",
        "                ",
        "                "};
        """

    def Initialize(self):
        import orbit3d_bootstrap

        orbit_commands = orbit3d_bootstrap.commands()

        orbit_commands.register_commands()
        toolbar_commands = ["Orbit3D_ToggleNativeInput", "Orbit3D_FitView"]
        menu_commands = toolbar_commands
        self.appendToolbar("Orbit3D", toolbar_commands)
        self.appendMenu("Orbit3D", menu_commands)

    def Activated(self):
        import orbit3d_bootstrap

        current = orbit3d_bootstrap.controller()
        if not current.running:
            current.start()

    def Deactivated(self):
        # Input remains active across workbench switches.
        return


Gui.addWorkbench(Orbit3DWorkbench())


def _autostart_orbit_controller() -> None:
    try:
        import orbit3d_bootstrap

        import FreeCAD as App

        App.Console.PrintMessage(f"[Orbit3D] FreeCAD adapter {orbit3d_bootstrap.ADDON_VERSION}\n")
        current = orbit3d_bootstrap.controller()
        if not current.running:
            current.start()
    except Exception as exc:
        import FreeCAD as App

        App.Console.PrintError(f"[Orbit3D] Startup failed: {exc}\n")


QtCore.QTimer.singleShot(1200, _autostart_orbit_controller)
