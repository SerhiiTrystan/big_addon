import bpy
import bmesh
from . import validators as val

class TSV_OT_run_validation(bpy.types.Operator):
    bl_idname = "tsv.run_validation"
    bl_label = "Run Validation"
    bl_description = "Check selected objects for asset problem"

    def execute(self, context):
        selected_objects = context.selected_objects

        if not selected_objects:
            self.report({'ERROR'}, "No objects selected")
            return {'CANCELLED'}

        val.run_all_checks(context.scene, selected_objects)
        self.report({'INFO'}, f"Validation finished,Found {len(context.scene.tsv_results)}")
        return {'FINISHED'}

class TSV_OT_clear_results(bpy.types.Operator):
    bl_idname = "tsv.clear_results"
    bl_label = "Clear Results"
    bl_description = "Clear all validation results"

    def execute(self, context):
        context.scene.tsv_results.clear()
        return {'FINISHED'}
class TSV_OT_select_problem_object(bpy.types.Operator):
    bl_idname = "tsv.select_problem_object"
    bl_label = "Select Problem Object"
    bl_description = "Select the object with the problem"

    result_index: bpy.props.IntProperty()

    def execute(self, context):
        results = context.scene.tsv_results

        if self.reult_index < 0 or self.result_index >= len(results):
            return{'CANCELLED'}
        item = results[self.result_index]
        obj = bpy.data.objects.get(item.objects_name)

        if not obj:
            self.report({"WARNING"}, "Object not found")
            return {'CANCELLED'}
        bpy.ops.object.mode_set(mode="OBJECT") if context.object else None
        for o in context.scene.objects:
            o.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj)
        return {'FINISHED'}

class TSV_OT_select_problem_elemets(bpy.types.Operator):
    bl_idname = "tsv.select_problem_elements"
    bl_label = "Select Problem Elements"
    bl_description = "Select the elements with the problem"

    result_index: bpy.props.IntProperty()

    def execute(self, context):
        results = context.scene.tsv_results

        if self.result_index < 0 or self.result_index >= len(results):
            return {'CANCELLED'}
        item = results[self.result_index]
        obj = bpy.data.objects.get(item.objects_name)

        if not obj or obj.type != 'MESH':
            self.report({"WARNING"}, "Object not found")
            return {'CANCELLED'}
        if not item.element_indices:
            self.report({"WARNING"}, "This problem has no element indices")
            return {'CANCELLED'}

        indices = [int(i) for i in item.element_indices.split(",") if i.strip() and i.isdigit()]

        bpy.ops.object.mode_set(mode="OBJECT") if context.object else None
        for o in context.scene.objects:
            o.select_set(False)

        obj.select_set(True)
        context.view_layer.objects.active = obj
        mesh = obj.data

        for v in mesh.vertices:
            v.select = False
        for e in mash.edges:
            e.select = False
        for p in mesh.polygons:
            p.select = False
        if item.element_type =="VERT":
            for index in indices:
                if index < len(mesh.vertices):
                    mesh.vertices[index].select = True
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_mode(action='VERT')

        elif item.element_type == "EDGE":
            for index in indices:
                if index < len(mesh.edges):
                    mesh.edges[index].select = True
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_mode(action='EDGE')

        elif item.element_type == "FACE":
            for index in indices:
                if index < len(mesh.polygons):
                    mesh.polygons[index].select = True
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_mode(action='FACE')
        else:
            self.report({"WARNING"}, "Invalid element type")
            return {'CANCELLED'}

classes = (
    TSV_OT_select_problem_elemets,
    TSV_OT_clear_results,
    TSV_OT_run_validation,
    TSV_OT_select_problem_object,
)
def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
