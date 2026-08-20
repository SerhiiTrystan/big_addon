import hashlib
import json
import math
import os
import time
import uuid
from datetime import datetime

import bpy
import bpy.utils.previews
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup

from .utils import get_data_dir


# -----------------------------------------------------------------------------
# TSG Mat - lightweight material browser + persistent Cycles preview cache
# -----------------------------------------------------------------------------

CACHE_VERSION = 1
CACHE_DIRNAME = "material_previews"
CACHE_FILENAME = "cache.json"
PREVIEW_SCENE_NAME = ".TSG_MAT_PREVIEW"
UUID_KEY = "tsg_mat_uuid"
TAG_KEY = "tsg_mat_tag"

_preview_collection = None
_timer_registered = False


def _cache_dir():
    path = os.path.join(get_data_dir(), CACHE_DIRNAME)
    os.makedirs(path, exist_ok=True)
    return path


def _cache_path():
    return os.path.join(_cache_dir(), CACHE_FILENAME)


def _default_cache():
    return {"version": CACHE_VERSION, "tags": [], "materials": {}}


def load_cache():
    path = _cache_path()
    if not os.path.isfile(path):
        return _default_cache()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return _default_cache()
    if not isinstance(data, dict):
        return _default_cache()
    data.setdefault("version", CACHE_VERSION)
    data.setdefault("tags", [])
    data.setdefault("materials", {})
    if not isinstance(data["tags"], list):
        data["tags"] = []
    if not isinstance(data["materials"], dict):
        data["materials"] = {}
    return data


def save_cache(data):
    path = _cache_path()
    tmp = path + ".tmp"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def get_material_uuid(mat):
    value = mat.get(UUID_KEY)
    if value and not mat.library:
        # A normal Blender material copy also copies custom properties. Repair
        # duplicate UUIDs lazily so two cards never share one preview file.
        duplicate = next((other for other in bpy.data.materials
                          if other != mat and other.get(UUID_KEY) == value), None)
        if duplicate is not None:
            value = str(uuid.uuid4())
            mat[UUID_KEY] = value
    if not value and not mat.library:
        value = str(uuid.uuid4())
        mat[UUID_KEY] = value
    if not value:
        # Linked data cannot be edited; build a stable session-independent key.
        lib = mat.library.filepath if mat.library else ""
        value = "linked-" + hashlib.sha1(f"{lib}|{mat.name_full}".encode("utf-8")).hexdigest()
    return str(value)


def get_material_tag(mat):
    return str(mat.get(TAG_KEY, ""))


def set_material_tag(mat, tag):
    if mat.library:
        return False
    if tag:
        mat[TAG_KEY] = tag
    elif TAG_KEY in mat:
        del mat[TAG_KEY]
    return True


def material_is_supported(mat):
    return mat is not None and not getattr(mat, "is_grease_pencil", False)


def _serialise_value(value):
    if hasattr(value, "to_tuple"):
        try:
            return tuple(round(float(v), 7) for v in value.to_tuple())
        except Exception:
            pass
    if isinstance(value, (tuple, list)):
        try:
            return tuple(round(float(v), 7) if isinstance(v, (int, float)) else str(v) for v in value)
        except Exception:
            return str(value)
    if isinstance(value, float):
        return round(value, 7)
    if isinstance(value, (int, bool, str)) or value is None:
        return value
    return str(value)


def material_hash(mat):
    """Hash visible shader state + image paths/mtimes. Cheap enough for periodic checks."""
    # Only visual shader state belongs in the preview hash. Renaming or tagging
    # a material must not trigger an expensive Cycles rerender.
    payload = [bool(mat.use_nodes)]
    if not mat.use_nodes or not mat.node_tree:
        payload.extend([
            _serialise_value(getattr(mat, "diffuse_color", None)),
            _serialise_value(getattr(mat, "metallic", None)),
            _serialise_value(getattr(mat, "roughness", None)),
        ])
    else:
        nt = mat.node_tree
        for node in sorted(nt.nodes, key=lambda n: (n.bl_idname, n.name)):
            item = [node.bl_idname, node.name, bool(node.mute)]
            if getattr(node, "node_tree", None):
                item.append(("group", node.node_tree.name_full))
            image = getattr(node, "image", None)
            if image:
                abs_path = bpy.path.abspath(image.filepath) if image.filepath else ""
                try:
                    mtime = os.path.getmtime(abs_path) if abs_path and os.path.isfile(abs_path) else None
                except OSError:
                    mtime = None
                item.append(("image", image.name_full, abs_path, mtime, image.source))
                try:
                    item.append(("colorspace", image.colorspace_settings.name))
                except Exception:
                    pass
            for socket in node.inputs:
                if not socket.is_linked and hasattr(socket, "default_value"):
                    item.append((socket.identifier, _serialise_value(socket.default_value)))
            payload.append(item)
        links = []
        for link in nt.links:
            links.append((link.from_node.name, link.from_socket.identifier,
                          link.to_node.name, link.to_socket.identifier))
        payload.append(sorted(links))

    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def preview_filepath(mat):
    return os.path.join(_cache_dir(), f"{get_material_uuid(mat)}.png")


