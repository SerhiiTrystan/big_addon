import math
import re

import bmesh
from mathutils import kdtree


UV_NAME_PATTERN = re.compile(r"^map\d+$")
TRANSFORM_EPSILON = 1e-5


def add_result(scene, category, problem_type, obj, description,
               element_type='NONE', indices=None):
    item = scene.tsg_validation_results.add()
    item.category = category
    item.problem_type = problem_type
    item.object_name = obj.name if obj else ""
    item.description = description
    item.element_type = element_type
    item.element_indices = ",".join(str(i) for i in (indices or []))


# -----------------------------------------------------------------------------
# 1. Empty / degenerate object checks
# -----------------------------------------------------------------------------


def check_empty_objects(scene, objects):
    for obj in objects:
        if obj.type == 'EMPTY':
            add_result(
                scene, "Object", "Empty Object", obj,
                "Blender Empty object has no mesh data."
            )
            continue

        if obj.type != 'MESH':
            continue

        mesh = obj.data
        if len(mesh.vertices) == 0:
            add_result(scene, "Object", "Empty Mesh", obj, "Mesh has no vertices.")
        elif len(mesh.vertices) == 1:
            add_result(
                scene, "Object", "Single Vertex Mesh", obj,
                "Mesh contains only one vertex.", 'VERT', [0]
            )
        elif len(mesh.polygons) == 0 and len(mesh.edges) <= 1:
            add_result(
                scene, "Object", "Degenerate Mesh", obj,
                "Mesh has no faces and contains at most one edge.",
                'EDGE', [e.index for e in mesh.edges]
            )


# -----------------------------------------------------------------------------
# 2. Unapplied transforms
# -----------------------------------------------------------------------------


def check_unapplied_transforms(scene, objects):
    for obj in objects:
        problems = []

        if any(abs(v) > TRANSFORM_EPSILON for v in obj.location):
            problems.append("Location")
        if any(abs(v) > TRANSFORM_EPSILON for v in obj.rotation_euler):
            problems.append("Rotation")
        if any(abs(v - 1.0) > TRANSFORM_EPSILON for v in obj.scale):
            problems.append("Scale")

        if problems:
            add_result(
                scene, "Transform", "Unapplied Transform", obj,
                "Non-default transform values: " + ", ".join(problems) + "."
            )


# -----------------------------------------------------------------------------
# 3. Duplicate / very close vertices
# -----------------------------------------------------------------------------


def check_duplicate_vertices(scene, objects, threshold=0.001):
    for obj in objects:
        if obj.type != 'MESH' or len(obj.data.vertices) < 2:
            continue

        mesh = obj.data
        kd = kdtree.KDTree(len(mesh.vertices))
        for vert in mesh.vertices:
            kd.insert(vert.co, vert.index)
        kd.balance()

        checked_pairs = set()
        problem_indices = set()

        for vert in mesh.vertices:
            for _co, index, _distance in kd.find_range(vert.co, threshold):
                if index == vert.index:
                    continue
                pair = tuple(sorted((vert.index, index)))
                if pair in checked_pairs:
                    continue
                checked_pairs.add(pair)
                problem_indices.update(pair)

        if problem_indices:
            add_result(
                scene, "Geometry", "Duplicate / Close Vertices", obj,
                f"Found {len(problem_indices)} vertices within {threshold:g} units.",
                'VERT', sorted(problem_indices)
            )


# -----------------------------------------------------------------------------
# 4. UV naming check: map1, map2, map3 ...
# -----------------------------------------------------------------------------


def check_uv_maps_naming(scene, objects):
    for obj in objects:
        if obj.type != 'MESH':
            continue

        uv_layers = obj.data.uv_layers
        if not uv_layers:
            add_result(scene, "UV", "Missing UV Map", obj, "No UV maps found.")
            continue

        wrong_names = [uv.name for uv in uv_layers if not UV_NAME_PATTERN.fullmatch(uv.name)]
        if wrong_names:
            add_result(
                scene, "UV", "Wrong UV Map Name", obj,
                "Invalid names: " + ", ".join(wrong_names) +
                ". Expected format: map1, map2, map3 ..."
            )


# -----------------------------------------------------------------------------
# 5. Potentially flipped/inconsistent normals
# -----------------------------------------------------------------------------


def check_flipped_normals(scene, objects):
    """Compare current face normals with a recalculated copy.

    This is a heuristic. On open/non-manifold meshes Blender cannot always infer
    a unique 'outside', so the result is intentionally described as potential.
    """
    for obj in objects:
        if obj.type != 'MESH' or not obj.data.polygons:
            continue

        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bm.faces.ensure_lookup_table()
            original = [face.normal.copy() for face in bm.faces]
            bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
            bm.faces.ensure_lookup_table()

            flipped = [
                face.index
                for face, old_normal in zip(bm.faces, original)
                if old_normal.dot(face.normal) < -0.5
            ]
        finally:
            bm.free()

        if flipped:
            add_result(
                scene, "Normals", "Potentially Flipped Normals", obj,
                f"Found {len(flipped)} faces whose direction differs from recalculated normals.",
                'FACE', flipped
            )


def run_all_checks(scene, objects):
    scene.tsg_validation_results.clear()
    check_empty_objects(scene, objects)
    check_unapplied_transforms(scene, objects)
    check_duplicate_vertices(scene, objects)
    check_uv_maps_naming(scene, objects)
    check_flipped_normals(scene, objects)
