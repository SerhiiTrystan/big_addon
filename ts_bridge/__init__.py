
import bpy
from . import operators
class ExchangeProperty(bpy.types.PropertyGroup):
    tsg_path: bpy.props.StringProperty(
        name="Exchange Folder",
        description="DIR_PATH",
        default="D:/Exchange",
    )

def register():
    bpy.utils.register_class(ExchangeProperty)
    bpy.types.Scene.tsg_props = bpy.props.PointerProperty(type=ExchangeProperty)
    for cls in  (
        operators.
        operators.
        operators.
        operators.
    )

def unregister():
    bpy.utils.unregister_class(ExchangeProperty)
