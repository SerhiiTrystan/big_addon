import bpy

from .properties import get_addon_preferences


class TSG_UL_projects(bpy.types.UIList):
    """Project list. Real paths stay out of the main list by design."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text="", icon='PINNED' if item.pinned else 'BLANK1')
        row.label(text=item.name, icon='FILE_BLEND')
        if item.status == 'ARCHIVED':
            row.label(text="Archived", icon='PACKAGE')

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        flags = [self.bitflag_filter_item] * len(items)
        if not context.scene.tsg_show_archived:
            for i, item in enumerate(items):
                if item.status == 'ARCHIVED':
                    flags[i] = 0
        return flags, []


def draw_projects(layout, context):
    scene = context.scene

    row = layout.row()
    row.template_list(
        "TSG_UL_projects", "",
        scene, "tsg_projects",
        scene, "tsg_project_index",
        rows=5,
    )
    col = row.column(align=True)
    col.operator("tsg.project_add", text="", icon='ADD')
    col.operator("tsg.project_remove", text="", icon='REMOVE')
    col.separator()
    col.operator("tsg.projects_reload", text="", icon='FILE_REFRESH')

    layout.prop(scene, "tsg_show_archived")

    if scene.tsg_projects and 0 <= scene.tsg_project_index < len(scene.tsg_projects):
        project = scene.tsg_projects[scene.tsg_project_index]
        box = layout.box()
        box.label(text=project.name, icon='FILE_BLEND')

        row = box.row(align=True)
        row.operator("tsg.project_open_latest", icon='FILE_FOLDER')
        row.operator("tsg.project_edit", text="Edit", icon='GREASEPENCIL')

        row = box.row(align=True)
        row.operator(
            "tsg.project_toggle_pin",
            text="Unpin" if project.pinned else "Pin",
            icon='PINNED' if project.pinned else 'UNPINNED',
        )
        row.operator(
            "tsg.project_toggle_archive",
            text="Restore" if project.status == 'ARCHIVED' else "Archive",
            icon='LOOP_BACK' if project.status == 'ARCHIVED' else 'PACKAGE',
        )

    layout.operator("tsg.project_open_json_location", icon='INFO')


def draw_uv(layout, context):
    scene = context.scene

    layout.prop(scene, "tsg_uv_map_selector", text="UV Map")
    row = layout.row(align=True)
    row.operator("tsg.uv_set_active", icon='CHECKMARK')
    row.operator("tsg.uv_delete", text="Delete", icon='TRASH')

    row = layout.row(align=True)
    row.operator("tsg.uv_hide_by_map", text="Hide With UV", icon='HIDE_ON')
    row.operator("tsg.uv_unhide_all", text="Unhide All", icon='HIDE_OFF')

    layout.separator()
    layout.prop(scene, "tsg_uv_map_name", text="Name")
    row = layout.row(align=True)
    row.operator("tsg.uv_create", icon='ADD')
    row.operator("tsg.uv_rename", icon='GREASEPENCIL')


def draw_bridge(layout, context):
    prefs = get_addon_preferences(context)
    layout.label(text=(prefs.exchange_path if prefs else "//TSG_Exchange/"), icon='FILE_FOLDER')
    row = layout.row(align=True)
    row.operator("tsg.bridge_export", text="Export", icon='EXPORT')
    row.operator("tsg.bridge_import", text="Import", icon='IMPORT')
    layout.operator("tsg.bridge_clear", icon='TRASH')


def draw_validator(layout, context):
    scene = context.scene

    row = layout.row(align=True)
    row.operator("tsg.validation_run", icon='VIEWZOOM')
    row.operator("tsg.validation_clear", text="Clear", icon='TRASH')

    results = scene.tsg_validation_results
    layout.label(text=f"Problems found: {len(results)}")
    if not results:
        layout.label(text="No validation results.", icon='INFO')
        return

    current_category = None
    for index, item in enumerate(results):
        if item.category != current_category:
            current_category = item.category
            layout.separator()
            layout.label(text=current_category, icon='FILE_FOLDER')

        box = layout.box()
        row = box.row()
        row.label(text=item.problem_type, icon='ERROR')
        box.label(text=f"Object: {item.object_name}")
        box.label(text=item.description)

        row = box.row(align=True)
        op = row.operator("tsg.validation_select_object", text="Object", icon='RESTRICT_SELECT_OFF')
        op.result_index = index
        if item.element_type != 'NONE' and item.element_indices:
            op = row.operator("tsg.validation_select_elements", text="Elements", icon='EDITMODE_HLT')
            op.result_index = index


class TSG_OT_show_popup(bpy.types.Operator):
    bl_idname = "tsg.show_popup"
    bl_label = "TSG Popup"

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=420)

    def draw(self, context):
        layout = self.layout
        layout.label(text="TSG", icon='TOOL_SETTINGS')

        box = layout.box()
        box.label(text="Project Manager", icon='FILEBROWSER')
        draw_projects(box, context)

        box = layout.box()
        box.label(text="UV Manager", icon='UV')
        draw_uv(box, context)

        box = layout.box()
        box.label(text="Bridge", icon='EXPORT')
        draw_bridge(box, context)

        box = layout.box()
        box.label(text="Validator", icon='CHECKMARK')
        draw_validator(box, context)


class TSG_PT_root(bpy.types.Panel):
    bl_label = "TSG"
    bl_idname = "TSG_PT_root"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'TSG'

    def draw(self, context):
        self.layout.label(text="Toolset", icon='TOOL_SETTINGS')


class TSG_PT_projects(bpy.types.Panel):
    bl_label = "Project Manager"
    bl_idname = "TSG_PT_projects"
    bl_parent_id = "TSG_PT_root"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'TSG'

    def draw(self, context):
        draw_projects(self.layout, context)


class TSG_PT_uv(bpy.types.Panel):
    bl_label = "UV Manager"
    bl_idname = "TSG_PT_uv"
    bl_parent_id = "TSG_PT_root"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'TSG'

    def draw(self, context):
        draw_uv(self.layout, context)


class TSG_PT_bridge(bpy.types.Panel):
    bl_label = "Bridge"
    bl_idname = "TSG_PT_bridge"
    bl_parent_id = "TSG_PT_root"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'TSG'

    def draw(self, context):
        draw_bridge(self.layout, context)


class TSG_PT_validator(bpy.types.Panel):
    bl_label = "Validator"
    bl_idname = "TSG_PT_validator"
    bl_parent_id = "TSG_PT_root"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'TSG'

    def draw(self, context):
        draw_validator(self.layout, context)


CLASSES = (
    TSG_UL_projects,
    TSG_OT_show_popup,
    TSG_PT_root,
    TSG_PT_projects,
    TSG_PT_uv,
    TSG_PT_bridge,
    TSG_PT_validator,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