def _reset_preview_collection():
    global _preview_collection
    if _preview_collection is not None:
        try:
            bpy.utils.previews.remove(_preview_collection)
        except Exception:
            pass
    _preview_collection = bpy.utils.previews.new()


def get_preview_icon_id(mat):
    global _preview_collection
    if _preview_collection is None:
        _reset_preview_collection()
    path = preview_filepath(mat)
    if not os.path.isfile(path):
        return 0
    key = get_material_uuid(mat)
    try:
        if key not in _preview_collection:
            _preview_collection.load(key, path, 'IMAGE')
        return _preview_collection[key].icon_id
    except Exception:
        return 0


def cache_entry(mat, cache=None):
    cache = cache or load_cache()
    return cache.get("materials", {}).get(get_material_uuid(mat), {})


def preview_state(mat, cache=None, current_hash=None):
    cache = cache or load_cache()
    entry = cache_entry(mat, cache)
    path = preview_filepath(mat)
    if not entry or not os.path.isfile(path):
        return 'MISSING'
    current_hash = current_hash or material_hash(mat)
    if entry.get("hash") != current_hash:
        return 'STALE'
    return 'READY'


def selected_names(scene):
    return {item.name for item in scene.tsg_mat_selected}


def set_selected_names(scene, names):
    scene.tsg_mat_selected.clear()
    for name in sorted(set(names)):
        if bpy.data.materials.get(name):
            item = scene.tsg_mat_selected.add()
            item.name = name


def redraw_view3d():
    wm = getattr(bpy.context, "window_manager", None)
    if not wm:
        return
    for window in wm.windows:
        screen = window.screen
        if not screen:
            continue
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


def _material_list(context):
    scene = context.scene
    search = scene.tsg_mat_search.strip().lower()
    active_tag = scene.tsg_mat_active_tag
    selected = selected_names(scene)
    result = []
    for mat in bpy.data.materials:
        if not material_is_supported(mat):
            continue
        if search and search not in mat.name.lower():
            continue
        if active_tag == "__UNTAGGED__" and get_material_tag(mat):
            continue
        if active_tag not in {"", "__ALL__", "__UNTAGGED__"} and get_material_tag(mat) != active_tag:
            continue
        if scene.tsg_mat_isolate and selected and mat.name not in selected:
            continue
        result.append(mat)
    return result


# -----------------------------------------------------------------------------
# Preview renderer
# -----------------------------------------------------------------------------


def _create_preview_scene(settings):
    # Remove stale temporary scene from an interrupted previous job.
    old = bpy.data.scenes.get(PREVIEW_SCENE_NAME)
    if old:
        bpy.data.scenes.remove(old, do_unlink=True)

    scene = bpy.data.scenes.new(PREVIEW_SCENE_NAME)
    scene.render.engine = 'CYCLES'
    scene.render.resolution_x = settings.tsg_mat_resolution
    scene.render.resolution_y = settings.tsg_mat_resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False
    try:
        scene.cycles.samples = settings.tsg_mat_samples
        scene.cycles.use_denoising = True
    except Exception:
        pass

    world = bpy.data.worlds.new(PREVIEW_SCENE_NAME + "_World")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.055, 0.055, 0.055, 1.0)
        bg.inputs[1].default_value = 0.35
    scene.world = world

    return scene


def _add_area_light(scene, name, location, energy, size):
    data = bpy.data.lights.new(name, type='AREA')
    data.energy = energy
    data.shape = 'DISK'
    data.size = size
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = location
    # Point down roughly toward origin.
    direction = -obj.location
    obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    return obj


def _build_preview_rig(context, scene):
    window = context.window
    old_scene = window.scene if window else None
    if window:
        window.scene = scene
    try:
        # Blender's primitive operator gives us a proper UV layer, which is
        # important for ordinary Image Texture/TGA materials.
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, location=(0, 0, 0))
        sphere = context.active_object
        sphere.name = PREVIEW_SCENE_NAME + "_Sphere"
        bpy.ops.object.shade_smooth()

        bpy.ops.object.camera_add(location=(0.0, -3.15, 0.15))
        camera = context.active_object
        camera.name = PREVIEW_SCENE_NAME + "_Camera"
        camera.data.lens = 58
        camera.rotation_euler = ((math.radians(90), 0, 0))
        direction = -camera.location
        camera.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
        scene.camera = camera

        _add_area_light(scene, PREVIEW_SCENE_NAME + "_Key", (-2.2, -2.3, 3.0), 850, 4.0)
        _add_area_light(scene, PREVIEW_SCENE_NAME + "_Fill", (2.8, -1.2, 1.5), 500, 3.0)
        _add_area_light(scene, PREVIEW_SCENE_NAME + "_Rim", (0.8, 2.2, 2.4), 700, 3.0)
        return sphere
    finally:
        if window and old_scene:
            window.scene = old_scene


