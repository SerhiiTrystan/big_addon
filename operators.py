import os
import shutil
import uuid

import bpy

from . import validators
from .utils import (
    get_current_time_string,
    get_latest_blend_file,
    get_project_by_id,
    get_projects_json_path,
    is_same_file,
    load_projects_data,
    save_projects_data,
)


# =============================================================================
# UV MANAGER
# =============================================================================


class TSG_OT_uv_set_active(bpy.types.Operator):
    bl_idname = "tsg.uv_set_active"
    bl_label = "Set Active UV Map"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        name = context.scene.tsg_uv_map_selector
        if not name:
            self.report({'WARNING'}, "No UV map selected")
            return {'CANCELLED'}

        changed = 0
        for obj in context.selected_objects:
            if obj.type == 'MESH' and name in obj.data.uv_layers:
                obj.data.uv_layers.active = obj.data.uv_layers[name]
                changed += 1

        self.report({'INFO'}, f"Set '{name}' active on {changed} object(s)")
        return {'FINISHED'}


class TSG_OT_uv_create(bpy.types.Operator):
    bl_idname = "tsg.uv_create"
    bl_label = "Create UV Map"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        name = context.scene.tsg_uv_map_name.strip()
        if not name:
            self.report({'ERROR'}, "UV map name cannot be empty")
            return {'CANCELLED'}

        changed = 0
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            if name in obj.data.uv_layers:
                continue
            uv = obj.data.uv_layers.new(name=name)
            obj.data.uv_layers.active = uv
            changed += 1

        self.report({'INFO'}, f"Created '{name}' on {changed} object(s)")
        return {'FINISHED'}


class TSG_OT_uv_rename(bpy.types.Operator):
    bl_idname = "tsg.uv_rename"
    bl_label = "Rename Selected UV Map"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        old_name = context.scene.tsg_uv_map_selector
        new_name = context.scene.tsg_uv_map_name.strip()
        if not old_name or not new_name:
            self.report({'ERROR'}, "Select a UV map and enter a new name")
            return {'CANCELLED'}

        changed = 0
        for obj in context.selected_objects:
            if obj.type == 'MESH' and old_name in obj.data.uv_layers:
                obj.data.uv_layers[old_name].name = new_name
                changed += 1

        self.report({'INFO'}, f"Renamed UV map on {changed} object(s)")
        return {'FINISHED'}


class TSG_OT_uv_delete(bpy.types.Operator):
    bl_idname = "tsg.uv_delete"
    bl_label = "Delete Selected UV Map"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        name = context.scene.tsg_uv_map_selector
        if not name:
            return {'CANCELLED'}

        changed = 0
        for obj in context.selected_objects:
            if obj.type == 'MESH' and name in obj.data.uv_layers:
                obj.data.uv_layers.remove(obj.data.uv_layers[name])
                changed += 1

        self.report({'INFO'}, f"Deleted '{name}' from {changed} object(s)")
        return {'FINISHED'}


# =============================================================================
# BRIDGE: simple FBX exchange folder
# =============================================================================


def _exchange_folder(context):
    return bpy.path.abspath(context.scene.tsg_exchange_path)


def _fbx_export_available():
    return hasattr(bpy.ops, "export_scene") and hasattr(bpy.ops.export_scene, "fbx")


def _fbx_import_available():
    return hasattr(bpy.ops, "import_scene") and hasattr(bpy.ops.import_scene, "fbx")


class TSG_OT_bridge_export(bpy.types.Operator):
    bl_idname = "tsg.bridge_export"
    bl_label = "Export Selected FBX"

    def execute(self, context):
        if not context.selected_objects:
            self.report({'WARNING'}, "No objects selected")
            return {'CANCELLED'}
        if not _fbx_export_available():
            self.report({'ERROR'}, "FBX exporter is not available in this Blender installation")
            return {'CANCELLED'}

        folder = _exchange_folder(context)
        os.makedirs(folder, exist_ok=True)
        filepath = os.path.join(folder, "blender_export.fbx")

        try:
            bpy.ops.export_scene.fbx(
                filepath=filepath,
                use_selection=True,
                apply_unit_scale=True,
                bake_space_transform=True,
            )
        except Exception as exc:
            self.report({'ERROR'}, f"FBX export failed: {exc}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Exported: {filepath}")
        return {'FINISHED'}


