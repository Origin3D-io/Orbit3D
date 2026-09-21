"""
Orbit3D Blender addon entry point.

Install the `orbit3d_blender` folder as a zip inside Blender's addon manager.
"""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty

from .viewport_driver import OrbitViewportController, set_application_focus

bl_info = {
    "name": "Orbit3D",
    "author": "Orbit3D contributors",
    "version": (0, 2, 4),
    "blender": (4, 0, 0),
    "location": "3D View Header",
    "description": "Orbit3D viewport control through OrbitHub",
    "category": "3D View",
}

_CONTROLLER: OrbitViewportController | None = None


def get_addon_preferences():
    addon = bpy.context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


class ORBIT3D_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    auto_connect: BoolProperty(
        name="Auto Connect",
        description="Automatically connect to OrbitHub while Blender is open",
        default=True,
    )
    device_identity: StringProperty(
        name="Device Identity",
        description="Vendor/product/serial from the OrbitHub monitor; blank selects a single connected device",
    )
    block_native_ndof: BoolProperty(
        name="Prevent Duplicate Native Input",
        description="Block Blender's built-in 3D mouse events while OrbitHub input is enabled",
        default=True,
    )
    translation_sensitivity: FloatProperty(
        name="Translation Sensitivity",
        description="Scales viewport pan and zoom speed",
        default=0.0002,
        min=0.000001,
        max=0.01,
        precision=6,
    )
    rotation_sensitivity: FloatProperty(
        name="Rotation Sensitivity",
        description="Scales viewport rotation speed",
        default=0.0002,
        min=0.000001,
        max=0.02,
        precision=6,
    )
    deadzone: IntProperty(
        name="Deadzone",
        description="Ignores small input near the center",
        default=0,
        min=0,
        max=128,
    )
    invert_tx: BoolProperty(name="Invert TX", default=False)
    invert_ty: BoolProperty(name="Invert TY", default=False)
    invert_tz: BoolProperty(name="Invert TZ", default=False)
    invert_rx: BoolProperty(name="Invert RX", default=False)
    invert_ry: BoolProperty(name="Invert RY", default=True)
    invert_rz: BoolProperty(name="Invert RZ", default=False)
    pitch_source: EnumProperty(
        name="Pitch Source",
        description="Reference-frame axis used for Blender forward/back viewport rotation",
        items=(
            ("rx", "RX", "Use reference RX"),
            ("ry", "RY", "Use reference RY"),
            ("rz", "RZ", "Use reference RZ"),
        ),
        default="rx",
        options={"HIDDEN"},
    )
    yaw_source: EnumProperty(
        name="Yaw Source",
        description="Reference-frame axis used for Blender left/right viewport rotation",
        items=(
            ("rx", "RX", "Use reference RX"),
            ("ry", "RY", "Use reference RY"),
            ("rz", "RZ", "Use reference RZ"),
        ),
        default="rz",
        options={"HIDDEN"},
    )
    roll_source: EnumProperty(
        name="Roll Source",
        description="Reference-frame axis used for Blender twist viewport rotation",
        items=(
            ("rx", "RX", "Use reference RX"),
            ("ry", "RY", "Use reference RY"),
            ("rz", "RZ", "Use reference RZ"),
        ),
        default="ry",
        options={"HIDDEN"},
    )
    invert_pitch: BoolProperty(name="Invert Pitch", default=False)
    invert_yaw: BoolProperty(name="Invert Yaw", default=False)
    invert_roll: BoolProperty(name="Invert Roll", default=False)

    def draw(self, _context):
        layout = self.layout
        layout.label(text="Orbit3D Device")
        layout.prop(self, "auto_connect")
        layout.prop(self, "device_identity")

        layout.separator()
        layout.label(text="Motion")
        layout.prop(self, "translation_sensitivity")
        layout.prop(self, "block_native_ndof")
        layout.prop(self, "rotation_sensitivity")
        layout.prop(self, "deadzone")

        layout.separator()
        layout.label(text="Axis Inversion")
        row = layout.row(align=True)
        row.prop(self, "invert_tx")
        row.prop(self, "invert_ty")
        row.prop(self, "invert_tz")
        row = layout.row(align=True)
        row.prop(self, "invert_rx")
        row.prop(self, "invert_ry")
        row.prop(self, "invert_rz")

        layout.separator()
        layout.label(text="Rotation Direction")
        row = layout.row(align=True)
        row.prop(self, "invert_pitch")
        row = layout.row(align=True)
        row.prop(self, "invert_yaw")
        row = layout.row(align=True)
        row.prop(self, "invert_roll")
        layout.operator("orbit3d.reset_rotation_mapping", icon="LOOP_BACK")

        layout.separator()
        layout.label(text="Device Status")
        layout.label(text=_controller_status_text())
        layout.operator("orbit3d.force_reconnect", icon="FILE_REFRESH")


