import bpy

from . import ts_bridge, ts_mat, ts_scs, ts_uv, ts_validator, ui_main

bl_info = {
    "name": "TSG",
    "author": "TS, Chat GPT",
    "version": (0, 0, 1),
    "blender": (5, 0, 0),
    "category": "3D View",
}


modules = [ts_mat, ts_scs, ts_uv, ts_manager, ts_bridge, ui_main]


def register():
    for module in modules:
        module.register()


def unregister():
    for module in modules:
        module.unregister()
