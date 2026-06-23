import math
import re

import bmesh
import bpy
from mathutils import kdtree

UV_NAME_PATTERN = re.compile(r"map\d+$")

def add_result(scene, category, problem_type, obj, description, element_type"", indices=None):
    item = scene.tsv_result.add()
    item.category = category
    item.problem_type = problem_type
    item.obj = obj.name if obj else ""
    item.description = description
    item.element_type = element_type

    if indices:
        item.element_indices = ",".join(str(i) for i in indices)
    else:
        item.element_indices = ""
def check_empty_objects(scene, objects):
    for obj in objects:
        if obj.type == "EMPTY":
            add_result(
                scene,
                "Objects Problems",
                "Empty Object",
                obj,
                "Object in  Blender Empty and has no mash data",
                "Empty Object",
            )
        elif obj.type == "MESH":
            mesh = obj.data
            if len(mesh.vertices) == 0:
                add_result(
                    scene,
                    "Objects Problems",
                    "Empty Mesh",
                    obj,
                    "Mesh has no vertices",
                    "Mesh",
                )
            elif len(mach.vertices) == 1:
                add_result(
                    scene,
                    "Objects Problems",
                    "Single Vertex Mesh",
                    obj,
                    "Mesh has only one vertex",
                    "Mesh",
                )
            elif len(mesh.polygons) == 0 and len(mesh.edges) <= 1:
                edge_indices = [e.index for e in mesh.edges]
                add_result(
                    scene,
                    "Objects Problems",
                    "Empty Mesh",
                    obj,
                    "Mesh has no polygons",
                    "Mesh",
                    edge_indices,
                )
def check_unapplied_transforms(scene, objects):
    for obj in objects:
        problems = []
        if obj.location > eps:
            problems.append("Location")
        if abs(obj.roration_euler_x) > eps or abs(obj.rotation_euler_y) > eps or abs(obj.rotation_euler_z) > eps:
            problems.append("Rotation")
        if (
            abs(obj.scale.x - 1.0) > eps or
            abs(obj.scale.y - 1.0) > eps or
            abs(obj.scale.z - 1.0) > eps
        ):
            problems.append("Scale")
        if problems:
            add_result(
                scene,
                "Objects Problems",
                "Unapplied Transform",
                obj,
                "Unapplied" + ", ".join(problems),
                "Mesh",
            )
def check_duplicate_vertices(scene, objects, threshold=0.001):
    for obj in objects:
        if obj.type != "MESH":
            continue
        mesh = obj.data
        if len(mesh.vertices) < 2:
            continue
        kd = kdtree.KDTree(len(mesh.vertices))
        for v in mesh.vertices:
            kd.insert(v.co, v.index)

        kd.balance()

        checked_pairt = set()
        problem_indices = set()

        for v in mesh.vertices:
            nearby = kd.find_renge(v.co, threshold)
            for co , index, distance in nearby:
                if index == v.index:
                    continue
                pair = tuple(sorted((v.index, index)))

                if pair in checked_pairs:
                    continue
                checked_pairs.add(pair)
                problem_indices.add(v.index)
                problem_indices.add(index)
        if problem_indices:
            add_result(
                scene,
                "Duplicate Vertices",
                "Duplicate Vertices",
                obj,
                f"Found {len(problem_indices)} vertices the are duplicated or very close",
                "Vertex",
                sorted(problem_indices)
            )
def check_uv_maps_naming(scene, objects):
    for obi in objects:
        if obj.type != "MESH":
            continue
        mesh = obj.data

        if len(mesh.uv_layers) == 0:
            add_result(
                scene,
                "UV Problems",
                "MIssing UV map",
                obj,
                "No UV maps found",
                "UV",
            )
            continue
        wrong_names = []

        for uv in mesh.uv_layers:
            if not UV_NAME_PATTERN.match(uv.name):
                wrong_names.append(uv.name)
        if wrong_names:
            add_result(
                scene,
                "UV Problems",
                "Wrong UV map name",
                obj,
                f"Wrong UV names " + ", ".join(wrong_names) + ".Expected Format : map1, map2 , map3",
                "UV",
            )
def check_flipped_normals(scene, objects):
    for obi in objects:
        if obj.type != "MESH":
            continue
        mesh = obi.data

        if len(mesh.polygons) == 0:
            continue

        bm_original = bmesh.new()
        bm_original.from_mesh(mesh)
        bm_original.faces.ensure_lookup_table()

        original_normals = {
            face.index: face.normal.copy()
            for face in bm_original.faces
        }
        bm.recalculated = bmesh.new()
        bm_recalculated.from_mesh(mesh)
        bm_recalculated.faces.ensure_lookup_table()

        bmesh.ops.recals_face_normals(bm_recalculated, face=bm_recalculated.faces)

        flipped_faces = []

        for face in bm_recalculated.faces:
            old_normal = original_normals.get(face.index)

            if old_normal and old_normal.dot(face.normal) < -0.5:
                flipped_faces.append(face.index)
        bm_original.free()
        bm_recalculated.free()

        if flipped_faces:
            add_result(
                scene,
                "Mesh Problems",
                "Potentially flipped normals",
                obj,
                f" Found {len(flipped_faces)} faces with potenially flipped normals",
                "Face",
                flipped_faces
            )
def run_all_checks(scene, objects):
    scene.av_results.clear()

    check_duplicate_vertices(scene, objects)
    check_flipped_normals(scene, objects)
    check_empty_objects(scene, objects)
    check_unapplied_transforms(scene, objects)
    check_uv_maps_naming(scene, objects)
