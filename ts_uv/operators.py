import bpy


class TSUV_OT_set_active(bpy.types.Operator):
    bl_idname = "object.tsuv_set_active"
    bl_label = "Set Active UV"
    bl_description = "Set selected uv map as active layer for the selected objects"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        uv_map_name = context.scene.uv_map_selector
        selected_object = context.selected_objects
        object_with_uv = []
        object_without_uv = []
        # iterate through selected objects
        for obj in selected_objects:
            if obj.type == "MESH" and uv_map_name in [
                uv.name for uv in obj.data.uv_layers
            ]:
                obj.data.uv_layers[uv_map_name].active = True
                object_with_uv.append(obj)
            else:
                object_without_uv.append(obj)
        # deselect all objects without uv what we need
        for obj in object_without_uv:
            obj.select_set(True)
        self.report({"INFO"}, f"Set '{uv_map_name}' as active for applicable objects")
        return {"FINISHED"}


# Delete uv from selected objects
class TSUV_OT_uv_map_delete(bpy.types.Operator):
    bl_idname = "object.tsuv_uv_map_delete"
    bl_label = "Delete Selected UV Map"
    bl_description = "Delete the selected UV map from the selected objects"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        uv_map_name = context.scene.uv_map_selector
        for obj in context.selected_objects:
            if obj.type == "MESH" and uv_map_name in [
                uv.name for uv in obj.data.uv_layers
            ]:
                obj.data.uv_layers.remove(obj.data.uv_layers[uv_map_name])
        self.report({"INFO"}, f"Deleted UV map '{uv_map_name}' from applicable objects")
        return {"FINISHED"}


# Creation new uv map
class TSUV_OT_uv_map_create(bpy.types.Operator):
    bl_idname = "object.tsuv_uv_map_create"
    bl_label = "Create UV Map"
    bl_description = "Create a new UV map on the selected objects"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        uv_map_name = context.scene.uv_map_name
        if not uv_map_name:
            self.report({"ERROR"}, "UV map name cannot be empty")
            return {"CANCELLED"}
        for obj in context.selected_objects:
            if obj.type == "MESH":
                new_uv = obj.data.uv_layers.new(name=uv_map_name)
                if new_uv:
                    new_uv.active = True
        self.report({"INFO"}, f"Created UV map '{uv_map_name}' on applicable objects")
        return {"FINISHED"}


# Rename selecter uv map
class TSUV_OT_uv_map_rename(bpy.types.Operator):
    bl_idname = "object.tsuv_uv_map_rename"
    bl_label = "Rename Selected UV Map"
    bl_description = "Rename the selected UV map on the selected objects"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        new_name = context.scene.new_uv_map_name
        if not new_name:
            self.report({"ERROR"}, "UV map name cannot be empty")
            return {"CANCELLED"}

        for obj in context.selected_objects:
            if obj.type == "MESH" and obj.data.uv_layers.active:
                obj.data.uv_layers.active.name = new_name
        self.report({"INFO"}, f"Renamed UV map to '{new_name}'")
        return {"FINISHED"}
