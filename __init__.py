import bpy

<<<<<<< HEAD
from . import ts_manager, ts_mat, ts_scs, ts_uv, ui_main
=======
from . import ts_bridge, ts_mat, ts_scs, ts_uv, ui_main
>>>>>>> 48e54a33cbe275d8789c36cac2f9a782ed05253f

bl_info = {
    "name": "TSG",
    "author": "TS, Chat GPT",
    "version": (0, 0, 1),
    "blender": (5, 0, 0),
    "category": "3D View",
}


<<<<<<< HEAD
modules = [ts_mat, ts_scs, ts_uv, ts_manager, ui_main]
=======
modules = [ts_mat, ts_scs, ts_uv, ts_bridge, ui_main]
>>>>>>> 48e54a33cbe275d8789c36cac2f9a782ed05253f


def register():
    for module in modules:
        module.register()


def unregister():
    for module in modules:
        module.unregister()
