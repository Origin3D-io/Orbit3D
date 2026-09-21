from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sdk" / "python" / "src"))

from orbit3d_hub import (
    ButtonEvent,
    MotionEvent,
    apply_button_event,
    to_viewport_motion,
)


class ViewportFrameTests(unittest.TestCase):
    def test_viewport_conversion_preserves_every_axis_at_small_and_full_scale(self):
        for amount in (-1000000, -1, 0, 1, 1000000):
            for axis in range(6):
                values = [0] * 6
                values[axis] = amount
                event = MotionEvent(1, 0, *values)
                frame = to_viewport_motion(event)
                expected = [-values[0], values[2], values[1], -values[3], values[5], -values[4]]
                actual = (frame.tx, frame.ty, frame.tz, frame.rx, frame.ry, frame.rz)
                for value, reference in zip(actual, expected):
                    self.assertAlmostEqual(value, reference * 511 / 1000000)

    def test_button_events_update_bitmap(self) -> None:
        buttons = apply_button_event(0, ButtonEvent(1, 2, 1, True))
        buttons = apply_button_event(buttons, ButtonEvent(1, 3, 3, True))
        self.assertEqual(buttons, 0b0101)
        buttons = apply_button_event(buttons, ButtonEvent(1, 4, 1, False))
        self.assertEqual(buttons, 0b0100)


if __name__ == "__main__":
    unittest.main()
