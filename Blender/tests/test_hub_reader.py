from __future__ import annotations

import importlib
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[2]
SDK_SRC = ROOT / "OrbitHub" / "sdk" / "python" / "src"
ADDON_DIR = ROOT / "Blender" / "orbit3d_blender"
sys.path.insert(0, str(SDK_SRC))

from orbit3d_hub import (
    ButtonEvent,
    ButtonStateEvent,
    DeviceEvent,
    InputState,
    MotionEvent,
)

PACKAGE = "_orbit3d_blender_test"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ADDON_DIR)]
sys.modules.setdefault(PACKAGE, package)
reader_thread = importlib.import_module(f"{PACKAGE}.reader_thread")


class FakeClient:
    events = [
        MotionEvent(7, 1, -1_000_000, 0, 1_000_000, 0, 0, 0),
        ButtonEvent(7, 2, 3, True),
        DeviceEvent(7, False),
    ]

    def __init__(self, **_kwargs):
        self.closed = False
        self.subscriptions = 0

    def list_devices(self):
        return [
            types.SimpleNamespace(
                device_id=7, connected=True, vendor="Test", product="Test", serial="1"
            )
        ]

    def subscribe(self, subscriptions):
        self.subscriptions = subscriptions

    def poll(self, timeout=None):
        del timeout
        return self.events.pop(0)

    def close(self):
        self.closed = True


class HubReaderTests(unittest.TestCase):
    def test_viewport_preserves_click_between_timer_ticks(self):
        import time

        bpy = types.ModuleType("bpy")
        mathutils = types.ModuleType("mathutils")
        mathutils.Quaternion = object
        mathutils.Vector = object
        sys.modules["bpy"] = bpy
        sys.modules["mathutils"] = mathutils
        viewport = importlib.import_module(f"{PACKAGE}.viewport_driver")
        state = InputState()
        state.accept(ButtonStateEvent(7, 0))
        state.accept(ButtonEvent(7, 1, 1, True))
        state.accept(ButtonEvent(7, 2, 1, False))
        obj = viewport.OrbitViewportController.__new__(viewport.OrbitViewportController)
        obj._running = True
        obj._last_buttons = 0
        obj._last_tick = time.monotonic()
        obj._reader = types.SimpleNamespace(
            input_state=state,
            device_identity="",
            running=True,
        )
        obj._preferences_getter = lambda: types.SimpleNamespace(
            auto_connect=True, device_identity=""
        )
        obj._find_target_view = lambda: object()
        observed = []

        def handle(_target, buttons):
            observed.append(buttons)
            obj._last_buttons = buttons

        obj._handle_buttons = handle
        obj._apply_motion = lambda *args: None
        obj._tag_redraw_all_viewports = lambda: None
        with patch.object(viewport, "application_has_focus", return_value=True):
            obj._timer_callback()
        self.assertEqual(observed, [1, 0])
        observed.clear()
        state.accept(ButtonEvent(7, 3, 1, True))
        state.accept(ButtonEvent(7, 4, 1, False))
        with patch.object(viewport, "application_has_focus", return_value=False):
            obj._timer_callback()
        with patch.object(viewport, "application_has_focus", return_value=True):
            obj._timer_callback()
        self.assertEqual(observed, [])

    def setUp(self):
        FakeClient.events = [
            MotionEvent(7, 1, -1_000_000, 0, 1_000_000, 0, 0, 0),
            ButtonEvent(7, 2, 3, True),
            DeviceEvent(7, False),
        ]
        self.client_patch = patch.object(reader_thread.hub, "Client", FakeClient)
        self.client_patch.start()
        self.addCleanup(self.client_patch.stop)

    def test_hub_events_reach_state_and_disconnect_clears_it(self):
        reader = reader_thread.OrbitReaderThread()
        observed = []
        accept = reader.input_state.accept

        def record(event):
            observed.append(event)
            accept(event)

        reader.input_state.accept = record
        reader._run_hub_session()
        self.assertEqual(len(observed), 3)
        self.assertIsInstance(observed[0], MotionEvent)
        self.assertIsInstance(observed[1], ButtonEvent)
        self.assertIsNone(reader.input_state.sample())
        self.assertEqual(reader.input_state.take_buttons(), [reader_thread.hub.InputReset()])
        self.assertFalse(reader.connected)
        self.assertEqual(reader.status, "OrbitHub: Device Disconnected")

    def test_timer_preserves_fractional_motion(self):
        self.test_viewport_preserves_click_between_timer_ticks()
        viewport = importlib.import_module(f"{PACKAGE}.viewport_driver")
        obj = viewport.OrbitViewportController(
            lambda: types.SimpleNamespace(auto_connect=True, device_identity="")
        )
        obj._running = True
        obj._reader = types.SimpleNamespace(
            input_state=InputState(), running=True, device_identity=""
        )
        obj._reader.input_state.accept(MotionEvent(7, 0, 1, -2, 3, -4, 5, -6))
        obj._find_target_view = lambda: object()
        observed = []
        obj._apply_motion = lambda target, motion, prefs, dt: observed.append(motion)
        with patch.object(viewport, "application_has_focus", return_value=True):
            obj._timer_callback()
        self.assertAlmostEqual(observed[0].tx, -0.000511)
        self.assertAlmostEqual(observed[0].ry, -0.003066)


if __name__ == "__main__":
    unittest.main()
