"""
Main-thread viewport driver for the Orbit3D Blender addon.

This module samples canonical input on Blender's timer and updates the viewport.
"""

from __future__ import annotations

import math
import os
import sys
import time
from dataclasses import dataclass
from typing import Callable, Optional

import bpy
from mathutils import Quaternion, Vector

from .reader_thread import OrbitReaderThread
from .sdk import hub

_APPLICATION_FOCUSED = True
_USER32 = None
if sys.platform == "win32":
    import ctypes

    _USER32 = ctypes.WinDLL("user32", use_last_error=True)
    _USER32.GetForegroundWindow.restype = ctypes.c_void_p
    _USER32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]


def application_has_focus():
    if _USER32 is not None:
        process_id = ctypes.c_ulong()
        _USER32.GetWindowThreadProcessId(_USER32.GetForegroundWindow(), ctypes.byref(process_id))
        return process_id.value == os.getpid()
    return _APPLICATION_FOCUSED


def set_application_focus(focused: bool):
    global _APPLICATION_FOCUSED
    _APPLICATION_FOCUSED = focused


@dataclass
class View3DTarget:
    window: bpy.types.Window
    area: bpy.types.Area
    region: bpy.types.Region
    region_3d: bpy.types.RegionView3D


class OrbitViewportController:
    """Coordinates the reader thread and applies motion in Blender."""

    TIMER_INTERVAL_S = 0.016

    def __init__(self, preferences_getter: Callable[[], Optional[bpy.types.AddonPreferences]]):
        self._preferences_getter = preferences_getter
        self._reader = OrbitReaderThread()
        self._running = False
        self._last_buttons = 0
        self._last_tick = time.monotonic()
        self._pivot_marker = None
        self._orbit_pivot = None
        self._pivot_area = None
        self._last_rotation_at = 0.0

    @property
    def connected(self) -> bool:
        return self._reader.connected

    @property
    def status_text(self) -> str:
        prefs = self._preferences_getter()
        if prefs is not None and not prefs.auto_connect:
            return "Disabled"
        return self._reader.status

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        if not bpy.app.background:
            from .pivot_marker import PivotMarker

            self._pivot_marker = PivotMarker()
            self._pivot_marker.start()
        bpy.app.timers.register(
            self._timer_callback, first_interval=self.TIMER_INTERVAL_S, persistent=True
        )

    def stop(self) -> None:
        self._running = False
        if self._pivot_marker is not None:
            self._pivot_marker.stop()
            self._pivot_marker = None
        if bpy.app.timers.is_registered(self._timer_callback):
            bpy.app.timers.unregister(self._timer_callback)
        self._reader.stop()
        self._reader.input_state.reset()
        self._tag_redraw_all_viewports()

    def force_reconnect(self) -> None:
        self._reader.force_reconnect()

    def _timer_callback(self) -> Optional[float]:
        if not self._running:
            return None

        prefs = self._preferences_getter()
        if prefs is None:
            return 0.25

        if prefs.auto_connect:
            if not self._reader.running:
                self._reader.start()
        else:
            if self._reader.running:
                self._reader.stop()
            self._reader.input_state.reset()
            return 0.25

        now = time.monotonic()
        time_scale = min(0.05, max(0, now - self._last_tick)) / self.TIMER_INTERVAL_S
        self._last_tick = now
        identity = getattr(prefs, "device_identity", "") or os.environ.get("ORBIT3D_DEVICE", "")
        if identity != self._reader.device_identity:
            self._reader.device_identity = identity
            self._reader.force_reconnect()
        button_events = self._reader.input_state.take_buttons()
        sample = self._reader.input_state.sample()
        latest_motion = (
            hub.to_viewport_motion(sample) if sample is not None else hub.ViewportMotion()
        )
        # Blender exposes application focus through its window event stream.
        if not application_has_focus():
            for event in button_events:
                if isinstance(event, hub.InputReset):
                    self._last_buttons = 0
                elif isinstance(event, hub.ButtonStateEvent):
                    self._last_buttons = event.buttons
                else:
                    self._last_buttons = hub.apply_button_event(self._last_buttons, event)
            return self.TIMER_INTERVAL_S
        target = self._find_target_view()
        if target is None:
            return self.TIMER_INTERVAL_S

        for event in button_events:
            if isinstance(event, hub.InputReset):
                self._last_buttons = 0
            elif isinstance(event, hub.ButtonStateEvent):
                self._last_buttons = event.buttons
            else:
                self._handle_buttons(target, hub.apply_button_event(self._last_buttons, event))
        self._apply_motion(target, latest_motion, prefs, time_scale)
        return self.TIMER_INTERVAL_S

    def _find_target_view(self) -> Optional[View3DTarget]:
        context = bpy.context
        preferred_window = context.window

        windows = list(context.window_manager.windows)
        if preferred_window in windows:
            windows.remove(preferred_window)
            windows.insert(0, preferred_window)

        for window in windows:
            screen = window.screen
            if screen is None:
                continue
            for area in screen.areas:
                if area.type != "VIEW_3D":
                    continue
                region = next((item for item in area.regions if item.type == "WINDOW"), None)
                if region is None:
                    continue
                space = area.spaces.active
                region_3d = getattr(space, "region_3d", None)
                if region_3d is None:
                    continue
                return View3DTarget(window=window, area=area, region=region, region_3d=region_3d)
        return None

    def _handle_buttons(self, target: View3DTarget, buttons: int) -> None:
        pressed_now = buttons & 0x01
        pressed_before = self._last_buttons & 0x01
        self._last_buttons = buttons

        if pressed_now and not pressed_before:
            with bpy.context.temp_override(
                window=target.window,
                area=target.area,
                region=target.region,
            ):
                bpy.ops.view3d.view_all(center=False)

    def _apply_motion(
        self,
        target: View3DTarget,
        motion: hub.ViewportMotion,
        prefs: bpy.types.AddonPreferences,
        time_scale: float = 1.0,
    ) -> None:
        adjusted = hub.ViewportMotion(
            tx=self._apply_invert(motion.tx, prefs.invert_tx),
            ty=self._apply_invert(motion.ty, prefs.invert_ty),
            tz=self._apply_invert(motion.tz, prefs.invert_tz),
            rx=self._apply_invert(motion.rx, prefs.invert_rx),
            ry=self._apply_invert(motion.ry, prefs.invert_ry),
            rz=self._apply_invert(motion.rz, prefs.invert_rz),
        )
        pan_x = self._apply_deadzone(-adjusted.tx, prefs.deadzone)
        zoom = self._apply_deadzone(adjusted.ty, prefs.deadzone)
        pan_y = self._apply_deadzone(adjusted.tz, prefs.deadzone)
        pitch = self._apply_deadzone(
            self._mapped_axis(adjusted, prefs.pitch_source, prefs.invert_pitch),
            prefs.deadzone,
        )
        yaw = self._apply_deadzone(
            self._mapped_axis(adjusted, prefs.yaw_source, prefs.invert_yaw),
            prefs.deadzone,
        )
        roll = self._apply_deadzone(
            self._mapped_axis(adjusted, prefs.roll_source, prefs.invert_roll),
            prefs.deadzone,
        )

        rv3d = target.region_3d
        if not any((pan_x, pan_y, zoom, pitch, yaw, roll)):
            if self._pivot_marker is not None and self._pivot_marker.until:
                target.area.tag_redraw()
                if time.monotonic() >= self._pivot_marker.until:
                    self._pivot_marker.until = 0.0
            return
        view_distance = max(rv3d.view_distance, 0.25)

        if pan_x or pan_y:
            pan_distance = (prefs.translation_sensitivity * time_scale) * view_distance
            local_offset = Vector((pan_x * pan_distance, pan_y * pan_distance, 0.0))
            world_offset = rv3d.view_rotation @ local_offset
            rv3d.view_location += world_offset

        if zoom:
            zoom_factor = math.exp(-zoom * (prefs.translation_sensitivity * time_scale) * 0.35)
            rv3d.view_distance = max(0.05, rv3d.view_distance * zoom_factor)

        if pitch or yaw or roll:
            from .dynamic_pivot import choose_pivot, rotate_about_pivot

            now = time.monotonic()
            area_id = target.area.as_pointer()
            if (
                self._orbit_pivot is None
                or self._pivot_area != area_id
                or now - self._last_rotation_at > 0.22
            ):
                self._orbit_pivot = choose_pivot(target)
                self._pivot_area = area_id
            self._last_rotation_at = now
            qx = Quaternion(
                Vector((1.0, 0.0, 0.0)), -pitch * (prefs.rotation_sensitivity * time_scale)
            )
            qy = Quaternion(
                Vector((0.0, 1.0, 0.0)), yaw * (prefs.rotation_sensitivity * time_scale)
            )
            qz = Quaternion(
                Vector((0.0, 0.0, 1.0)), roll * (prefs.rotation_sensitivity * time_scale)
            )
            delta = qz @ qy @ qx
            rotate_about_pivot(rv3d, delta, self._orbit_pivot)
            if self._pivot_marker is not None:
                self._pivot_marker.show(target, self._orbit_pivot)

        rv3d.update()
        target.area.tag_redraw()

    @staticmethod
    def _apply_deadzone(value: float, threshold: int) -> float:
        return 0 if abs(value) < threshold else value

    @staticmethod
    def _apply_invert(value: float, invert: bool) -> float:
        return -value if invert else value

    @staticmethod
    def _mapped_axis(motion: hub.ViewportMotion, source: str, invert: bool) -> float:
        value = getattr(motion, source, 0)
        return -value if invert else value

    @staticmethod
    def _tag_redraw_all_viewports() -> None:
        for window in bpy.context.window_manager.windows:
            screen = window.screen
            if screen is None:
                continue
            for area in screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