def _render_material(context, scene, sphere, mat, filepath):
    window = context.window
    old_scene = window.scene if window else None
    try:
        if window:
            window.scene = scene
        sphere.data.materials.clear()
        sphere.data.materials.append(mat)
        scene.render.filepath = filepath
        bpy.ops.render.render(write_still=True)
    finally:
        sphere.data.materials.clear()
        if window and old_scene:
            window.scene = old_scene


def render_previews(context, materials, force=False, operator=None):
    if not materials:
        return 0, 0
    cache = load_cache()
    scene = None
    rendered = 0
    skipped = 0
    try:
        scene = _create_preview_scene(context.scene)
        sphere = _build_preview_rig(context, scene)
        for index, mat in enumerate(materials, 1):
            current = material_hash(mat)
            entry = cache_entry(mat, cache)
            path = preview_filepath(mat)
            if not force and entry.get("hash") == current and os.path.isfile(path):
                skipped += 1
                continue
            if operator:
                operator.report({'INFO'}, f"TSG Mat preview {index}/{len(materials)}: {mat.name}")
            _render_material(context, scene, sphere, mat, path)
            cache["materials"][get_material_uuid(mat)] = {
                "name": mat.name_full,
                "hash": current,
                "preview": os.path.basename(path),
                "rendered_at": datetime.now().isoformat(timespec="seconds"),
            }
            rendered += 1
            save_cache(cache)
    finally:
        if scene and scene.name in bpy.data.scenes:
            world = scene.world
            temp_objects = list(scene.objects)
            temp_data = [getattr(obj, "data", None) for obj in temp_objects]
            bpy.data.scenes.remove(scene, do_unlink=True)
            for obj in temp_objects:
                try:
                    if obj.name in bpy.data.objects:
                        bpy.data.objects.remove(obj, do_unlink=True)
                except Exception:
                    pass
            # Objects do not necessarily delete their mesh/light/camera datablocks.
            for data in temp_data:
                if not data or getattr(data, "users", 1) != 0:
                    continue
                try:
                    if isinstance(data, bpy.types.Mesh):
                        bpy.data.meshes.remove(data)
                    elif isinstance(data, bpy.types.Light):
                        bpy.data.lights.remove(data)
                    elif isinstance(data, bpy.types.Camera):
                        bpy.data.cameras.remove(data)
                except Exception:
                    pass
            if world and world.users == 0:
                bpy.data.worlds.remove(world)
        _reset_preview_collection()
        redraw_view3d()
    return rendered, skipped


# -----------------------------------------------------------------------------
# Properties
# -----------------------------------------------------------------------------


class TSGMatName(PropertyGroup):
    name: StringProperty(name="Name")


# -----------------------------------------------------------------------------
# Tags
# -----------------------------------------------------------------------------


class TSGMAT_OT_add_tag(Operator):
    bl_idname = "tsg_mat.add_tag"
    bl_label = "Add Material Tag"
    bl_options = {'REGISTER', 'UNDO'}

    tag_name: StringProperty(name="Tag", default="New Tag")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "tag_name")

    def execute(self, context):
        tag = self.tag_name.strip()
        if not tag or tag.startswith("__"):
            self.report({'ERROR'}, "Invalid tag name")
            return {'CANCELLED'}
        cache = load_cache()
        if tag not in cache["tags"]:
            cache["tags"].append(tag)
            cache["tags"] = sorted(set(cache["tags"]), key=str.lower)
            save_cache(cache)
        context.scene.tsg_mat_active_tag = tag
        redraw_view3d()
        return {'FINISHED'}


class TSGMAT_OT_remove_tag(Operator):
    bl_idname = "tsg_mat.remove_tag"
    bl_label = "Remove Active Tag"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.tsg_mat_active_tag not in {"", "__ALL__", "__UNTAGGED__"}

    def execute(self, context):
        tag = context.scene.tsg_mat_active_tag
        for mat in bpy.data.materials:
            if get_material_tag(mat) == tag:
                set_material_tag(mat, "")
        cache = load_cache()
        cache["tags"] = [t for t in cache["tags"] if t != tag]
        save_cache(cache)
        context.scene.tsg_mat_active_tag = "__ALL__"
        redraw_view3d()
        return {'FINISHED'}


class TSGMAT_OT_filter_tag(Operator):
    bl_idname = "tsg_mat.filter_tag"
    bl_label = "Filter by Tag"

    tag_name: StringProperty()

    def execute(self, context):
        context.scene.tsg_mat_active_tag = self.tag_name
        redraw_view3d()
        return {'FINISHED'}


class TSGMAT_OT_filter_menu(Operator):
    bl_idname = "tsg_mat.filter_menu"
    bl_label = "All Material Tags"

    def invoke(self, context, event):
        return context.window_manager.popup_menu(self.draw_menu, title="Filter Tags", icon='FILTER')

    def draw_menu(self, menu, context):
        layout = menu.layout
        active = context.scene.tsg_mat_active_tag
        for tag_name, label in (("__ALL__", "All"), ("__UNTAGGED__", "Untagged")):
            op = layout.operator("tsg_mat.filter_tag", text=label,
                                 icon='CHECKMARK' if active == tag_name else 'TAG')
            op.tag_name = tag_name
        layout.separator()
        for tag in load_cache()["tags"]:
            op = layout.operator("tsg_mat.filter_tag", text=tag,
                                 icon='CHECKMARK' if active == tag else 'TAG')
            op.tag_name = tag


