bl_info = {
    "name": "TSG",
    "author": "TS, OpenAI",
    "version": (0, 2, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > TSG",
    "description": "TSG tools: project manager, UV tools, bridge and validation",
    "category": "3D View",
}

from . import properties, operators, ui


def register():
    properties.register()
    operators.register()
    ui.register()
    properties.register_popup_keymap()


def unregister():
    properties.unregister_popup_keymap()
    ui.unregister()
    operators.unregister()
    properties.unregister()
