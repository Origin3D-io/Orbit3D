"""Choose a visible scene pivot without reframing the viewport."""

from mathutils import Vector


def choose_pivot(target):
    import bpy
    from bpy_extras.view3d_utils import (
        location_3d_to_region_2d,
        region_2d_to_origin_3d,
        region_2d_to_vector_3d,
    )

    region, view = target.region, target.region_3d
    center = (region.width * 0.5, region.height * 0.5)
    origin = region_2d_to_origin_3d(region, view, center)
    direction = region_2d_to_vector_3d(region, view, center)
    with bpy.context.temp_override(window=target.window, area=target.area, region=region):
        depsgraph = bpy.context.evaluated_depsgraph_get()
        hit, location, _, _, obj, _ = bpy.context.scene.ray_cast(depsgraph, origin, direction)
        if hit and obj.visible_get(
            view_layer=bpy.context.view_layer, viewport=target.area.spaces.active
        ):
            return location.copy()
        # Ignore cameras/lights and offscreen geometry when the center ray misses.
        nearest = None
        for obj in bpy.context.visible_objects:
            if obj.type != "MESH":
                continue
            bounds = obj.bound_box
            point = obj.matrix_world @ (sum((Vector(corner) for corner in bounds), Vector()) / 8)
            if (point - origin).dot(direction) <= 0:
                continue
            screen = location_3d_to_region_2d(region, view, point)
            if screen is None or not (
                0 <= screen.x <= region.width and 0 <= screen.y <= region.height
            ):
                continue
            distance = (screen.x - center[0]) ** 2 + (screen.y - center[1]) ** 2
            if nearest is None or distance < nearest[0]:
                nearest = (distance, point)
        return nearest[1].copy() if nearest else view.view_location.copy()


def rotate_about_pivot(view, delta, pivot):
    old_rotation = view.view_rotation.copy()
    new_rotation = old_rotation @ delta
    new_rotation.normalize()
    world_delta = new_rotation @ old_rotation.inverted()
    # Orbit both the camera orientation and its view center around the chosen
    # world point. Simply changing view_location would cause a visible jump.
    view.view_location = pivot + world_delta @ (view.view_location - pivot)
    view.view_rotation = new_rotation
