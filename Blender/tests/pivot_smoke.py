"""Run inside Blender --background --factory-startup --python-exit-code 1."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "OrbitHub" / "sdk" / "python" / "src"))
import bpy
from mathutils import Quaternion, Vector
from orbit3d_blender.dynamic_pivot import choose_pivot, rotate_about_pivot

area = next(a for a in bpy.context.screen.areas if a.type == "VIEW_3D")
region = next(r for r in area.regions if r.type == "WINDOW")
view = SimpleNamespace()
target = SimpleNamespace(window=bpy.context.window, area=area, region=region, region_3d=view)
view.view_perspective = "PERSP"
view.view_rotation = Quaternion((1, 0, 0, 0))
view.view_location = Vector((0, 0, 0))
view.view_distance = 10
bpy.context.view_layer.update()
# Background Blender cannot update a GPU viewport's projection matrices safely.
# Use a deterministic projection but real scene ray casting and quaternion math.
import bpy_extras.view3d_utils as utils

utils.region_2d_to_origin_3d = lambda region, view, center: view.view_location + Vector((0, 0, 10))
utils.region_2d_to_vector_3d = lambda region, view, center: Vector((0, 0, -1))
utils.location_3d_to_region_2d = lambda region, view, point: Vector(
    (
        region.width / 2 + 50 * (point.x - view.view_location.x),
        region.height / 2 + 50 * (point.y - view.view_location.y),
    )
)
location_before = view.view_location.copy()
pivot = choose_pivot(target)
assert (view.view_location - location_before).length < 1e-5, "Choosing pivot moved the view"
assert abs(pivot.z - 1) < 0.01, ("Expected center ray to hit cube surface", pivot)

bpy.data.objects["Camera"].location = (10000, 10000, 10000)
bpy.context.view_layer.update()
assert (choose_pivot(target) - pivot).length < 1e-5, "Distant camera influenced pivot"


def camera_relative_point():
    camera = view.view_location + view.view_rotation @ Vector((0, 0, view.view_distance))
    return view.view_rotation.inverted() @ (pivot - camera)


before = camera_relative_point()
rotate_about_pivot(view, Quaternion(Vector((0, 1, 0)), 0.3), pivot)
assert (camera_relative_point() - before).length < 1e-5, "Camera did not orbit chosen point"
assert (view.view_location - location_before).length > 0.01, "Only orientation changed"

view.view_rotation = Quaternion((1, 0, 0, 0))
view.view_location = Vector((3, 0, 0))
fallback = choose_pivot(target)
assert fallback.length < 0.01, ("Expected nearby mesh fallback, not camera/scene bounds", fallback)
print("DYNAMIC_PIVOT_OK: surface hit, no reframe, camera ignored, real orbit, mesh fallback")
