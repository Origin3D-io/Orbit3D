"""Reference camera frame for the FreeCAD integration."""

from __future__ import annotations

from dataclasses import dataclass

from .sdk import hub


@dataclass
class NavigationFrame:
    pan_x: float = 0.0
    zoom: float = 0.0
    pan_y: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    roll: float = 0.0


def to_navigation_frame(frame: hub.ViewportMotion) -> NavigationFrame:
    return NavigationFrame(
        pan_x=-frame.tx,
        zoom=frame.ty,
        pan_y=frame.tz,
        pitch=frame.rx,
        yaw=frame.rz,
        roll=frame.ry,
    )
