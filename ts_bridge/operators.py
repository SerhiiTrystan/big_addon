
import bpy
import os

class TSB_OT_export_geo(bpy.types.Operator):
    bl_idname = "tsb.export_geo"
    bl_label = "Export Selected Geo"
    bl_description = "Export the selected geo to the selected folder on fbx format"

    def execute(self, context):
        props = context.scene.tsb_props
        path = bpy.path.abspath(props.tsg_path)
        os.makedirs(path, exist_ok=True)
        # Deleting old files from folder
        for file in os.listdir(path):
            if file.lower().endswith(".fbx"):
                os.remove(os.path.join(path, file))
        filepath = os.path.join(path, "blender_export.fbx")
        bpy.ops.export_scene.fbx(
            filepath=filepath
            use_selection=True
            apply_unit_scale=True
            bake_space_transform=True

        )
        self.report({'INFO'}, f"Exported {filepath}")
        return {'FINISHED'}

class TSB_OT_import_geo(bpy.types.Operator):
    bl_idname = "tsb.import_geo"
    bl_label = "Import Geo from folder"
    bl_description = "Import geo from the selected folder"

    def execute(self, context):
        props = context.scene.tsb_props
        path = bpy.path.abspath(props.tsg_path)
        if not os.path.exists(path):
            self.report({'ERROR'}, f"Path {path} does not exist")
            return {'CANCELLED'}
        fbx_files = [f for f in os.listdir(path) if f.lower().endswith(".fbx")]
        if not fbx_files:
            self.report({'INFO'}, "No fbx files found in folder")
            return {'FINISHED'}
        if len(fbx_files) == 1:
            filepath = os.path.join(path, fbx_files[0])
            bpy.ops.import_scene.fbx(
                filepath=filepath
            )
            self.report({'INFO'}, f"Imported {fbx_files[0]}")
            return {'FINISHED'}
        else:
            def draw(self.context):
                for f in fbx_files:
                    op = self.layout.operator("tsb.import_fbx", text=f)
                    op.filepath = f
                bpy.context.window_manager.popup_menu(draw, title="Import FBX", icon='FILE_FOLDER')
        return {'FINISHED'}

class TSB_OT_folder_path(bpy.types.Operator):
    bl_idname = "tsb.folder_path"
    bl_label = "Select Folder"

    filepath = bpy.props.StringProperty()

    def execute(self, context):
        props = context.scene.tsb_props
        path = bpy.path.abspath(props.tsg_path)
        filepath = bpy.path.abspath(path, self.filepath)

        if os.path.exists(filepath):
            bpy.ops.import_scene.fbx(filepath=filepath)
            self.report({'INFO'}, f"Imported {self.filepath}")
        else:
            self.report({'ERROR'}, f"File {self.filepath} does not exist")
        return {'FINISHED'}

class TSB_OT_clear_folder(bpy.types.Operator):
    bl_idname = "tsb.clear_folder"
    bl_label = "Clear Folder"
    bl_description = "Clear folder"

    def execute(self, context):
        props = context.scene.tsb_props
        path = bpy.path.abspath(props.tsg_path)
        if os.path.exists(path):
            for file in os.listdir(path):
                os.remove(os.path.join(path, file))
            self.report({'INFO'}, f"Cleared folder {path}")
        else:
            self.report({'INFO'}, f"Folder {path} does not exist")
        return {'FINISHED'}
