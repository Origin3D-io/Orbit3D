"""Small OrbitHub pivot indicator, independent of Blender's native NDOF input."""

import math
import time

import bpy


class PivotMarker:
    def __init__(self):
        self.handle = None
        self.area = None
        self.until = 0.0

    def start(self):
        if self.handle is None and not bpy.app.background:
            self.handle = bpy.types.SpaceView3D.draw_handler_add(
                self.draw, (), "WINDOW", "POST_PIXEL"
            )

    def stop(self):
        if self.handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self.handle, "WINDOW")
            self.handle = None
        self.area = None

    def show(self, target, point):
        self.area = target.area.as_pointer()
        self.point = point.copy()
        self.until = time.monotonic() + 0.22

    def draw(self):
        context = bpy.context
        remaining = self.until - time.monotonic()
        if remaining <= 0 or context.area is None or context.area.as_pointer() != self.area:
            return
        import gpu
        from bpy_extras.view3d_utils import location_3d_to_region_2d
        from gpu_extras.batch import batch_for_shader

        view = context.region_data
        if view is None:
            return
        point = location_3d_to_region_2d(context.region, view, self.point)
        if point is None:
            return
        radius = 3.0 * context.preferences.system.ui_scale
        ring = [
            (
                point.x + radius * math.cos(i * math.tau / 20),
                point.y + radius * math.sin(i * math.tau / 20),
            )
            for i in range(20)
        ]
        vertices = []
        for i in range(20):
            vertices.extend([(point.x, point.y), ring[i], ring[(i + 1) % 20]])
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "TRIS", {"pos": vertices})
        previous_blend = gpu.state.blend_get()
        try:
            gpu.state.blend_set("ALPHA")
            shader.bind()
            shader.uniform_float("color", (0.78, 0.86, 0.82, min(0.85, remaining / 0.1)))
            batch.draw(shader)
        finally:
            gpu.state.blend_set(previous_blend)
