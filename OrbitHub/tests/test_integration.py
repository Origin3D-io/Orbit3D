from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "sdk" / "python" / "src"
BIN = pathlib.Path(os.environ.get("ORBIT_HUB_TEST_BIN_DIR", ROOT / "build"))
EXE = ".exe" if os.name == "nt" else ""
sys.path.insert(0, str(PYTHON_SDK))

from orbit3d_hub import (
    BUTTONS,
    DEVICES,
    MOTION,
    ButtonEvent,
    Client,
    DeviceEvent,
    MotionEvent,
    Provider,
)


class OrbitHubIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = subprocess.Popen(
            [str(BIN / ("orbithub" + EXE)), "--simulate", "--port", "0"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert cls.server.stdout is not None
        ready = cls.server.stdout.readline().strip().split()
        if len(ready) != 2 or ready[0] != "ORBIT_HUB_READY":
            stderr = cls.server.stderr.read() if cls.server.stderr else ""
            raise RuntimeError(f"OrbitHub did not start: {stderr}")
        cls.port = int(ready[1])

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.terminate()
        try:
            cls.server.wait(timeout=3)
        except subprocess.TimeoutExpired:
            cls.server.kill()
            cls.server.wait(timeout=3)

    def test_python_sdk_lists_device_and_streams_motion_and_buttons(self) -> None:
        with Client(port=self.port) as client, Provider(port=self.port) as provider:
            devices = client.list_devices()
            self.assertEqual(len(devices), 1)
            self.assertEqual(devices[0].vendor, "Orbit3D")
            self.assertEqual(devices[0].button_count, 4)

            device = provider.register_device("Test", "Event Delivery", "python-test", 1)
            client.subscribe(MOTION | BUTTONS)
            self.assertEqual(len(client.list_devices()), 2)
            # Test ordered transitions explicitly, not the simulator's wall-clock
            # button cycle, which depends on scheduling on shared CI runners.
            provider.publish_motion(device, 25000, 0, 0, 0, 0, 0)
            provider.publish_button(device, 1, True)
            provider.publish_button(device, 1, False)
            provider.ping()
            saw_motion = False
            button_states: set[bool] = set()
            deadline = time.monotonic() + 4.0
            while time.monotonic() < deadline and not (saw_motion and len(button_states) == 2):
                event = client.poll(timeout=0.5)
                if event.device_id != device.device_id:
                    continue
                if isinstance(event, MotionEvent):
                    saw_motion = True
                elif isinstance(event, ButtonEvent):
                    self.assertEqual(event.button_id, 1)
                    button_states.add(event.pressed)

            self.assertTrue(saw_motion)
            self.assertEqual(button_states, {False, True})

    def test_cpp_sdk(self) -> None:
        result = subprocess.run(
            [str(BIN / ("orbit3d_sdk_smoke" + EXE)), str(self.port)],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_provider_registers_and_publishes_motion_and_buttons(self) -> None:
        with Client(port=self.port) as client, Provider(port=self.port) as provider:
            client.subscribe(MOTION | BUTTONS | DEVICES)
            device = provider.register_device("Example Devices", "Example 6DOF", "EX-1", 3)
            devices = client.list_devices()
            published = next(item for item in devices if item.device_id == device.device_id)
            self.assertEqual(published.vendor, "Example Devices")
            self.assertEqual(published.button_count, 3)

            provider.publish_motion(device, 1, 2, 3, 4, 5, 6, timestamp_us=10)
            provider.publish_button(device, 2, True, timestamp_us=11)

            saw_motion = False
            saw_button = False
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline and not (saw_motion and saw_button):
                event = client.poll(timeout=0.2)
                if isinstance(event, MotionEvent) and event.device_id == device.device_id:
                    self.assertEqual((event.tx, event.ty, event.tz), (1, 2, 3))
                    saw_motion = True
                elif isinstance(event, ButtonEvent) and event.device_id == device.device_id:
                    self.assertEqual((event.button_id, event.pressed), (2, True))
                    saw_button = True
            self.assertTrue(saw_motion)
            self.assertTrue(saw_button)

            provider.publish_button(device, 2, True, timestamp_us=12)
            duplicate_deadline = time.monotonic() + 0.25
            while time.monotonic() < duplicate_deadline:
                event = client.poll(timeout=0.2)
                self.assertFalse(
                    isinstance(event, ButtonEvent)
                    and event.device_id == device.device_id
                    and event.button_id == 2
                )

            provider.close()
            saw_release = False
            saw_disconnect = False
            while time.monotonic() < deadline + 1.0 and not (saw_release and saw_disconnect):
                event = client.poll(timeout=0.2)
                if isinstance(event, ButtonEvent) and event.device_id == device.device_id:
                    saw_release = event.button_id == 2 and not event.pressed
                elif isinstance(event, DeviceEvent) and event.device_id == device.device_id:
                    saw_disconnect = not event.connected
            self.assertTrue(saw_release)
            self.assertTrue(saw_disconnect)

    def test_provider_can_register_multiple_devices(self) -> None:
        with Provider(port=self.port) as provider, Client(port=self.port) as client:
            first = provider.register_device("Example", "First")
            second = provider.register_device("Example", "Second", button_count=1)
            device_ids = {device.device_id for device in client.list_devices()}
            self.assertIn(first.device_id, device_ids)
            self.assertIn(second.device_id, device_ids)
            self.assertNotEqual(first.device_id, second.device_id)
            provider.unregister_device(first)
            device_ids = {device.device_id for device in client.list_devices()}
            self.assertNotIn(first.device_id, device_ids)
            self.assertIn(second.device_id, device_ids)

    def test_c_sdk(self) -> None:
        result = subprocess.run(
            [str(BIN / ("orbit3d_c_sdk_smoke" + EXE)), str(self.port)],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
