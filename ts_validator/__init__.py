import bpy

from . import operators, properties

modules = [operators, properties]


def register():
    for module in modules:
        module.register()


def unregister():
    for module in modules:
        module.unregister()