class TSGMAT_OT_assign_tag(Operator):
    bl_idname = "tsg_mat.assign_tag"
    bl_label = "Assign Tag"
    bl_options = {'REGISTER', 'UNDO'}

    tag_name: StringProperty()
    material_name: StringProperty()

    def execute(self, context):
        targets = []
        if self.material_name:
            mat = bpy.data.materials.get(self.material_name)
            if mat:
                targets.append(mat)
        else:
            targets = [bpy.data.materials.get(n) for n in selected_names(context.scene)]
            targets = [m for m in targets if m]
        if not targets:
            self.report({'WARNING'}, "No material selected")
            return {'CANCELLED'}
        changed = 0
        for mat in targets:
            if set_material_tag(mat, self.tag_name):
                changed += 1
        self.report({'INFO'}, f"Tagged {changed} material(s)")
        redraw_view3d()
        return {'FINISHED'}


class TSGMAT_OT_clear_tag(Operator):
    bl_idname = "tsg_mat.clear_tag"
    bl_label = "Clear Tag"
    bl_options = {'REGISTER', 'UNDO'}

    material_name: StringProperty()

    def execute(self, context):
        mat = bpy.data.materials.get(self.material_name)
        if not mat:
            return {'CANCELLED'}
        if not set_material_tag(mat, ""):
            self.report({'WARNING'}, "Linked material cannot be edited")
            return {'CANCELLED'}
        redraw_view3d()
        return {'FINISHED'}


class TSGMAT_OT_tag_menu(Operator):
    bl_idname = "tsg_mat.tag_menu"
    bl_label = "Material Tag"

    material_name: StringProperty()

    def invoke(self, context, event):
        return context.window_manager.popup_menu(self.draw_menu, title="Tag", icon='TAG')

    def draw_menu(self, menu, context):
        layout = menu.layout
        mat = bpy.data.materials.get(self.material_name)
        current = get_material_tag(mat) if mat else ""
        op = layout.operator("tsg_mat.clear_tag", text="No Tag", icon='X')
        op.material_name = self.material_name
        for tag in load_cache()["tags"]:
            op = layout.operator("tsg_mat.assign_tag", text=tag,
                                 icon='CHECKMARK' if current == tag else 'TAG')
            op.material_name = self.material_name
            op.tag_name = tag


# -----------------------------------------------------------------------------
# Selection / assignment / editing
# -----------------------------------------------------------------------------


class TSGMAT_OT_toggle_select(Operator):
    bl_idname = "tsg_mat.toggle_select"
    bl_label = "Select Material"

    material_name: StringProperty()

    def execute(self, context):
        names = selected_names(context.scene)
        if self.material_name in names:
            names.remove(self.material_name)
        else:
            names.add(self.material_name)
        set_selected_names(context.scene, names)
        redraw_view3d()
        return {'FINISHED'}


class TSGMAT_OT_clear_selection(Operator):
    bl_idname = "tsg_mat.clear_selection"
    bl_label = "Clear Material Selection"

    def execute(self, context):
        context.scene.tsg_mat_selected.clear()
        redraw_view3d()
        return {'FINISHED'}


class TSGMAT_OT_pick(Operator):
    bl_idname = "tsg_mat.pick"
    bl_label = "Pick Materials from Selection"

    def execute(self, context):
        names = set()
        if context.mode == 'EDIT_MESH':
            for obj in context.objects_in_mode_unique_data:
                if obj.type != 'MESH':
                    continue
                for poly in obj.data.polygons:
                    if poly.select and poly.material_index < len(obj.material_slots):
                        mat = obj.material_slots[poly.material_index].material
                        if mat:
                            names.add(mat.name)
        else:
            for obj in context.selected_objects:
                if obj.type != 'MESH':
                    continue
                for slot in obj.material_slots:
                    if slot.material:
                        names.add(slot.material.name)
        set_selected_names(context.scene, names)
        self.report({'INFO'}, f"Picked {len(names)} material(s)")
        redraw_view3d()
        return {'FINISHED'}


