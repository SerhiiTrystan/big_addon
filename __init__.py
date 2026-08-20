bl_info = {
    "name": "TSG",
    "author": "TS, OpenAI",
    "version": (0, 3, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > TSG",
    "description": "TSG tools plus TSG Mat material browser, tags and Cycles preview cache",
    "category": "3D View",
}

from . import properties, operators, ui, materials


def register():
    properties.register()
    operators.register()
    ui.register()
    materials.register()
    properties.register_popup_keymap()


def unregister():
    properties.unregister_popup_keymap()
    materials.unregister()
    ui.unregister()
    operators.unregister()
    properties.unregister()
