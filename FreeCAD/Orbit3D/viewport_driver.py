"""Viewport math for applying Orbit3D input inside FreeCAD."""

from __future__ import annotations

import math
import time

try:
    import FreeCADGui as Gui

    import FreeCAD as App
except ImportError:
    App = None
    Gui = None

try:
    from pivy import coin
except ImportError:
    coin = None

from .navigation import to_navigation_frame
from .sdk import hub


class OrbitViewportDriver:
    """Applies accumulated 6DOF motion to the active FreeCAD 3D view."""

    def __init__(self):
        self.pan_speed = 0.00012
        self.orbit_speed = 0.0062
        self.zoom_speed = 0.0002
        self.deadzone = 0
        self._last_buttons = 0
        self._prepared_view = None
        self._feedback = None
        self._feedback_until = 0.0
        self._orbit_pivot = None
        self._orbit_view = None
        self._last_motion = 0.0

    @staticmethod
    def view_height(camera):
        if hasattr(camera, "height"):
            return max(1e-6, float(camera.height.getValue()))
        distance = max(1e-6, float(camera.focalDistance.getValue()))
        angle = float(camera.heightAngle.getValue())
        return max(1e-6, 2 * distance * math.tan(angle / 2))

    def clear_feedback(self):
        if self._feedback is not None:
            root, node = self._feedback
            try:
                root.removeChild(node)
            except RuntimeError:
                pass
            self._feedback = None

    def expire_feedback(self):
        if self._feedback is not None and time.monotonic() > self._feedback_until:
            self.clear_feedback()

    def _show_pivot(self, view, pivot):
        # A world-space, unpickable point at the actual orbit center, not a HUD dot.
        try:
            root = view.getSceneGraph()
            if self._feedback is None or self._feedback[0] != root:
                self.clear_feedback()
                node = coin.SoAnnotation()
                pick = coin.SoPickStyle()
                pick.style = coin.SoPickStyle.UNPICKABLE
                light = coin.SoLightModel()
                light.model = coin.SoLightModel.BASE_COLOR
                color = coin.SoBaseColor()
                color.rgb = (0.8, 0.86, 0.9)
                style = coin.SoDrawStyle()
                style.pointSize = 5
                coords = coin.SoCoordinate3()
                points = coin.SoPointSet()
                points.numPoints = 1
                for child in (coin.SoResetTransform(), pick, light, color, style, coords, points):
                    node.addChild(child)
                root.addChild(node)
                self._feedback = (root, node)
                self._pivot_coords = coords
            self._pivot_coords.point.setValue(pivot.x, pivot.y, pivot.z)
            self._feedback_until = time.monotonic() + 0.2
        except (AttributeError, RuntimeError):
            self.clear_feedback()

    def active_view(self):
        if Gui is None or Gui.ActiveDocument is None:
            return None
        return getattr(Gui.ActiveDocument, "ActiveView", None)

    @staticmethod
    def _choose_pivot(view, camera, orientation):
        position = App.Vector(*camera.position.getValue().getValue())
        forward = orientation.multVec(App.Vector(0, 0, -1))
        fallback = position + forward * float(camera.focalDistance.getValue())
        try:
            width, height = view.getSize()
            # Pick once per gesture, center first, then nearby visible geometry.
            for x, y in (
                (0, 0),
                (-1, 0),
                (1, 0),
                (0, -1),
                (0, 1),
                (-1, -1),
                (1, -1),
                (-1, 1),
                (1, 1),
            ):
                hit = view.getObjectInfo(
                    (int(width * (0.5 + x * 0.15)), int(height * (0.5 + y * 0.15)))
                )
                if hit:
                    point = App.Vector(float(hit["x"]), float(hit["y"]), float(hit["z"]))
                    if all(math.isfinite(v) for v in (point.x, point.y, point.z)) and (
                        hasattr(camera, "height") or (point - position).dot(forward) > 1e-6
                    ):
                        return point
        except (AttributeError, RuntimeError, TypeError, KeyError, ValueError):
            pass
        return fallback

    def apply_motion(self, motion: hub.ViewportMotion, time_scale: float = 1.0) -> bool:
        view = self.active_view()
        if view is None or App is None or coin is None:
            return False

        self._prepare_view(view)

        nav = to_navigation_frame(motion)
        pan_x = self._dz(nav.pan_x)
        zoom = self._dz(nav.zoom)
        pan_y = self._dz(nav.pan_y)
        pitch = self._dz(nav.pitch)
        yaw = self._dz(nav.yaw)
        roll = self._dz(nav.roll)

        changed = False
        camera = view.getCameraNode()
        if camera is None:
            return False

        cam_orient = view.getCameraOrientation()
        cam_right = cam_orient.multVec(App.Vector(1, 0, 0))
        cam_up = cam_orient.multVec(App.Vector(0, 1, 0))
        cam_fwd = cam_orient.multVec(App.Vector(0, 0, -1))
        focal_distance = max(float(camera.focalDistance.getValue()), 1e-6)
        visible_height = self.view_height(camera)
        moving = any((pan_x, pan_y, zoom, pitch, yaw, roll))
        now = time.monotonic()
        if moving and (
            self._orbit_pivot is None or self._orbit_view != view or now - self._last_motion > 0.25
        ):
            self._orbit_pivot = self._choose_pivot(view, camera, cam_orient)
            self._orbit_view = view

        if pan_x or pan_y:
            pan_offset = cam_right * (
                pan_x * self.pan_speed * time_scale * visible_height
            ) + cam_up * (pan_y * self.pan_speed * time_scale * visible_height)
            current = camera.position.getValue().getValue()
            camera.position.setValue(
                current[0] + pan_offset.x,
                current[1] + pan_offset.y,
                current[2] + pan_offset.z,
            )
            changed = True

        if zoom:
            zoom_factor = math.exp(max(-0.3, min(0.3, -zoom * self.zoom_speed * time_scale)))
            if hasattr(camera, "height"):
                camera.height.setValue(max(1e-6, min(1e12, visible_height * zoom_factor)))
                changed = True
            else:
                self._perspective_zoom(camera, cam_fwd, focal_distance, zoom_factor)
                changed = True

        if pitch or yaw or roll:
            qx = App.Rotation(App.Vector(1, 0, 0), -pitch * self.orbit_speed * time_scale)
            qy = App.Rotation(App.Vector(0, 1, 0), yaw * self.orbit_speed * time_scale)
            qz = App.Rotation(App.Vector(0, 0, 1), -roll * self.orbit_speed * time_scale)
            delta = qz.multiply(qy.multiply(qx))
            new_orient = cam_orient.multiply(delta)
            current = camera.position.getValue().getValue()
            pivot = self._orbit_pivot
            world_delta = new_orient.multiply(cam_orient.inverted())
            position = pivot + world_delta.multVec(App.Vector(*current) - pivot)
            view.setCameraOrientation(new_orient)
            camera.position.setValue(position.x, position.y, position.z)
            changed = True

        if changed:
            self._show_pivot(view, self._orbit_pivot)
            self._last_motion = now
            view.redraw()

        return changed

    @staticmethod
    def _perspective_zoom(camera, cam_fwd, focal_distance, zoom_factor):
        new_focal_distance = max(1e-6, min(1e12, focal_distance * zoom_factor))
        distance_delta = focal_distance - new_focal_distance
        current = camera.position.getValue().getValue()
        zoom_offset = cam_fwd * distance_delta
        camera.position.setValue(
            current[0] + zoom_offset.x,
            current[1] + zoom_offset.y,
            current[2] + zoom_offset.z,
        )
        camera.focalDistance.setValue(new_focal_distance)

    def apply_button_event(self, event, focused=True):
        if isinstance(event, hub.InputReset):
            self._last_buttons = 0
            self._orbit_pivot = None
            self.clear_feedback()
            return
        if isinstance(event, hub.ButtonStateEvent):
            self._last_buttons = event.buttons
            return
        bit = 1 << (event.button_id - 1)
        buttons = self._last_buttons | bit if event.pressed else self._last_buttons & ~bit
        view = self.active_view()
        if focused and view is not None:
            self._handle_buttons(view, buttons)
        else:
            self._last_buttons = buttons

    def _handle_buttons(self, view, buttons: int) -> None:
        b1_now = buttons & 0x01
        b1_was = self._last_buttons & 0x01
        self._last_buttons = buttons
        if b1_now and not b1_was:
            self._orbit_pivot = None
            self.clear_feedback()
            view.fitAll()

    def _dz(self, value: float) -> float:
        return 0 if abs(value) < self.deadzone else value

    def _prepare_view(self, view) -> None:
        if self._prepared_view == view:
            return
        try:
            view.setAnimationEnabled(False)
        except Exception:
            pass
        self._prepared_view = view
