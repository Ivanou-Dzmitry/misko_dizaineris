import json
import re
from pathlib import Path

import bmesh
import bpy
from bpy.props import BoolProperty, StringProperty

from . import generator
from .operators import STAMP_PART, STAMP_TYPE, apply_settings, selected_roots

_presets = None     # name -> settings of the saved presets, read from the disk when first needed


def safe_name(name):
    """A name that is fine as a file name; letters of any language stay."""
    return re.sub(r"[^\w.\- ]+", "_", name).strip(" .") or "tree"


def get_prefs(context):
    addon = context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


def export_folder(context, override=""):
    prefs = get_prefs(context)
    raw = override or (prefs.export_dir if prefs else "")
    return Path(bpy.path.abspath(raw)) if raw else Path.home() / "MiskoDizaineris"


def presets_dir(create=False):
    """The folder of the saved presets: in the extension's user folder, or in the config folder when the
    add-on is not installed as an extension."""
    try:
        return Path(bpy.utils.extension_path_user(__package__, path="presets", create=create))
    except (ValueError, RuntimeError, AttributeError):
        return Path(bpy.utils.user_resource('CONFIG', path="MiskoDizaineris_presets", create=create))


def load_presets(refresh=False):
    global _presets
    if _presets is None or refresh:
        _presets = {}
        folder = presets_dir()
        for path in sorted(folder.glob("*.json")) if folder.is_dir() else ():
            try:
                data = json.loads(path.read_text("utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and isinstance(data.get("settings"), dict):
                _presets[str(data.get("name", path.stem))] = data["settings"]
    return _presets


def current_settings(context):
    props = context.scene.forest_props
    return {key: getattr(props, key) for key in generator.PARAM_KEYS}


def trees_to_export(context):
    """The selected trees; when none is selected, every tree of the scene."""
    return selected_roots(context) or [o for o in context.scene.objects if STAMP_TYPE in o]


def merge_wood(root):
    """A temporary object, a child of the tree, with the trunk and the branches in one mesh (the UV, the smoothing and the
    material are kept). None when the tree has no such pair. The caller removes it (remove_temp) after the export."""
    parts = {child.get(STAMP_PART): child for child in root.children}
    trunk, branches = parts.get('trunk'), parts.get('branches')
    if trunk is None or branches is None:
        return None
    bm = bmesh.new()
    bm.from_mesh(trunk.data)
    bm.from_mesh(branches.data)                 # added to the same bmesh: the UV layer of the same name is shared
    mesh = bpy.data.meshes.new(root.name + "_wood")
    bm.to_mesh(mesh)
    bm.free()
    for material in trunk.data.materials:
        mesh.materials.append(material)
    obj = bpy.data.objects.new(root.name + "_wood", mesh)
    obj.parent = root
    for collection in (trunk.users_collection or root.users_collection):
        collection.objects.link(obj)
    return obj


def remove_temp(obj):
    mesh = obj.data
    bpy.data.objects.remove(obj)
    bpy.data.meshes.remove(mesh)


class FOREST_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    export_dir: StringProperty(
        name="Export Folder",
        description="Where Export FBX puts the files",
        subtype='DIR_PATH',
        default=str(Path.home() / "MiskoDizaineris"),
    )

    def draw(self, context):
        self.layout.prop(self, "export_dir")


class FOREST_OT_export_fbx(bpy.types.Operator):
    bl_idname = "forest.export_fbx"
    bl_label = "Export FBX"
    bl_description = ("Save the selected trees (all of them when nothing is selected) as FBX: one file per tree, "
                      "or everything in one file. Every tree is exported at the world origin")
    bl_options = {'REGISTER'}

    directory: StringProperty(name="Folder", description="Export folder; empty uses the one from the add-on preferences",
                              subtype='DIR_PATH', default="")

    @classmethod
    def poll(cls, context):
        return any(STAMP_TYPE in o for o in context.scene.objects)

    def execute(self, context):
        props = context.scene.forest_props
        trees = trees_to_export(context)
        folder = export_folder(context, self.directory)
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            self.report({'ERROR'}, "Cannot create %s: %s" % (folder, error))
            return {'CANCELLED'}

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        active = context.view_layer.objects.active
        selection = list(context.selected_objects)
        batches = [([o], safe_name(o.name)) for o in trees] if props.export_separate else [(trees, safe_name(props.export_filename))]
        written = []
        try:
            for group, name in batches:
                saved = [(o, o.location.copy(), o.rotation_euler.copy()) for o in group]
                temps = []
                bpy.ops.object.select_all(action='DESELECT')
                for o in group:
                    o.select_set(True)
                    wood = merge_wood(o) if props.export_merge_wood else None
                    if wood is not None:
                        temps.append(wood)
                    for part in o.children:
                        if wood is not None and part.get(STAMP_PART) in ('trunk', 'branches'):
                            continue                # the merged mesh goes instead of the two
                        part.select_set(True)
                    if props.export_at_origin and props.export_separate:
                        o.location = (0.0, 0.0, 0.0)
                        o.rotation_euler = (0.0, 0.0, 0.0)
                context.view_layer.objects.active = group[0]
                context.view_layer.update()
                path = folder / (name + ".fbx")
                try:
                    # Unity-friendly: the scale and the axis conversion are baked into the mesh, so the object has rotation 0 and
                    # scale 1 in Unity (without this the importer adds a rotation of -90 and a scale of 100 to every tree).
                    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, object_types={'MESH', 'EMPTY'},
                                             add_leaf_bones=False, apply_scale_options='FBX_SCALE_ALL',
                                             bake_space_transform=True)
                finally:
                    for o, location, rotation in saved:
                        o.location, o.rotation_euler = location, rotation
                    for obj in temps:
                        remove_temp(obj)
                written.append(path)
        finally:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in selection:
                obj.select_set(True)
            context.view_layer.objects.active = active
            context.view_layer.update()
        self.report({'INFO'}, "Exported %d file(s) to %s" % (len(written), folder))
        return {'FINISHED'}


class FOREST_OT_open_export_folder(bpy.types.Operator):
    bl_idname = "forest.open_export_folder"
    bl_label = "Open Folder"
    bl_description = "Open the export folder in the file manager"

    def execute(self, context):
        folder = export_folder(context)
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            self.report({'ERROR'}, "Cannot create %s: %s" % (folder, error))
            return {'CANCELLED'}
        bpy.ops.wm.path_open(filepath=str(folder))
        return {'FINISHED'}


class FOREST_OT_open_presets_folder(bpy.types.Operator):
    bl_idname = "forest.open_presets_folder"
    bl_label = "Open Presets Folder"
    bl_description = ("Open the folder of the saved presets in the file manager. A preset is one JSON file: copy it to share it, "
                      "put one here to add it (then press Reload)")

    def execute(self, context):
        folder = presets_dir(create=True)
        bpy.ops.wm.path_open(filepath=str(folder))
        return {'FINISHED'}


class FOREST_OT_reload_presets(bpy.types.Operator):
    bl_idname = "forest.reload_presets"
    bl_label = "Reload Presets"
    bl_description = "Read the preset files from the folder again (after copying files into it)"

    def execute(self, context):
        self.report({'INFO'}, "%d preset(s)" % len(load_presets(refresh=True)))
        return {'FINISHED'}


class FOREST_OT_save_preset(bpy.types.Operator):
    bl_idname = "forest.save_preset"
    bl_label = "Save Preset"
    bl_description = "Save the settings of the panel (type, trunk, crown, branches, UV) under a name"

    name: StringProperty(name="Name", default="My Trees")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        name = self.name.strip()
        if not name:
            self.report({'ERROR'}, "Give the preset a name")
            return {'CANCELLED'}
        path = presets_dir(create=True) / (safe_name(name) + ".json")
        data = {"name": name, "version": generator.ADDON_VERSION, "settings": current_settings(context)}
        try:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
        except OSError as error:
            self.report({'ERROR'}, "Cannot save %s: %s" % (path, error))
            return {'CANCELLED'}
        load_presets(refresh=True)
        self.report({'INFO'}, "Saved preset %s" % name)
        return {'FINISHED'}


class FOREST_OT_load_preset(bpy.types.Operator):
    bl_idname = "forest.load_preset"
    bl_label = "Load Preset"
    bl_description = "Put the settings of this preset into the panel. Rebuild Selected applies them to the trees"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(name="Name")

    def execute(self, context):
        settings = load_presets().get(self.name)
        if settings is None:
            self.report({'ERROR'}, "No preset %s" % self.name)
            return {'CANCELLED'}
        apply_settings(context.scene.forest_props, settings)
        self.report({'INFO'}, "Loaded preset %s" % self.name)
        return {'FINISHED'}


class FOREST_OT_delete_preset(bpy.types.Operator):
    bl_idname = "forest.delete_preset"
    bl_label = "Delete Preset"
    bl_description = "Delete this saved preset"

    name: StringProperty(name="Name")

    def execute(self, context):
        path = presets_dir() / (safe_name(self.name) + ".json")
        try:
            path.unlink()
        except OSError as error:
            self.report({'ERROR'}, "Cannot delete %s: %s" % (path, error))
            return {'CANCELLED'}
        load_presets(refresh=True)
        return {'FINISHED'}


def draw_export(layout, context):
    header, body = layout.panel("FOREST_SECTION_export", default_closed=False)
    header.label(text="Export", icon='EXPORT')
    if body is None:
        return
    col = body.column(align=True)
    prefs = get_prefs(context)
    if prefs:
        col.prop(prefs, "export_dir", text="")
    row = col.row(align=True)
    row.operator(FOREST_OT_export_fbx.bl_idname, text="Export FBX", icon='EXPORT')
    row.operator(FOREST_OT_open_export_folder.bl_idname, text="Open Folder", icon='FILE_FOLDER')
    props = context.scene.forest_props
    col.prop(props, "export_merge_wood")
    col.prop(props, "export_separate")
    if props.export_separate:
        col.prop(props, "export_at_origin")
    else:
        col.prop(props, "export_filename")


def draw_presets(layout, context):
    header, body = layout.panel("FOREST_SECTION_presets", default_closed=False)
    header.label(text="Presets", icon='PRESET')
    if body is None:
        return
    col = body.column(align=True)
    row = col.row(align=True)
    row.operator(FOREST_OT_save_preset.bl_idname, text="Save Settings as Preset...", icon='ADD')
    row.operator(FOREST_OT_open_presets_folder.bl_idname, text="", icon='FILE_FOLDER')
    row.operator(FOREST_OT_reload_presets.bl_idname, text="", icon='FILE_REFRESH')
    for name in load_presets():
        row = col.row(align=True)
        row.operator(FOREST_OT_load_preset.bl_idname, text=name, icon='IMPORT').name = name
        row.operator(FOREST_OT_delete_preset.bl_idname, text="", icon='X').name = name


classes = (FOREST_Preferences, FOREST_OT_export_fbx, FOREST_OT_open_export_folder, FOREST_OT_open_presets_folder,
           FOREST_OT_reload_presets, FOREST_OT_save_preset,
           FOREST_OT_load_preset, FOREST_OT_delete_preset)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
