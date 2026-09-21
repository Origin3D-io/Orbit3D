from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_DIR = ROOT / "FreeCAD" / "Orbit3D"
SDK_SRC = ROOT / "OrbitHub" / "sdk" / "python" / "src"
sys.path.insert(0, str(MODULE_DIR))
sys.path.insert(0, str(SDK_SRC))
sys.modules["FreeCAD"] = None

from orbit3d_hub import (
    ButtonEvent,
    ButtonStateEvent,
    DeviceEvent,
    MotionEvent,
)


class FakeSignal:
    def connect(self, _callback):
        pass


class FakeTimer:
    def __init__(self):
        self.timeout = FakeSignal()
        self.active = False

    def setInterval(self, _milliseconds):
        pass

    def start(self):
        self.active = True

    def stop(self):
        self.active = False


qt_module = types.SimpleNamespace(QTimer=FakeTimer)
pyside_module = types.ModuleType("PySide6")
pyside_module.QtCore = qt_module
sys.modules.setdefault("PySide6", pyside_module)

import orbit3d_bootstrap

viewport_module = types.ModuleType("orbit3d_freecad.viewport_driver")
viewport_module.OrbitViewportDriver = type(
    "OrbitViewportDriver",
    (),
    {
        "apply_motion": lambda self, motion: None,
        "expire_feedback": lambda self: None,
        "clear_feedback": lambda self: None,
    },
)
sys.modules["orbit3d_freecad.viewport_driver"] = viewport_module

spec = importlib.util.spec_from_file_location(
    "orbit3d_freecad.controller",
    MODULE_DIR / "controller.py",
)
controller_module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(controller_module)


class FakeClient:
    events = []

    def __init__(self, **_kwargs):
        self.closed = False

    def list_devices(self):
        return [
            types.SimpleNamespace(
                device_id=9, connected=True, vendor="Test", product="Test", serial="1"
            )
        ]

    def subscribe(self, _subscriptions):
        pass

    def poll(self, timeout=None):
        del timeout
        return self.events.pop(0)

    def close(self):
        self.closed = True


class HubControllerTests(unittest.TestCase):
    def test_restart_waits_for_old_reader_without_clearing_its_stop_event(self):
        controller = controller_module.OrbitFreeCADController()
        old = Mock()
        old.is_alive.return_value = True
        controller._thread = old
        controller.stop()
        controller.start()
        self.assertTrue(controller.running)
        self.assertTrue(controller._restart_pending)
        self.assertTrue(controller._timer.active)
        self.assertTrue(controller._stop_event.is_set())
        replacement = Mock()
        with patch.object(
            controller_module.threading, "Thread", return_value=replacement
        ) as create:
            controller._tick()
            create.assert_not_called()
            old.is_alive.return_value = False
            controller._tick()
            create.assert_called_once()
        replacement.start.assert_called_once()
        self.assertFalse(controller._restart_pending)
        self.assertFalse(controller._stop_event.is_set())
        self.assertTrue(controller.running)

    def test_stop_cancels_pending_restart(self):
        controller = controller_module.OrbitFreeCADController()
        old = Mock()
        old.is_alive.return_value = True
        controller._thread = old
        controller.stop()
        controller.start()
        controller.stop()
        old.is_alive.return_value = False
        with patch.object(controller_module.threading, "Thread") as create:
            controller._tick()
            create.assert_not_called()
        self.assertFalse(controller.running)
        self.assertFalse(controller._restart_pending)
        self.assertFalse(controller._timer.active)

    def test_bootstrap_does_not_require_file_global_or_generic_modules(self):
        added = []
        fake_gui = types.SimpleNamespace(addWorkbench=added.append)
        timer = types.SimpleNamespace(singleShot=lambda *_args: None)
        namespace = {"Workbench": type("Workbench", (), {})}
        with patch.dict(
            sys.modules,
            {
                "FreeCADGui": fake_gui,
                "PySide": types.SimpleNamespace(QtCore=types.SimpleNamespace(QTimer=timer)),
                "protocol": types.ModuleType("unrelated_protocol"),
            },
        ):
            source = (MODULE_DIR / "InitGui.py").read_text(encoding="utf-8")
            exec(compile(source, "InitGui.py", "exec"), namespace)
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0].MenuText, "Orbit3D")
        self.assertEqual(controller_module.hub.ViewportMotion.__module__, "orbit3d_hub.viewport")
        # FreeCAD clears bootstrap globals before deferred timer callbacks run.
        namespace.pop("orbit3d_bootstrap", None)
        current = types.SimpleNamespace(
            running=False, start=lambda: setattr(current, "running", True)
        )
        with (
            patch.object(orbit3d_bootstrap, "controller", return_value=current),
            patch.dict(
                sys.modules,
                {
                    "FreeCAD": types.SimpleNamespace(
                        Console=types.SimpleNamespace(PrintMessage=lambda _: None)
                    )
                },
            ),
        ):
            namespace["_autostart_orbit_controller"]()
        self.assertTrue(current.running)

    def test_viewport_receives_both_click_edges_before_next_tick(self):
        controller = controller_module.OrbitFreeCADController()
        controller._running = True
        state = controller.input_state
        state.accept(ButtonStateEvent(9, 0))
        state.accept(ButtonEvent(9, 1, 1, True))
        state.accept(ButtonEvent(9, 2, 1, False))
        observed = []
        controller._viewport = types.SimpleNamespace(
            apply_button_event=lambda event, focused: observed.append(event),
            expire_feedback=lambda: None,
        )
        controller._tick()
        self.assertEqual(
            [event.pressed for event in observed if isinstance(event, ButtonEvent)], [True, False]
        )

    def setUp(self):
        FakeClient.events = [
            MotionEvent(9, 1, 0, 1_000_000, -1_000_000, 0, 0, 0),
            ButtonEvent(9, 2, 2, True),
            DeviceEvent(9, False),
        ]
        self.client_patch = patch.object(controller_module.hub, "Client", FakeClient)
        self.client_patch.start()
        self.addCleanup(self.client_patch.stop)

    def test_hub_events_reach_state_and_disconnect_clears_it(self):
        controller = controller_module.OrbitFreeCADController()
        observed = []
        accept = controller.input_state.accept

        def record(event):
            observed.append(event)
            accept(event)

        controller.input_state.accept = record
        controller._run_hub_session()
        self.assertEqual(len(observed), 3)
        self.assertIsNone(controller.input_state.sample())
        self.assertEqual(
            controller.input_state.take_buttons(), [controller_module.hub.InputReset()]
        )
        self.assertEqual(controller.status, "OrbitHub: Device Disconnected")

    def test_timer_preserves_fractional_motion(self):
        controller = controller_module.OrbitFreeCADController()
        controller._running = True
        controller.input_state.accept(MotionEvent(9, 0, 1, -2, 3, -4, 5, -6))
        observed = []
        controller._viewport = types.SimpleNamespace(
            expire_feedback=lambda: None,
            apply_motion=lambda motion, dt: observed.append(motion),
        )
        controller._tick()
        self.assertAlmostEqual(observed[0].tx, -0.000511)
        self.assertAlmostEqual(observed[0].ry, -0.003066)


if __name__ == "__main__":
    unittest.main()
