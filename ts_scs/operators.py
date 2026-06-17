import bpy


class TSG_OT_scs_map_check(bpy.types.Operator):
    bl_idname = "tsg_ot_scs_map_check"
    bl_label = "Check naming ofUV map "

    def execute(self, context):
        for obj in context.selected_objects:
            for uv_map in obj.data.uv_layers:
                if uv_map.name != "UVMap":
                    uv_map_name = uv_map.name

                    pass

        return {"FINISHED"}