class TSGMAT_OT_assign(Operator):
    bl_idname = "tsg_mat.assign"
    bl_label = "Assign Material"
    bl_options = {'REGISTER', 'UNDO'}

    material_name: StringProperty()

    def _target(self, context):
        if self.material_name:
            return bpy.data.materials.get(self.material_name)
        names = list(selected_names(context.scene))
        return bpy.data.materials.get(names[0]) if len(names) == 1 else None

    def execute(self, context):
        mat = self._target(context)
        if not mat:
            self.report({'ERROR'}, "Select exactly one material")
            return {'CANCELLED'}
        objects = context.objects_in_mode_unique_data if context.mode == 'EDIT_MESH' else context.selected_objects
        mesh_objects = [obj for obj in objects if obj and obj.type == 'MESH']
        if not mesh_objects:
            self.report({'ERROR'}, "Select a mesh object")
            return {'CANCELLED'}

        if context.mode == 'EDIT_MESH':
            # Preserve multi-object edit mode and assign only selected faces.
            for obj in mesh_objects:
                slot_index = next((i for i, slot in enumerate(obj.material_slots) if slot.material == mat), -1)
                if slot_index < 0:
                    obj.data.materials.append(mat)
                    slot_index = len(obj.data.materials) - 1
                for poly in obj.data.polygons:
                    if poly.select:
                        poly.material_index = slot_index
                obj.data.update()
        else:
            # Safe object-mode behavior: use active slot, or create one.
            for obj in mesh_objects:
                if not obj.material_slots:
                    obj.data.materials.append(mat)
                else:
                    idx = max(0, min(obj.active_material_index, len(obj.material_slots) - 1))
                    obj.material_slots[idx].material = mat
        self.report({'INFO'}, f"Assigned {mat.name}")
        return {'FINISHED'}


class TSGMAT_OT_select_objects(Operator):
    bl_idname = "tsg_mat.select_objects"
    bl_label = "Select Objects Using Materials"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        names = selected_names(context.scene)
        if not names:
            self.report({'WARNING'}, "No materials selected")
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        count = 0
        for obj in context.scene.objects:
            if obj.type == 'MESH' and any(slot.material and slot.material.name in names for slot in obj.material_slots):
                obj.select_set(True)
                count += 1
        self.report({'INFO'}, f"Selected {count} object(s)")
        return {'FINISHED'}


class TSGMAT_OT_create(Operator):
    bl_idname = "tsg_mat.create"
    bl_label = "New Material"
    bl_options = {'REGISTER', 'UNDO'}

    material_name: StringProperty(name="Name", default="Material")
    assign: BoolProperty(name="Assign to Selection", default=True)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "material_name")
        self.layout.prop(self, "assign")

    def execute(self, context):
        mat = bpy.data.materials.new(self.material_name.strip() or "Material")
        mat.use_nodes = True
        get_material_uuid(mat)
        set_selected_names(context.scene, {mat.name})
        if self.assign:
            bpy.ops.tsg_mat.assign(material_name=mat.name)
        redraw_view3d()
        return {'FINISHED'}


class TSGMAT_OT_duplicate(Operator):
    bl_idname = "tsg_mat.duplicate"
    bl_label = "Duplicate Material"
    bl_options = {'REGISTER', 'UNDO'}

    material_name: StringProperty()

    def execute(self, context):
        mat = bpy.data.materials.get(self.material_name)
        if not mat:
            return {'CANCELLED'}
        copy = mat.copy()
        copy.name = mat.name + " Copy"
        copy[UUID_KEY] = str(uuid.uuid4())
        set_selected_names(context.scene, {copy.name})
        redraw_view3d()
        return {'FINISHED'}


class TSGMAT_OT_rename(Operator):
    bl_idname = "tsg_mat.rename"
    bl_label = "Rename Material"
    bl_options = {'REGISTER', 'UNDO'}

    material_name: StringProperty()
    new_name: StringProperty(name="Name")

    def invoke(self, context, event):
        mat = bpy.data.materials.get(self.material_name)
        if not mat:
            return {'CANCELLED'}
        self.new_name = mat.name
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "new_name")

    def execute(self, context):
        mat = bpy.data.materials.get(self.material_name)
        if not mat or mat.library:
            self.report({'ERROR'}, "Material cannot be renamed")
            return {'CANCELLED'}
        old = mat.name
        mat.name = self.new_name.strip() or old
        names = selected_names(context.scene)
        if old in names:
            names.remove(old)
            names.add(mat.name)
            set_selected_names(context.scene, names)
        redraw_view3d()
        return {'FINISHED'}


class TSGMAT_OT_delete(Operator):
    bl_idname = "tsg_mat.delete"
    bl_label = "Delete Material"
    bl_options = {'REGISTER', 'UNDO'}

    material_name: StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        mat = bpy.data.materials.get(self.material_name)
        if not mat or mat.library:
            self.report({'ERROR'}, "Linked material cannot be deleted")
            return {'CANCELLED'}
        uid = get_material_uuid(mat)
        path = preview_filepath(mat)
        bpy.data.materials.remove(mat, do_unlink=True)
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass
        cache = load_cache()
        cache["materials"].pop(uid, None)
        save_cache(cache)
        set_selected_names(context.scene, selected_names(context.scene))
        _reset_preview_collection()
        redraw_view3d()
        return {'FINISHED'}


