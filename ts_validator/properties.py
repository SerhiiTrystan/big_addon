from pydoc import describe

import bpy

from ts_uv import classes


class TSM_PT_result_item(bpy.types.PropertyGroup):
    category: bpy.props.StringProperty(name="Category")
    problem_type: bpy.props.StringProperty(name="Problem Type")
    object_name: bpy.props.StringProperty(name="Object Name")
    description: bpy.props.StringProperty(name="Description")
    element_type: bpy.props.StringProperty(name="Element Type")
    element_indices: bpy.props.IntProperty(name="Element Indices")

    classes = TSM_PT_result_item

    def register():
        for cls in classes:
            bpy.utils.register_class(cls)
        bpy.types.Scene.tsm_result_items = bpy.props.CollectionProperty(
            type=TSM_PT_result_item
        )
        bpy.types.Scene.tsm_result_index = bpy.props.IntProperty(default=0)

    def unregister():
        del bpy.types.Scene.tsm_result_items
        del bpy.types.Scene.tsm_result_index

        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)
