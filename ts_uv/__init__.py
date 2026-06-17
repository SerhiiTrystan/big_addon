from turtle import up

from . import operators

modules = [operators]

classes = [
    operators.TSUV_OT_set_active,
    operators.TSUV_OT_uv_map_rename,
    operators.TSUV_OT_uv_map_delete,
    operators.TSUV_OT_uv_map_create
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.uv_map_selector = bpy.props.EnumProperty(
        items=lambda self,
        context: [(name, name, "") for name in sorted (set(uv.name for obj in context.selected_objects if obj.type == 'MESH' for uv in obj.data.uv_layers))]
        name="UV Maps",
        description="Select UV Map",
        update=lambda self, context: None
    )
    bpy.types.Scene.new_uv_map_name = bpy.props.StringProperty(
        name="New UV Map Name",
        description="Name of the new UV map",
        default="map1"
    )


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.uv_map_selector
    del bpy.types.Scene.new_uv_map_name
