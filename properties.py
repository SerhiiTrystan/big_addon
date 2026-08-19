import bpy


# -----------------------------------------------------------------------------
# Shared properties
# -----------------------------------------------------------------------------


def uv_map_items(self, context):
    """Build a UV map selector from currently selected mesh objects."""
    names = set()
    if context:
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                names.update(uv.name for uv in obj.data.uv_layers)

    if not names:
        return [("", "No UV Maps", "No UV maps found on selected mesh objects")]

    return [(name, name, "") for name in sorted(names)]


class TSG_ProjectItem(bpy.types.PropertyGroup):
    project_id: bpy.props.StringProperty(name="Project ID")
    name: bpy.props.StringProperty(name="Project Name")
    folder_path: bpy.props.StringProperty(name="Folder Path", subtype='DIR_PATH')
    status: bpy.props.EnumProperty(
        name="Status",
        items=(
            ('ACTIVE', "Active", "Active project"),
            ('ARCHIVED', "Archived", "Archived project"),
        ),
        default='ACTIVE',
    )
    pinned: bpy.props.BoolProperty(name="Pinned", default=False)


class TSG_ValidationResult(bpy.types.PropertyGroup):
    category: bpy.props.StringProperty(name="Category")
    problem_type: bpy.props.StringProperty(name="Problem Type")
    object_name: bpy.props.StringProperty(name="Object Name")
    description: bpy.props.StringProperty(name="Description")
    element_type: bpy.props.EnumProperty(
        name="Element Type",
        items=(
            ('NONE', "None", "No mesh element selection"),
            ('VERT', "Vertex", "Vertex indices"),
            ('EDGE', "Edge", "Edge indices"),
            ('FACE', "Face", "Face indices"),
        ),
        default='NONE',
    )
    element_indices: bpy.props.StringProperty(name="Element Indices")


CLASSES = (
    TSG_ProjectItem,
    TSG_ValidationResult,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)

    # UV manager
    bpy.types.Scene.tsg_uv_map_selector = bpy.props.EnumProperty(
        name="UV Maps",
        description="UV map found on selected mesh objects",
        items=uv_map_items,
    )
    bpy.types.Scene.tsg_uv_map_name = bpy.props.StringProperty(
        name="UV Map Name",
        default="map1",
    )

    # Bridge
    bpy.types.Scene.tsg_exchange_path = bpy.props.StringProperty(
        name="Exchange Folder",
        description="Folder used by the Blender/Maya exchange bridge",
        subtype='DIR_PATH',
        default="//TSG_Exchange/",
    )

    # Project manager
    bpy.types.Scene.tsg_projects = bpy.props.CollectionProperty(type=TSG_ProjectItem)
    bpy.types.Scene.tsg_project_index = bpy.props.IntProperty(default=0)
    bpy.types.Scene.tsg_show_archived = bpy.props.BoolProperty(
        name="Show Archived",
        default=False,
    )

    # Validator
    bpy.types.Scene.tsg_validation_results = bpy.props.CollectionProperty(
        type=TSG_ValidationResult
    )
    bpy.types.Scene.tsg_validation_index = bpy.props.IntProperty(default=0)


def unregister():
    for name in (
        "tsg_validation_index",
        "tsg_validation_results",
        "tsg_show_archived",
        "tsg_project_index",
        "tsg_projects",
        "tsg_exchange_path",
        "tsg_uv_map_name",
        "tsg_uv_map_selector",
    ):
        if hasattr(bpy.types.Scene, name):
            delattr(bpy.types.Scene, name)

    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