class TSG_OT_bridge_import(bpy.types.Operator):
    bl_idname = "tsg.bridge_import"
    bl_label = "Import FBX"

    filename: bpy.props.EnumProperty(name="FBX File", items=lambda self, context: self.file_items(context))

    @staticmethod
    def file_items(context):
        folder = _exchange_folder(context)
        if not os.path.isdir(folder):
            return [("", "No FBX files", "Exchange folder does not exist")]
        files = sorted(f for f in os.listdir(folder) if f.lower().endswith(".fbx"))
        return [(f, f, "") for f in files] or [("", "No FBX files", "")]

    def invoke(self, context, event):
        if not _fbx_import_available():
            self.report({'ERROR'}, "FBX importer is not available in this Blender installation")
            return {'CANCELLED'}

        items = self.file_items(context)
        if not items or not items[0][0]:
            self.report({'WARNING'}, "No FBX files found")
            return {'CANCELLED'}
        if len(items) == 1:
            self.filename = items[0][0]
            return self.execute(context)
        return context.window_manager.invoke_props_dialog(self, width=420)

    def execute(self, context):
        if not self.filename:
            return {'CANCELLED'}
        filepath = os.path.join(_exchange_folder(context), self.filename)
        if not os.path.isfile(filepath):
            self.report({'ERROR'}, "Selected FBX file does not exist")
            return {'CANCELLED'}
        try:
            bpy.ops.import_scene.fbx(filepath=filepath)
        except Exception as exc:
            self.report({'ERROR'}, f"FBX import failed: {exc}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Imported: {self.filename}")
        return {'FINISHED'}


class TSG_OT_bridge_clear(bpy.types.Operator):
    bl_idname = "tsg.bridge_clear"
    bl_label = "Clear Exchange Folder"

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        folder = _exchange_folder(context)
        if not os.path.isdir(folder):
            self.report({'INFO'}, "Exchange folder does not exist")
            return {'FINISHED'}

        removed = 0
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            try:
                if os.path.isfile(path) or os.path.islink(path):
                    os.remove(path)
                    removed += 1
                elif os.path.isdir(path):
                    shutil.rmtree(path)
                    removed += 1
            except OSError as exc:
                self.report({'WARNING'}, f"Could not remove {name}: {exc}")

        self.report({'INFO'}, f"Removed {removed} item(s)")
        return {'FINISHED'}


# =============================================================================
# PROJECT MANAGER
# =============================================================================


def reload_projects_to_ui(context):
    scene = context.scene
    scene.tsg_projects.clear()

    data = load_projects_data()
    projects = list(data.get("projects", []))
    projects.sort(key=lambda p: (not bool(p.get("pinned")), p.get("name", "").lower()))

    for project in projects:
        item = scene.tsg_projects.add()
        item.project_id = project.get("id", "")
        item.name = project.get("name", "Unnamed Project")
        item.folder_path = project.get("folder_path", "")
        item.status = project.get("status", "ACTIVE")
        item.pinned = bool(project.get("pinned", False))

    if len(scene.tsg_projects) == 0:
        scene.tsg_project_index = 0
    else:
        scene.tsg_project_index = min(scene.tsg_project_index, len(scene.tsg_projects) - 1)


def get_active_project(context):
    scene = context.scene
    index = scene.tsg_project_index
    if 0 <= index < len(scene.tsg_projects):
        return scene.tsg_projects[index]
    return None


class TSG_OT_projects_reload(bpy.types.Operator):
    bl_idname = "tsg.projects_reload"
    bl_label = "Reload Projects"

    def execute(self, context):
        reload_projects_to_ui(context)
        return {'FINISHED'}


class TSG_OT_project_add(bpy.types.Operator):
    bl_idname = "tsg.project_add"
    bl_label = "Add Project"

    project_name: bpy.props.StringProperty(name="Project Name")
    folder_path: bpy.props.StringProperty(name="Project Folder", subtype='DIR_PATH')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=460)

    def execute(self, context):
        name = self.project_name.strip()
        folder = self.folder_path.strip()
        if not name or not folder:
            self.report({'WARNING'}, "Project name and folder are required")
            return {'CANCELLED'}

        data = load_projects_data()
        data["projects"].append({
            "id": str(uuid.uuid4()),
            "name": name,
            "folder_path": folder,
            "status": "ACTIVE",
            "pinned": False,
            "created_at": get_current_time_string(),
            "last_opened": None,
        })
        save_projects_data(data)
        reload_projects_to_ui(context)
        return {'FINISHED'}


