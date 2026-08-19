import bpy


# -----------------------------------------------------------------------------
# Shared properties / addon preferences
# -----------------------------------------------------------------------------


POPUP_KEY_ITEMS = [
    (chr(code), chr(code), f"Use {chr(code)} as popup hotkey")
    for code in range(ord('A'), ord('Z') + 1)
]

addon_keymaps = []


def get_addon_preferences(context=None):
    context = context or bpy.context
    preferences = getattr(context, "preferences", None)
    if not preferences:
        return None
    return preferences.addons.get(__package__).preferences if __package__ in preferences.addons else None


def get_exchange_path(context=None):
    prefs = get_addon_preferences(context)
    if prefs and prefs.exchange_path:
        return bpy.path.abspath(prefs.exchange_path)
    return bpy.path.abspath("//TSG_Exchange/")


def unregister_popup_keymap():
    wm = getattr(bpy.context, "window_manager", None)
    if not wm or not wm.keyconfigs or not wm.keyconfigs.addon:
        addon_keymaps.clear()
        return

    for km, kmi in addon_keymaps:
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    addon_keymaps.clear()


def register_popup_keymap():
    unregister_popup_keymap()

    wm = getattr(bpy.context, "window_manager", None)
    if not wm or not wm.keyconfigs or not wm.keyconfigs.addon:
        return

    prefs = get_addon_preferences()
    key_type = prefs.popup_key if prefs else 'Q'
    shift = prefs.popup_shift if prefs else True
    ctrl = prefs.popup_ctrl if prefs else False
    alt = prefs.popup_alt if prefs else False

    km = wm.keyconfigs.addon.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new(
        "tsg.show_popup",
        type=key_type,
        value='PRESS',
        shift=shift,
        ctrl=ctrl,
        alt=alt,
    )
    addon_keymaps.append((km, kmi))


def _update_popup_keymap(self, context):
    register_popup_keymap()


def uv_map_items(self, context):
    """Build a UV map selector from currently selected mesh objects."""
    names = set()
    if context:
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                names.update(uv.name for uv in obj.data.uv_layers)

    if not names:
        return [("", "No UV Maps", "No UV maps found on selected mesh objects")]

    return [(name, name, "") for name in sorted(names)]


class TSG_ProjectItem(bpy.types.PropertyGroup):
    project_id: bpy.props.StringProperty(name="Project ID")
    name: bpy.props.StringProperty(name="Project Name")
    folder_path: bpy.props.StringProperty(name="Folder Path", subtype='DIR_PATH')
    status: bpy.props.EnumProperty(
        name="Status",
        items=(
            ('ACTIVE', "Active", "Active project"),
            ('ARCHIVED', "Archived", "Archived project"),
        ),
        default='ACTIVE',
    )
    pinned: bpy.props.BoolProperty(name="Pinned", default=False)


class TSG_ValidationResult(bpy.types.PropertyGroup):
    category: bpy.props.StringProperty(name="Category")
    problem_type: bpy.props.StringProperty(name="Problem Type")
    object_name: bpy.props.StringProperty(name="Object Name")
    description: bpy.props.StringProperty(name="Description")
    element_type: bpy.props.EnumProperty(
        name="Element Type",
        items=(
            ('NONE', "None", "No mesh element selection"),
            ('VERT', "Vertex", "Vertex indices"),
            ('EDGE', "Edge", "Edge indices"),
            ('FACE', "Face", "Face indices"),
        ),
        default='NONE',
    )
    element_indices: bpy.props.StringProperty(name="Element Indices")


class TSG_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    exchange_path: bpy.props.StringProperty(
        name="Exchange Folder",
        description="Folder used by the Blender/Maya exchange bridge",
        subtype='DIR_PATH',
        default="//TSG_Exchange/",
    )
    popup_key: bpy.props.EnumProperty(
        name="Popup Key",
        description="Keyboard key that opens the TSG popup",
        items=POPUP_KEY_ITEMS,
        default='Q',
        update=_update_popup_keymap,
    )
    popup_shift: bpy.props.BoolProperty(
        name="Shift",
        default=True,
        update=_update_popup_keymap,
    )
    popup_ctrl: bpy.props.BoolProperty(
        name="Ctrl",
        default=False,
        update=_update_popup_keymap,
    )
    popup_alt: bpy.props.BoolProperty(
        name="Alt",
        default=False,
        update=_update_popup_keymap,
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="Bridge")
        layout.prop(self, "exchange_path")

        layout.separator()
        layout.label(text="Popup Hotkey")
        row = layout.row(align=True)
        row.prop(self, "popup_ctrl", toggle=True)
        row.prop(self, "popup_shift", toggle=True)
        row.prop(self, "popup_alt", toggle=True)
        row.prop(self, "popup_key", text="Key")
        layout.label(text="Default: Shift + Q", icon='EVENT_SHIFT')


CLASSES = (
    TSG_ProjectItem,
    TSG_ValidationResult,
    TSG_AddonPreferences,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)

    # UV manager
    bpy.types.Scene.tsg_uv_map_selector = bpy.props.EnumProperty(
        name="UV Maps",
        description="UV map found on selected mesh objects",
        items=uv_map_items,
    )
    bpy.types.Scene.tsg_uv_map_name = bpy.props.StringProperty(
        name="UV Map Name",
        default="map1",
    )

    # Project manager
    bpy.types.Scene.tsg_projects = bpy.props.CollectionProperty(type=TSG_ProjectItem)
    bpy.types.Scene.tsg_project_index = bpy.props.IntProperty(default=0)
    bpy.types.Scene.tsg_show_archived = bpy.props.BoolProperty(
        name="Show Archived",
        default=False,
    )

    # Validator
    bpy.types.Scene.tsg_validation_results = bpy.props.CollectionProperty(
        type=TSG_ValidationResult
    )
    bpy.types.Scene.tsg_validation_index = bpy.props.IntProperty(default=0)


def unregister():
    for name in (
        "tsg_validation_index",
        "tsg_validation_results",
        "tsg_show_archived",
        "tsg_project_index",
        "tsg_projects",

        "tsg_uv_map_name",
        "tsg_uv_map_selector",
    ):
        if hasattr(bpy.types.Scene, name):
            delattr(bpy.types.Scene, name)

    unregister_popup_keymap()

    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