class ORBIT3D_OT_ForceReconnect(bpy.types.Operator):
    bl_idname = "orbit3d.force_reconnect"
    bl_label = "Reconnect Controller"
    bl_description = "Reconnect to OrbitHub and discover connected controllers"

    def execute(self, _context):
        if _CONTROLLER is not None:
            _CONTROLLER.force_reconnect()
        return {"FINISHED"}


class ORBIT3D_OT_ResetRotationMapping(bpy.types.Operator):
    bl_idname = "orbit3d.reset_rotation_mapping"
    bl_label = "Reset Navigation Settings"
    bl_description = "Restore the default viewport sensitivity and rotation settings"

    def execute(self, _context):
        prefs = get_addon_preferences()
        if prefs is not None:
            prefs.translation_sensitivity = 0.0002
            prefs.rotation_sensitivity = 0.0002
            prefs.deadzone = 0
            prefs.invert_tx = False
            prefs.invert_ty = False
            prefs.invert_tz = False
            prefs.invert_rx = False
            prefs.invert_ry = True
            prefs.invert_rz = False
            prefs.pitch_source = "rx"
            prefs.yaw_source = "rz"
            prefs.roll_source = "ry"
            prefs.invert_pitch = False
            prefs.invert_yaw = False
            prefs.invert_roll = False
        return {"FINISHED"}


def draw_view3d_header(self, context):
    if context.area is None or context.area.type != "VIEW_3D":
        return

    icon = "ORIENTATION_GIMBAL" if _CONTROLLER and _CONTROLLER.connected else "PAUSE"
    self.layout.separator()
    # Keep a fixed-size header; detailed connection attempts belong in the tooltip.
    row = self.layout.row()
    row.ui_units_x = 8
    row.operator("orbit3d.connection_status", text="Orbit3D", icon=icon, emboss=False)


def _controller_status_text() -> str:
    if _CONTROLLER is None:
        return "Stopped"
    return _CONTROLLER.status_text


_FOCUS_WINDOWS = set()
_FOCUS_GENERATION = 0


class ORBIT3D_OT_ConnectionStatus(bpy.types.Operator):
    bl_idname = "orbit3d.connection_status"
    bl_label = "Orbit3D Connection"

    @classmethod
    def description(cls, context, properties):
        return _controller_status_text()

    def execute(self, context):
        self.report({"INFO"}, _controller_status_text())
        return {"FINISHED"}


class ORBIT3D_OT_FocusMonitor(bpy.types.Operator):
    bl_idname = "orbit3d.focus_monitor"
    bl_label = "Orbit3D Focus Monitor"

    def invoke(self, context, _event):
        self.generation = _FOCUS_GENERATION
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, _context, event):
        if self.generation != _FOCUS_GENERATION or _CONTROLLER is None:
            return {"CANCELLED"}
        prefs = get_addon_preferences()
        if (
            event.type.startswith("NDOF_")
            and prefs
            and prefs.auto_connect
            and prefs.block_native_ndof
        ):
            return {"RUNNING_MODAL"}
        if event.type == "WINDOW_DEACTIVATE":
            set_application_focus(False)
        elif event.type in {"MOUSEMOVE", "LEFTMOUSE", "RIGHTMOUSE", "INBETWEEN_MOUSEMOVE"}:
            set_application_focus(True)
        return {"PASS_THROUGH"}


def _ensure_focus_monitors():
    if _CONTROLLER is None:
        return None
    _FOCUS_WINDOWS.intersection_update(
        window.as_pointer() for window in bpy.context.window_manager.windows
    )
    for window in bpy.context.window_manager.windows:
        key = window.as_pointer()
        if key not in _FOCUS_WINDOWS:
            with bpy.context.temp_override(window=window):
                bpy.ops.orbit3d.focus_monitor("INVOKE_DEFAULT")
            _FOCUS_WINDOWS.add(key)
    return 0.5


CLASSES = (
    ORBIT3D_OT_ConnectionStatus,
    ORBIT3D_OT_FocusMonitor,
    ORBIT3D_AddonPreferences,
    ORBIT3D_OT_ForceReconnect,
    ORBIT3D_OT_ResetRotationMapping,
)


def register():
    global _CONTROLLER

    for cls in CLASSES:
        bpy.utils.register_class(cls)

    _CONTROLLER = OrbitViewportController(get_addon_preferences)
    bpy.types.VIEW3D_HT_header.append(draw_view3d_header)
    _CONTROLLER.start()
    bpy.app.timers.register(_ensure_focus_monitors, first_interval=0.1)


def unregister():
    global _CONTROLLER, _FOCUS_GENERATION
    _FOCUS_GENERATION += 1
    _FOCUS_WINDOWS.clear()
    if bpy.app.timers.is_registered(_ensure_focus_monitors):
        bpy.app.timers.unregister(_ensure_focus_monitors)

    if _CONTROLLER is not None:
        _CONTROLLER.stop()
        _CONTROLLER = None

    try:
        bpy.types.VIEW3D_HT_header.remove(draw_view3d_header)
    except ValueError:
        pass

    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