class TSGMAT_OT_edit_shader(Operator):
    bl_idname = "tsg_mat.edit_shader"
    bl_label = "Edit in Shader Editor"

    material_name: StringProperty()

    def execute(self, context):
        mat = bpy.data.materials.get(self.material_name)
        if not mat:
            return {'CANCELLED'}
        obj = context.active_object
        if obj and obj.type == 'MESH':
            obj.active_material = mat
        target_area = None
        for area in context.screen.areas if context.screen else []:
            if area.type == 'NODE_EDITOR':
                target_area = area
                break
        if target_area is None and context.area:
            target_area = context.area
            target_area.type = 'NODE_EDITOR'
        if target_area and target_area.type == 'NODE_EDITOR':
            space = target_area.spaces.active
            space.tree_type = 'ShaderNodeTree'
            try:
                space.shader_type = 'OBJECT'
            except Exception:
                pass
        return {'FINISHED'}


class TSGMAT_OT_select_unused(Operator):
    bl_idname = "tsg_mat.select_unused"
    bl_label = "Select Unused Materials"

    def execute(self, context):
        names = {mat.name for mat in bpy.data.materials
                 if material_is_supported(mat) and mat.users == 0 and not mat.use_fake_user and not mat.library}
        set_selected_names(context.scene, names)
        self.report({'INFO'}, f"Selected {len(names)} unused material(s)")
        redraw_view3d()
        return {'FINISHED'}


class TSGMAT_OT_delete_selected_unused(Operator):
    bl_idname = "tsg_mat.delete_selected_unused"
    bl_label = "Delete Selected Unused"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        names = list(selected_names(context.scene))
        deleted = 0
        for name in names:
            mat = bpy.data.materials.get(name)
            # Protected: linked, fake-user, actually used, or tagged materials.
            if not mat or mat.library or mat.users != 0 or mat.use_fake_user or get_material_tag(mat):
                continue
            uid = get_material_uuid(mat)
            path = preview_filepath(mat)
            bpy.data.materials.remove(mat, do_unlink=True)
            try:
                if os.path.isfile(path):
                    os.remove(path)
            except OSError:
                pass
            cache = load_cache()
            cache["materials"].pop(uid, None)
            save_cache(cache)
            deleted += 1
        context.scene.tsg_mat_selected.clear()
        _reset_preview_collection()
        self.report({'INFO'}, f"Deleted {deleted} untagged unused material(s)")
        redraw_view3d()
        return {'FINISHED'}


class TSGMAT_OT_card_menu(Operator):
    bl_idname = "tsg_mat.card_menu"
    bl_label = "Material Actions"

    material_name: StringProperty()

    def invoke(self, context, event):
        return context.window_manager.popup_menu(self.draw_menu, title=self.material_name, icon='MATERIAL')

    def draw_menu(self, menu, context):
        layout = menu.layout
        for op_id, text, icon in (
            ("tsg_mat.assign", "Assign", 'CHECKMARK'),
            ("tsg_mat.edit_shader", "Edit Shader", 'NODE_MATERIAL'),
            ("tsg_mat.duplicate", "Duplicate", 'DUPLICATE'),
            ("tsg_mat.rename", "Rename", 'GREASEPENCIL'),
            ("tsg_mat.tag_menu", "Tag", 'TAG'),
            ("tsg_mat.delete", "Delete", 'TRASH'),
        ):
            op = layout.operator(op_id, text=text, icon=icon)
            op.material_name = self.material_name


# -----------------------------------------------------------------------------
# Preview operators / popup
# -----------------------------------------------------------------------------


class TSGMAT_OT_update_previews(Operator):
    bl_idname = "tsg_mat.update_previews"
    bl_label = "Update Changed Previews"
    bl_description = "Render missing or changed material previews with Cycles"

    force_all: BoolProperty(default=False)

    def execute(self, context):
        mats = [m for m in bpy.data.materials if material_is_supported(m)]
        try:
            rendered, skipped = render_previews(context, mats, force=self.force_all, operator=self)
        except Exception as exc:
            self.report({'ERROR'}, f"Preview render failed: {exc}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Rendered {rendered}; unchanged {skipped}")
        return {'FINISHED'}


class TSGMAT_OT_update_selected_previews(Operator):
    bl_idname = "tsg_mat.update_selected_previews"
    bl_label = "Update Selected Previews"

    def execute(self, context):
        mats = [bpy.data.materials.get(n) for n in selected_names(context.scene)]
        mats = [m for m in mats if m]
        if not mats:
            self.report({'WARNING'}, "No materials selected")
            return {'CANCELLED'}
        try:
            rendered, skipped = render_previews(context, mats, force=True, operator=self)
        except Exception as exc:
            self.report({'ERROR'}, f"Preview render failed: {exc}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Rendered {rendered} selected preview(s)")
        return {'FINISHED'}


class TSGMAT_OT_show_popup(Operator):
    bl_idname = "tsg_mat.show_popup"
    bl_label = "TSG Mat Popup"

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=620)

    def draw(self, context):
        draw_material_manager(self.layout, context, popup=True)


# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------


