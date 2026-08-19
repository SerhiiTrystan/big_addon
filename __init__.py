bl_info = {
    "name": "TSG",
    "author": "TS, OpenAI",
    "version": (0, 2, 0),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > TSG",
    "description": "TSG tools: project manager, UV tools, bridge and validation",
    "category": "3D View",
}

from . import properties, operators, ui


def register():
    properties.register()
    operators.register()
    ui.register()


def unregister():
    ui.unregister()
    operators.unregister()
    properties.unregister()
