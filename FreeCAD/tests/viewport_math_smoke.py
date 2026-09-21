"""Run with FreeCADCmd: real vector/quaternion math, no HID or document writes."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import FreeCAD as App

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "FreeCAD" / "Orbit3D"))
sys.path.insert(0, str(ROOT / "OrbitHub" / "sdk" / "python" / "src"))
import orbit3d_bootstrap  # noqa: F401 - creates the isolated workbench package

driver_module = importlib.import_module("orbit3d_freecad.viewport_driver")
navigation = importlib.import_module("orbit3d_freecad.navigation")
driver_module.App = App
driver_module.coin = object()


class Position:
    def __init__(self):
        self.xyz = (0, 0, 10)

    def getValue(self):
        return self

    def setValue(self, x, y, z):
        self.xyz = (x, y, z)


class View:
    def __init__(self, orientation):
        self.orientation = orientation
        position = Position()
        # Match Coin's position.getValue().getValue() convention.
        self.camera = SimpleNamespace(
            position=SimpleNamespace(
                getValue=lambda: SimpleNamespace(getValue=lambda: position.xyz),
                setValue=position.setValue,
            ),
            focalDistance=SimpleNamespace(getValue=lambda: 10.0),
        )
        self.camera.height = SimpleNamespace(getValue=lambda: 10.0)
        self.position = position

    def getCameraNode(self):
        return self.camera

    def getCameraOrientation(self):
        return self.orientation

    def setCameraOrientation(self, rotation):
        self.orientation = rotation

    def redraw(self):
        pass


def run():
    nav = navigation.to_navigation_frame(navigation.hub.ViewportMotion(1, 2, 3, 4, 5, 6))
    assert (nav.pan_x, nav.zoom, nav.pan_y, nav.pitch, nav.yaw, nav.roll) == (-1, 2, 3, 4, 6, 5)
    for orientation in (App.Rotation(), App.Rotation(App.Vector(1, 2, 3), 61)):
        for field, axis, sign in (
            ("rx", (1, 0, 0), -1),
            ("ry", (0, 0, 1), -1),
            ("rz", (0, 1, 0), 1),
        ):
            view = View(orientation)
            driver = driver_module.OrbitViewportDriver()
            driver.active_view = lambda: view
            before = App.Vector(*view.position.xyz) + orientation.multVec(App.Vector(0, 0, -10))
            motion = navigation.hub.ViewportMotion(**{field: 100})
            assert driver.apply_motion(motion)
            expected = orientation.multiply(
                App.Rotation(App.Vector(*axis), sign * 100 * driver.orbit_speed)
            )
            for basis in (App.Vector(1, 0, 0), App.Vector(0, 1, 0), App.Vector(0, 0, 1)):
                assert (expected.multVec(basis) - view.orientation.multVec(basis)).Length < 1e-8
            after = App.Vector(*view.position.xyz) + view.orientation.multVec(App.Vector(0, 0, -10))
            assert (after - before).Length < 1e-8, "Orbit focal point moved"
        for field, direction in (("tx", App.Vector(-1, 0, 0)), ("tz", App.Vector(0, 1, 0))):
            view = View(orientation)
            driver = driver_module.OrbitViewportDriver()
            driver.active_view = lambda: view
            driver.apply_motion(navigation.hub.ViewportMotion(**{field: 100}))
            offset = App.Vector(*view.position.xyz) - App.Vector(0, 0, 10)
            expected = orientation.multVec(direction) * (100 * driver.pan_speed * 10)
            assert (offset - expected).Length < 1e-8, "Pan sign or camera-local mapping wrong"
    print("FREECAD_VIEWPORT_MATH_OK")


run()