class TSG_OT_project_edit(bpy.types.Operator):
    bl_idname = "tsg.project_edit"
    bl_label = "Edit Project"

    project_name: bpy.props.StringProperty(name="Project Name")
    folder_path: bpy.props.StringProperty(name="Project Folder", subtype='DIR_PATH')
    project_id: bpy.props.StringProperty(options={'HIDDEN'})

    def invoke(self, context, event):
        project = get_active_project(context)
        if not project:
            return {'CANCELLED'}
        self.project_id = project.project_id
        self.project_name = project.name
        self.folder_path = project.folder_path
        return context.window_manager.invoke_props_dialog(self, width=460)

    def execute(self, context):
        data, project = get_project_by_id(self.project_id)
        if not project:
            self.report({'ERROR'}, "Project was not found in JSON")
            return {'CANCELLED'}
        project["name"] = self.project_name.strip() or project.get("name", "Unnamed Project")
        project["folder_path"] = self.folder_path.strip()
        save_projects_data(data)
        reload_projects_to_ui(context)
        return {'FINISHED'}


class TSG_OT_project_toggle_archive(bpy.types.Operator):
    bl_idname = "tsg.project_toggle_archive"
    bl_label = "Archive / Restore"

    def execute(self, context):
        current = get_active_project(context)
        if not current:
            return {'CANCELLED'}
        data, project = get_project_by_id(current.project_id)
        if not project:
            return {'CANCELLED'}
        project["status"] = "ARCHIVED" if project.get("status") == "ACTIVE" else "ACTIVE"
        save_projects_data(data)
        reload_projects_to_ui(context)
        return {'FINISHED'}


class TSG_OT_project_toggle_pin(bpy.types.Operator):
    bl_idname = "tsg.project_toggle_pin"
    bl_label = "Pin / Unpin"

    def execute(self, context):
        current = get_active_project(context)
        if not current:
            return {'CANCELLED'}
        data, project = get_project_by_id(current.project_id)
        if not project:
            return {'CANCELLED'}
        project["pinned"] = not bool(project.get("pinned", False))
        save_projects_data(data)
        reload_projects_to_ui(context)
        return {'FINISHED'}


class TSG_OT_project_remove(bpy.types.Operator):
    bl_idname = "tsg.project_remove"
    bl_label = "Remove Project From List"

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        current = get_active_project(context)
        if not current:
            return {'CANCELLED'}
        data = load_projects_data()
        data["projects"] = [p for p in data.get("projects", []) if p.get("id") != current.project_id]
        save_projects_data(data)
        reload_projects_to_ui(context)
        return {'FINISHED'}


class TSG_OT_project_open_latest(bpy.types.Operator):
    bl_idname = "tsg.project_open_latest"
    bl_label = "Open Latest Blend"

    target_file: bpy.props.StringProperty(options={'HIDDEN'})
    project_id: bpy.props.StringProperty(options={'HIDDEN'})

    def invoke(self, context, event):
        current = get_active_project(context)
        if not current:
            self.report({'WARNING'}, "No project selected")
            return {'CANCELLED'}

        latest = get_latest_blend_file(current.folder_path)
        if not latest:
            self.report({'WARNING'}, "No .blend files found in the project folder")
            return {'CANCELLED'}

        self.target_file = latest["path"]
        self.project_id = current.project_id
        if is_same_file(bpy.data.filepath, self.target_file):
            self.report({'WARNING'}, "This Blender file is already open")
            return {'CANCELLED'}

        return context.window_manager.invoke_props_dialog(self, width=520)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Open the newest .blend file from this project?", icon='QUESTION')
        layout.separator()
        layout.label(text=os.path.basename(self.target_file), icon='FILE_BLEND')
        layout.label(text=self.target_file)
        if bpy.data.is_dirty:
            layout.separator()
            layout.label(text="Current file has unsaved changes.", icon='ERROR')

    def execute(self, context):
        if not self.target_file or not os.path.isfile(self.target_file):
            self.report({'ERROR'}, "Target .blend file no longer exists")
            return {'CANCELLED'}
        if is_same_file(bpy.data.filepath, self.target_file):
            self.report({'WARNING'}, "This Blender file is already open")
            return {'CANCELLED'}

        data, project = get_project_by_id(self.project_id)
        if project:
            project["last_opened"] = get_current_time_string()
            save_projects_data(data)

        bpy.ops.wm.open_mainfile(filepath=self.target_file)
        return {'FINISHED'}