def _draw_tags(layout, context):
    scene = context.scene
    tags = load_cache()["tags"]
    row = layout.row(align=True)
    op = row.operator("tsg_mat.filter_tag", text="All", depress=scene.tsg_mat_active_tag in {"", "__ALL__"})
    op.tag_name = "__ALL__"
    op = row.operator("tsg_mat.filter_tag", text="Untagged", depress=scene.tsg_mat_active_tag == "__UNTAGGED__")
    op.tag_name = "__UNTAGGED__"
    for tag in tags[:4]:
        op = row.operator("tsg_mat.filter_tag", text=tag, depress=scene.tsg_mat_active_tag == tag)
        op.tag_name = tag
    row.operator("tsg_mat.add_tag", text="", icon='ADD')
    row.operator("tsg_mat.remove_tag", text="", icon='REMOVE')
    if len(tags) > 4:
        row = layout.row(align=True)
        for tag in tags[4:8]:
            op = row.operator("tsg_mat.filter_tag", text=tag, depress=scene.tsg_mat_active_tag == tag)
            op.tag_name = tag
        if len(tags) > 8:
            row.operator("tsg_mat.filter_menu", text=f"More ({len(tags) - 8})", icon='DOWNARROW_HLT')


def _draw_card(cell, mat, selected, state):
    icon_id = get_preview_icon_id(mat)
    if icon_id:
        cell.template_icon(icon_value=icon_id, scale=5.0)
    else:
        box = cell.box()
        box.scale_y = 3.8
        box.label(text="", icon='MATERIAL')

    row = cell.row(align=True)
    op = row.operator("tsg_mat.toggle_select", text=mat.name, depress=selected)
    op.material_name = mat.name
    op = row.operator("tsg_mat.card_menu", text="", icon='DOWNARROW_HLT')
    op.material_name = mat.name

    tag = get_material_tag(mat)
    status_row = cell.row(align=True)
    op = status_row.operator("tsg_mat.tag_menu", text=tag or "No tag", icon='TAG')
    op.material_name = mat.name
    if state == 'MISSING':
        status_row.label(text="Missing", icon='ERROR')
    elif state == 'STALE':
        status_row.label(text="Changed", icon='FILE_REFRESH')


def draw_material_manager(layout, context, popup=False):
    scene = context.scene
    cache = load_cache()

    header = layout.row(align=True)
    header.operator("tsg_mat.create", text="New", icon='ADD')
    header.operator("tsg_mat.pick", text="Pick", icon='EYEDROPPER')
    if not popup:
        header.operator("tsg_mat.show_popup", text="Popup", icon='WINDOW')

    _draw_tags(layout, context)

    row = layout.row(align=True)
    row.prop(scene, "tsg_mat_search", text="", icon='VIEWZOOM')
    row.prop(scene, "tsg_mat_isolate", text="Isolate", toggle=True)
    if scene.tsg_mat_selected:
        row.operator("tsg_mat.clear_selection", text=f"Clear ({len(scene.tsg_mat_selected)})", icon='X')

    mats = _material_list(context)
    selected = selected_names(scene)
    ready = stale = missing = 0
    states = {}
    # Compute once per draw, then reuse for counters and cards.
    for mat in mats:
        state = preview_state(mat, cache=cache)
        states[mat.name] = state
        if state == 'READY':
            ready += 1
        elif state == 'STALE':
            stale += 1
        else:
            missing += 1

    layout.label(text=f"{len(mats)} materials  |  Ready {ready}  Changed {stale}  Missing {missing}")

    if mats:
        columns = 4 if popup else 2
        grid = layout.grid_flow(row_major=True, columns=columns, even_columns=True, even_rows=False)
        for mat in mats[:80]:
            _draw_card(grid.column(align=True), mat, mat.name in selected, states[mat.name])
        if len(mats) > 80:
            layout.label(text=f"Showing first 80 of {len(mats)}. Use Search/Tags to filter.", icon='INFO')
    else:
        layout.box().label(text="No materials match the current filter", icon='INFO')

    layout.separator()
    row = layout.row(align=True)
    row.operator("tsg_mat.assign", text="Assign", icon='CHECKMARK')
    row.operator("tsg_mat.select_objects", text="Select Objects", icon='RESTRICT_SELECT_OFF')
    if len(selected) == 1:
        name = next(iter(selected))
        op = row.operator("tsg_mat.edit_shader", text="Shader", icon='NODE_MATERIAL')
        op.material_name = name

    row = layout.row(align=True)
    row.operator("tsg_mat.select_unused", text="Select Unused", icon='CHECKBOX_HLT')
    sub = row.row(align=True)
    sub.alert = True
    sub.operator("tsg_mat.delete_selected_unused", text="Delete Unused", icon='TRASH')

    box = layout.box()
    box.label(text="Cycles Preview Cache", icon='RENDER_STILL')
    row = box.row(align=True)
    row.operator("tsg_mat.update_previews", text=f"Update Changed ({stale + missing})", icon='FILE_REFRESH')
    row.operator("tsg_mat.update_selected_previews", text="Selected", icon='RENDER_STILL')
    op = row.operator("tsg_mat.update_previews", text="Rebuild All", icon='RECOVER_LAST')
    op.force_all = True

    row = box.row(align=True)
    row.prop(scene, "tsg_mat_resolution", text="Size")
    row.prop(scene, "tsg_mat_samples", text="Samples")
    row = box.row(align=True)
    row.prop(scene, "tsg_mat_preview_mode", text="Check")
    if scene.tsg_mat_preview_mode != 'MANUAL':
        row.prop(scene, "tsg_mat_check_interval", text="Minutes")
    box.label(text="Automatic checks do not render unless Auto Render is selected.", icon='INFO')


