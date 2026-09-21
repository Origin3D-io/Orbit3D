"""FreeCADCmd regression tests using real Coin cameras, no hardware access."""

import importlib
import math
import sys
from pathlib import Path

from pivy import coin

import FreeCAD as App

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Orbit3D"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "OrbitHub" / "sdk" / "python" / "src"))
import orbit3d_bootstrap  # noqa: F401 - creates the isolated workbench package

m = importlib.import_module("orbit3d_freecad.viewport_driver")
navigation = importlib.import_module("orbit3d_freecad.navigation")
m.App, m.coin = App, coin


class View:
    def __init__(self, perspective=False):
        self.camera = coin.SoPerspectiveCamera() if perspective else coin.SoOrthographicCamera()
        self.camera.position.setValue(0, 0, 1000)
        self.camera.focalDistance = 1000
        if not perspective:
            self.camera.height = 20
        self.orientation = App.Rotation()
        self.root = coin.SoSeparator()

    def getCameraNode(self):
        return self.camera

    def getCameraOrientation(self):
        return self.orientation

    def setCameraOrientation(self, rotation):
        self.orientation = rotation

    def getSceneGraph(self):
        return self.root

    def redraw(self):
        pass

    def position(self):
        return App.Vector(*self.camera.position.getValue().getValue())

    def pivot(self):
        return self.position() + self.orientation.multVec(
            App.Vector(0, 0, -self.camera.focalDistance.getValue())
        )


for perspective in (False, True):
    view = View(perspective)
    driver = m.OrbitViewportDriver()
    driver.active_view = lambda: view
    before = driver.view_height(view.camera)
    pivot = view.pivot()
    driver.apply_motion(navigation.hub.ViewportMotion(ty=100))
    assert math.isclose(
        driver.view_height(view.camera), before * math.exp(-100 * driver.zoom_speed), rel_tol=1e-5
    )
    assert (view.pivot() - pivot).Length < 0.001
    driver.apply_motion(navigation.hub.ViewportMotion(ty=-100))
    assert math.isclose(driver.view_height(view.camera), before, rel_tol=1e-5)
    position = view.position()
    assert driver.apply_motion(navigation.hub.ViewportMotion(tx=1))
    assert (view.position() - position).Length > 0, "Tiny movement discarded"
    pivot = view.pivot()
    driver._last_motion -= 1
    driver.apply_motion(navigation.hub.ViewportMotion(ry=100))
    assert view.root.getNumChildren() == 1, "Pivot marker missing"
    shown = App.Vector(*driver._pivot_coords.point.getValues()[0].getValue())
    assert (shown - pivot).Length < 0.001, "Marker not at the orbit point"
    assert (view.pivot() - pivot).Length < 0.001
    driver.clear_feedback()
    assert view.root.getNumChildren() == 0

for height in (1, 20, 200):
    view = View()
    view.camera.height = height
    view.camera.focalDistance = 1e6
    driver = m.OrbitViewportDriver()
    driver.active_view = lambda: view
    before = view.position()
    driver.apply_motion(navigation.hub.ViewportMotion(tz=100))
    fraction = (view.position() - before).Length / height
    assert math.isclose(fraction, 100 * driver.pan_speed, rel_tol=1e-5), (
        "Pan depends on focal distance"
    )
for perspective in (False, True):
    view = View(perspective)
    point = App.Vector(3, 4, 980)
    view.getSize = lambda: (800, 600)
    view.getObjectInfo = lambda pixel: dict(x=point.x, y=point.y, z=point.z)
    driver = m.OrbitViewportDriver()
    driver.active_view = lambda: view
    local = view.orientation.inverted().multVec(point - view.position())
    for _ in range(80):
        driver.apply_motion(navigation.hub.ViewportMotion(rx=100, ry=40, rz=30))
        after = view.orientation.inverted().multVec(point - view.position())
        assert (after - local).Length < 0.005, "Off-center pivot drifts during rotation"
        shown = App.Vector(*driver._pivot_coords.point.getValues()[0].getValue())
        assert (shown - point).Length < 0.001
    # Geometry changes during a gesture must not make the orbit center jump.
    view.getObjectInfo = lambda pixel: dict(x=20, y=0, z=970)
    driver.apply_motion(navigation.hub.ViewportMotion(rx=100))
    assert (driver._orbit_pivot - point).Length < 0.001
    driver._last_motion -= 1
    driver.apply_motion(navigation.hub.ViewportMotion(rx=100))
    assert (driver._orbit_pivot - App.Vector(20, 0, 970)).Length < 0.001

view = View()
point = App.Vector(3, 4, 980)
view.getSize = lambda: (800, 600)
view.getObjectInfo = lambda pixel: dict(x=point.x, y=point.y, z=point.z)
driver = m.OrbitViewportDriver()
driver.active_view = lambda: view
for motion in (
    navigation.hub.ViewportMotion(tx=100),
    navigation.hub.ViewportMotion(tz=100, rx=80),
    navigation.hub.ViewportMotion(ty=100),
):
    before_position = view.position()
    driver.apply_motion(motion)
    assert (driver._orbit_pivot - point).Length < 0.001, "Pan detached pivot from the object"
    shown = App.Vector(*driver._pivot_coords.point.getValues()[0].getValue())
    assert (shown - point).Length < 0.001, "Marker detached from scene point"
driver._feedback_until = 0
driver.expire_feedback()
assert driver._feedback is None, "Marker remains visible after release"
driver._last_motion -= 1
view.getObjectInfo = lambda pixel: dict(x=6, y=7, z=980)
driver.apply_motion(navigation.hub.ViewportMotion(tx=100))
assert (driver._orbit_pivot - App.Vector(6, 7, 980)).Length < 0.001

view = View()
transform = coin.SoTranslation()
transform.translation = (50, 20, 10)
view.root.addChild(transform)
driver = m.OrbitViewportDriver()
driver._show_pivot(view, App.Vector(3, 4, 5))
path = coin.SoPath(view.root)
path.append(driver._feedback[1])
path.append(driver._pivot_coords)
action = coin.SoGetMatrixAction(coin.SbViewportRegion(800, 600))
action.apply(path)
shown = action.getMatrix().multVecMatrix(coin.SbVec3f(3, 4, 5))
assert (App.Vector(*shown.getValue()) - App.Vector(3, 4, 5)).Length < 0.001, (
    "Scene transform offsets marker"
)
print("FREECAD_CAMERA_AND_PIVOT_TESTS_OK")