class TSG_OT_project_open_json_location(bpy.types.Operator):
    bl_idname = "tsg.project_open_json_location"
    bl_label = "Show JSON Path"

    def execute(self, context):
        self.report({'INFO'}, get_projects_json_path())
        print("TSG projects JSON:", get_projects_json_path())
        return {'FINISHED'}


# =============================================================================
# VALIDATOR
# =============================================================================


class TSG_OT_validation_run(bpy.types.Operator):
    bl_idname = "tsg.validation_run"
    bl_label = "Run Validation"

    def execute(self, context):
        objects = list(context.selected_objects)
        if not objects:
            self.report({'WARNING'}, "No objects selected")
            return {'CANCELLED'}
        validators.run_all_checks(context.scene, objects)
        self.report({'INFO'}, f"Validation complete: {len(context.scene.tsg_validation_results)} result(s)")
        return {'FINISHED'}


class TSG_OT_validation_clear(bpy.types.Operator):
    bl_idname = "tsg.validation_clear"
    bl_label = "Clear Validation Results"

    def execute(self, context):
        context.scene.tsg_validation_results.clear()
        return {'FINISHED'}


class TSG_OT_validation_select_object(bpy.types.Operator):
    bl_idname = "tsg.validation_select_object"
    bl_label = "Select Problem Object"

    result_index: bpy.props.IntProperty()

    def execute(self, context):
        results = context.scene.tsg_validation_results
        if not 0 <= self.result_index < len(results):
            return {'CANCELLED'}

        obj = bpy.data.objects.get(results[self.result_index].object_name)
        if not obj:
            self.report({'WARNING'}, "Object not found")
            return {'CANCELLED'}

        if context.object and context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj
        return {'FINISHED'}


class TSG_OT_validation_select_elements(bpy.types.Operator):
    bl_idname = "tsg.validation_select_elements"
    bl_label = "Select Problem Elements"

    result_index: bpy.props.IntProperty()

    def execute(self, context):
        results = context.scene.tsg_validation_results
        if not 0 <= self.result_index < len(results):
            return {'CANCELLED'}

        item = results[self.result_index]
        obj = bpy.data.objects.get(item.object_name)
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "Mesh object not found")
            return {'CANCELLED'}
        if item.element_type == 'NONE' or not item.element_indices:
            self.report({'WARNING'}, "This result has no selectable mesh elements")
            return {'CANCELLED'}

        indices = [int(v) for v in item.element_indices.split(',') if v.strip().isdigit()]

        if context.object and context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj

        mesh = obj.data
        for vert in mesh.vertices:
            vert.select = False
        for edge in mesh.edges:
            edge.select = False
        for poly in mesh.polygons:
            poly.select = False

        if item.element_type == 'VERT':
            for i in indices:
                if 0 <= i < len(mesh.vertices):
                    mesh.vertices[i].select = True
            select_mode = 'VERT'
        elif item.element_type == 'EDGE':
            for i in indices:
                if 0 <= i < len(mesh.edges):
                    mesh.edges[i].select = True
            select_mode = 'EDGE'
        elif item.element_type == 'FACE':
            for i in indices:
                if 0 <= i < len(mesh.polygons):
                    mesh.polygons[i].select = True
            select_mode = 'FACE'
        else:
            return {'CANCELLED'}

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type=select_mode)
        return {'FINISHED'}


CLASSES = (
    TSG_OT_uv_set_active,
    TSG_OT_uv_create,
    TSG_OT_uv_rename,
    TSG_OT_uv_delete,
    TSG_OT_bridge_export,
    TSG_OT_bridge_import,
    TSG_OT_bridge_clear,
    TSG_OT_projects_reload,
    TSG_OT_project_add,
    TSG_OT_project_edit,
    TSG_OT_project_toggle_archive,
    TSG_OT_project_toggle_pin,
    TSG_OT_project_remove,
    TSG_OT_project_open_latest,
    TSG_OT_project_open_json_location,
    TSG_OT_validation_run,
    TSG_OT_validation_clear,
    TSG_OT_validation_select_object,
    TSG_OT_validation_select_elements,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)

    # Load JSON into the scene after registration. This does not require
    # bpy.ops and therefore is safe during addon enable/reload.
    try:
        reload_projects_to_ui(bpy.context)
    except Exception as exc:
        print("TSG: could not load project list:", exc)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
