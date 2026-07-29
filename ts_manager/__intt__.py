import bpy
bl_info = {
    "name": "Simple Project Manager",
    "author": "TSG",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > N-Panel > Projects",
    "description": "Simple JSON-based Blender project manager",
    "category": "System",
}

import bpy

from .properties import register_properties, unregister_properties
from .operators import classes as operator_classes
from .ui_panels import classes as panel_classes


classes = (
    *operator_classes,
    *panel_classes,
)


def register():
    register_properties()

    for cls in classes:
        bpy.utils.register_class(cls)

    # Автоматически читаем JSON при запуске аддона
    bpy.ops.spm.reload_projects()


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    unregister_properties()