class TSGMAT_PT_main(Panel):
    bl_label = "TSG Mat"
    bl_idname = "TSGMAT_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'TSG Mat'

    def draw(self, context):
        draw_material_manager(self.layout, context)


# -----------------------------------------------------------------------------
# Timer
# -----------------------------------------------------------------------------


def _preview_timer():
    global _timer_registered
    if not hasattr(bpy.types.Scene, "tsg_mat_preview_mode"):
        _timer_registered = False
        return None
    scene = getattr(bpy.context, "scene", None)
    if not scene:
        return 120.0
    interval = max(1.0, float(scene.tsg_mat_check_interval)) * 60.0
    if scene.tsg_mat_preview_mode == 'MANUAL':
        return interval

    # DETECT mode intentionally only redraws; preview_state() will mark changed
    # cards on the next draw without causing background GPU work.
    redraw_view3d()

    if scene.tsg_mat_preview_mode == 'AUTO':
        changed = []
        cache = load_cache()
        for mat in bpy.data.materials:
            if material_is_supported(mat) and preview_state(mat, cache=cache) != 'READY':
                changed.append(mat)
        if changed and bpy.context.window:
            try:
                render_previews(bpy.context, changed, force=False)
            except Exception:
                # Never break Blender's timer loop because a render context is unavailable.
                pass
    return interval


def _register_timer():
    global _timer_registered
    if not _timer_registered:
        bpy.app.timers.register(_preview_timer, first_interval=120.0, persistent=True)
        _timer_registered = True


def _unregister_timer():
    global _timer_registered
    try:
        if bpy.app.timers.is_registered(_preview_timer):
            bpy.app.timers.unregister(_preview_timer)
    except Exception:
        pass
    _timer_registered = False


CLASSES = (
    TSGMatName,
    TSGMAT_OT_add_tag,
    TSGMAT_OT_remove_tag,
    TSGMAT_OT_filter_tag,
    TSGMAT_OT_filter_menu,
    TSGMAT_OT_assign_tag,
    TSGMAT_OT_clear_tag,
    TSGMAT_OT_tag_menu,
    TSGMAT_OT_toggle_select,
    TSGMAT_OT_clear_selection,
    TSGMAT_OT_pick,
    TSGMAT_OT_assign,
    TSGMAT_OT_select_objects,
    TSGMAT_OT_create,
    TSGMAT_OT_duplicate,
    TSGMAT_OT_rename,
    TSGMAT_OT_delete,
    TSGMAT_OT_edit_shader,
    TSGMAT_OT_select_unused,
    TSGMAT_OT_delete_selected_unused,
    TSGMAT_OT_card_menu,
    TSGMAT_OT_update_previews,
    TSGMAT_OT_update_selected_previews,
    TSGMAT_OT_show_popup,
    TSGMAT_PT_main,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)

    bpy.types.Scene.tsg_mat_search = StringProperty(name="Search")
    bpy.types.Scene.tsg_mat_active_tag = StringProperty(name="Active Tag", default="__ALL__")
    bpy.types.Scene.tsg_mat_isolate = BoolProperty(name="Isolate Selected", default=False)
    bpy.types.Scene.tsg_mat_selected = bpy.props.CollectionProperty(type=TSGMatName)
    bpy.types.Scene.tsg_mat_resolution = IntProperty(name="Preview Size", default=256, min=64, max=1024, step=64)
    bpy.types.Scene.tsg_mat_samples = IntProperty(name="Samples", default=32, min=1, max=512)
    bpy.types.Scene.tsg_mat_preview_mode = EnumProperty(
        name="Preview Updates",
        items=(
            ('MANUAL', "Manual", "Only update when you press a render/update button"),
            ('DETECT', "Detect Changes", "Periodically detect changes without rendering"),
            ('AUTO', "Auto Render", "Periodically render only changed previews"),
        ),
        default='DETECT',
    )
    bpy.types.Scene.tsg_mat_check_interval = FloatProperty(name="Check Interval", default=2.0, min=1.0, max=60.0)

    _reset_preview_collection()
    _register_timer()


def unregister():
    _unregister_timer()
    global _preview_collection
    if _preview_collection is not None:
        try:
            bpy.utils.previews.remove(_preview_collection)
        except Exception:
            pass
        _preview_collection = None

    for name in (
        "tsg_mat_check_interval",
        "tsg_mat_preview_mode",
        "tsg_mat_samples",
        "tsg_mat_resolution",
        "tsg_mat_selected",
        "tsg_mat_isolate",
        "tsg_mat_active_tag",
        "tsg_mat_search",
    ):
        if hasattr(bpy.types.Scene, name):
            delattr(bpy.types.Scene, name)

    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
