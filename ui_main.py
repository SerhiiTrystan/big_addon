import bpy

from . import ts_mat, ts_scs, ts_uv


class TSG_PT_ui_main(bpy.types.Panel):
    bl_label = "TSUV"
    bl_space_type = "TSG"
    bl_idname = "TSG_PT_ui_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "TSG"

    # uv part of ui
    def draw(self, context):
        layout = self.layout
        layout.label(text="UV Map Manegment", icon="UV Maps")
        # dinamic uv map list
        layout.prop(context.scene, "uv_map_selector", text="UV Maps")

        # buttons for uv map operators
        layout.operator("t", text="Set Active UV Map")
        layout.operator("t1", text="Delete Selected UV Map")

        layout.prop(context.scene, "new_uv_map_name", text="UV Map Name")
        layout.operator("t2", text="Create UV Map")
        layout.operator("t3", text="Rename UV Map")

# material panel
class TSG_PT_mat_panel(bpy.types.Panel):
    bl_label = "TSMaterial"
    bl_space_type = "TSG"
    bl_idname = "TSG_PT_mat_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "TSG"

    def draw(self, context):
        layout = self.layout

# bridge panel main
class TSG_PT_bridge_panel(bpy.types.Panel):
    bl_label = "TSBridge"
    bl_space_type = "TSG"
    bl_idname = "TSG_PT_bridge_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "TSG"

    def draw(self, context):
        layout = self.layout
        props - context.scene.exchange_props

        layout.prop(props, "exchange_path")
        layout.separator()
        layout.operator("t4", text="Export Selected Objects")
        layout.operator("t5", text="Import From Folder")
        layout.operator("t6", text="Clean Exchange Folder")
        
pass
