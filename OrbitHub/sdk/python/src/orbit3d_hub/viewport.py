from __future__ import annotations

from dataclasses import dataclass

from .client import ButtonEvent, MotionEvent

NORMALIZED_MAX = 1_000_000
# Reference camera sensitivities were tuned against an axis range of +/-511.
REFERENCE_AXIS_SCALE = 511


@dataclass(frozen=True)
class ViewportMotion:
    """Float-preserving frame used by the example viewport integrations."""

    tx: float = 0.0
    ty: float = 0.0
    tz: float = 0.0
    rx: float = 0.0
    ry: float = 0.0
    rz: float = 0.0


def to_viewport_motion(event: MotionEvent) -> ViewportMotion:
    """Preserve the reference camera scale without quantizing small movements."""
    scale = REFERENCE_AXIS_SCALE / NORMALIZED_MAX
    return ViewportMotion(
        tx=-event.tx * scale,
        ty=event.tz * scale,
        tz=event.ty * scale,
        rx=-event.rx * scale,
        ry=event.rz * scale,
        rz=-event.ry * scale,
    )


def apply_button_event(buttons: int, event: ButtonEvent) -> int:
    if event.button_id < 1 or event.button_id > 32:
        raise ValueError("button_id must be between 1 and 32")
    bit = 1 << (event.button_id - 1)
    return buttons | bit if event.pressed else buttons & ~bit
