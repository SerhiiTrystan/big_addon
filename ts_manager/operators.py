import bpy
import os

from .utils import (
    load_projects_data,
    save_projects_data,
    get_latest_blend_file,
    is_same_file,
    get_current_time_string,
)


def reload_projects_to_ui(context):
    scene = context.scene
    scene.spm_projects.clear()

    data = load_projects_data()
    projects = data.get("projects", [])

    # Сначала закреплённые, потом обычные
    projects.sort(key=lambda p: (not p.get("pinned", False), p.get("name", "").lower()))

    for project in projects:
        item = scene.spm_projects.add()
        item.name = project.get("name", "Unnamed Project")
        item.folder_path = project.get("folder_path", "")
        item.status = project.get("status", "active")
        item.pinned = project.get("pinned", False)

    if scene.spm_project_index >= len(scene.spm_projects):
        scene.spm_project_index = max(0, len(scene.spm_projects) - 1)


def get_active_project(context):
    scene = context.scene

    if not scene.spm_projects:
        return None

    index = scene.spm_project_index

    if index < 0 or index >= len(scene.spm_projects):
        return None

    return scene.spm_projects[index]


class SPM_OT_reload_projects(bpy.types.Operator):
    bl_idname = "spm.reload_projects"
    bl_label = "Reload Projects"

    def execute(self, context):
        reload_projects_to_ui(context)
        self.report({'INFO'}, "Projects reloaded from JSON")
        return {'FINISHED'}


class SPM_OT_add_project(bpy.types.Operator):
    bl_idname = "spm.add_project"
    bl_label = "Add Project"

    project_name: bpy.props.StringProperty(name="Project Name")
    folder_path: bpy.props.StringProperty(name="Project Folder", subtype='DIR_PATH')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=450)

    def execute(self, context):
        if not self.project_name.strip():
            self.report({'WARNING'}, "Project name is empty")
            return {'CANCELLED'}

        if not self.folder_path.strip():
            self.report({'WARNING'}, "Folder path is empty")
            return {'CANCELLED'}

        data = load_projects_data()

        data["projects"].append({
            "name": self.project_name.strip(),
            "folder_path": self.folder_path,
            "status": "active",
            "pinned": False,
            "created_at": get_current_time_string(),
            "last_opened": None,
        })

        save_projects_data(data)
        reload_projects_to_ui(context)

        return {'FINISHED'}


class SPM_OT_edit_project(bpy.types.Operator):
    bl_idname = "spm.edit_project"
    bl_label = "Edit Project"

    project_name: bpy.props.StringProperty(name="Project Name")
    folder_path: bpy.props.StringProperty(name="Project Folder", subtype='DIR_PATH')

    def invoke(self, context, event):
        project = get_active_project(context)

        if not project:
            self.report({'WARNING'}, "No project selected")
            return {'CANCELLED'}

        self.project_name = project.name
        self.folder_path = project.folder_path

        return context.window_manager.invoke_props_dialog(self, width=450)

    def execute(self, context):
        project = get_active_project(context)

        if not project:
            return {'CANCELLED'}

        data = load_projects_data()

        for item in data.get("projects", []):
            if item.get("name") == project.name and item.get("folder_path") == project.folder_path:
                item["name"] = self.project_name.strip()
                item["folder_path"] = self.folder_path
                break

        save_projects_data(data)
        reload_projects_to_ui(context)

        return {'FINISHED'}


class SPM_OT_toggle_archive(bpy.types.Operator):
    bl_idname = "spm.toggle_archive"
    bl_label = "Toggle Archive"

    def execute(self, context):
        project = get_active_project(context)

        if not project:
            return {'CANCELLED'}

        data = load_projects_data()

        for item in data.get("projects", []):
            if item.get("name") == project.name and item.get("folder_path") == project.folder_path:
                item["status"] = "archived" if item.get("status") == "active" else "active"
                break

        save_projects_data(data)
        reload_projects_to_ui(context)

        return {'FINISHED'}


class SPM_OT_toggle_pin(bpy.types.Operator):
    bl_idname = "spm.toggle_pin"
    bl_label = "Pin / Unpin Project"

    def execute(self, context):
        project = get_active_project(context)

        if not project:
            return {'CANCELLED'}

        data = load_projects_data()

        for item in data.get("projects", []):
            if item.get("name") == project.name and item.get("folder_path") == project.folder_path:
                item["pinned"] = not item.get("pinned", False)
                break

        save_projects_data(data)
        reload_projects_to_ui(context)

        return {'FINISHED'}


class SPM_OT_remove_project(bpy.types.Operator):
    bl_idname = "spm.remove_project"
    bl_label = "Remove Project From List"

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        project = get_active_project(context)

        if not project:
            return {'CANCELLED'}

        data = load_projects_data()

        data["projects"] = [
            item for item in data.get("projects", [])
            if not (
                item.get("name") == project.name and
                item.get("folder_path") == project.folder_path
            )
        ]

        save_projects_data(data)
        reload_projects_to_ui(context)

        return {'FINISHED'}


class SPM_OT_open_latest_blend(bpy.types.Operator):
    bl_idname = "spm.open_latest_blend"
    bl_label = "Open Latest Blend"

    target_file: bpy.props.StringProperty()

    def invoke(self, context, event):
        project = get_active_project(context)

        if not project:
            self.report({'WARNING'}, "No project selected")
            return {'CANCELLED'}

        latest_file = get_latest_blend_file(project.folder_path)

        if not latest_file:
            self.report({'WARNING'}, "No .blend files found in project folder")
            return {'CANCELLED'}

        self.target_file = latest_file["path"]

        if is_same_file(bpy.data.filepath, self.target_file):
            self.report({'WARNING'}, "This file is already open")
            return {'CANCELLED'}

        return context.window_manager.invoke_props_dialog(self, width=500)

    def draw(self, context):
        layout = self.layout

        layout.label(text="Open this Blender file?")
        layout.separator()
        layout.label(text=os.path.basename(self.target_file))
        layout.label(text=self.target_file)

    def execute(self, context):
        if not self.target_file:
            return {'CANCELLED'}

        if is_same_file(bpy.data.filepath, self.target_file):
            self.report({'WARNING'}, "This file is already open")
            return {'CANCELLED'}

        bpy.ops.wm.open_mainfile(filepath=self.target_file)

        return {'FINISHED'}


classes = (
    SPM_OT_reload_projects,
    SPM_OT_add_project,
    SPM_OT_edit_project,
    SPM_OT_toggle_archive,
    SPM_OT_toggle_pin,
    SPM_OT_remove_project,
    SPM_OT_open_latest_blend,
)
