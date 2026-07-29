import bpy


class SPM_ProjectItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Project Name")
    folder_path: bpy.props.StringProperty(name="Folder Path", subtype='DIR_PATH')
    status: bpy.props.StringProperty(name="Status", default="active")
    pinned: bpy.props.BoolProperty(name="Pinned", default=False)


def register_properties():
    bpy.utils.register_class(SPM_ProjectItem)

    bpy.types.Scene.spm_projects = bpy.props.CollectionProperty(
        type=SPM_ProjectItem
    )

    bpy.types.Scene.spm_project_index = bpy.props.IntProperty(default=0)

    bpy.types.Scene.spm_show_archived = bpy.props.BoolProperty(
        name="Show Archived",
        default=False
    )


def unregister_properties():
    del bpy.types.Scene.spm_projects
    del bpy.types.Scene.spm_project_index
    del bpy.types.Scene.spm_show_archived

    bpy.utils.unregister_class(SPM_ProjectItem)
