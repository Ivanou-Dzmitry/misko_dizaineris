import bpy

from . import exporter, generator
from .operators import FOREST_OT_add_tree, FOREST_OT_add_types, FOREST_OT_add_variants, FOREST_OT_pick, FOREST_OT_rebuild, ForestProps

_ICONS = {
    'SPRUCE': 'OUTLINER_OB_FORCE_FIELD', 'PINE': 'TRIA_UP', 'POPLAR': 'TRIA_UP_BAR', 'LINDEN': 'MESH_UVSPHERE',
    'WILLOW': 'IPO_EASE_OUT', 'BIRCH': 'IPO_LINEAR', 'BUSH': 'MESH_ICOSPHERE', 'BARE': 'CURVE_BEZCURVE',
}

# The settings, in sections (every setting of ForestProps is in one; the rest goes to "Other").
_SETTINGS = (
    ("FOREST_SET_tree", "Tree", False, ("seed", "randomness", "smooth")),
    ("FOREST_SET_trunk", "Trunk", False,
     ("height", "radius_base", "radius_mid", "radius_top", "trunk_sides", "trunk_segments", "trunk_bend", "trunk_wobble",
      "trunk_flare", "trunk_stubs", "stub_start", "stub_length", "trunk_sink", "bottom_cap")),
    ("FOREST_SET_crown", "Crown (3 Levels)", False,
     ("branch_start", "crown_radius_bottom", "crown_mid", "crown_radius_mid", "branch_end", "crown_radius_top", "crown_round")),
    ("FOREST_SET_branches", "Branches", False,
     ("branch_levels", "branches_per_level", "branch_spread", "branch_angle_bottom", "branch_angle_top", "branch_droop", "branch_radius",
      "branch_wiggle", "branch_collar", "branch_tip", "branch_sides", "branch_segments")),
    ("FOREST_SET_forks", "Forks (Branches of Branches)", False,
     ("branch_forks", "fork_pattern", "fork_levels", "fork_fade", "fork_top_skip", "fork_start", "fork_angle", "fork_lift", "fork_length", "fork_radius")),
    ("FOREST_SET_foliage", "Foliage", False, ("foliage", "bush_shape", "bush_width", "bush_length", "bush_blobs", "bush_rough", "bush_lift", "bush_stems", "bush_stem_radius", "bush_stem_lean", "bush_cloud", "tier_lobes", "tier_gap", "tier_bend", "tier_height", "tier_thickness", "tier_chamfer", "tier_layers", "tier_notch", "leaf_size", "leaf_lobes", "leaf_spread", "leaf_variation", "leaf_taper", "leaf_flat", "leaf_detail", "leaf_merge")),
)
_UV_PROPS = ("uv_bake", "uv_straight", "uv_cut", "uv_similar", "uv_margin")
_NOT_SHOWN_HERE = ("tree_type", "live", "export_merge_wood", "export_separate", "export_at_origin", "export_filename")      # drawn elsewhere


def other_settings():
    placed = {name for _id, _title, _closed, names in _SETTINGS for name in names} | set(_UV_PROPS) | set(_NOT_SHOWN_HERE)
    return [name for name in ForestProps.__annotations__ if name not in placed]


def _section(layout, idname, title, closed):
    header, body = layout.panel(idname, default_closed=closed)
    header.label(text=title)
    return body


class FOREST_PT_main(bpy.types.Panel):
    bl_label = "MiskoDizaineris"
    bl_idname = "FOREST_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MiskoDizaineris"

    def draw_header(self, context):
        self.layout.label(text=f"v{generator.ADDON_VERSION}")

    def draw(self, context):
        layout = self.layout
        props = context.scene.forest_props

        # the type: a button per type adds that tree (at the 3D cursor) and puts its settings into the panel
        header, body = layout.panel("FOREST_SECTION_types", default_closed=False)
        header.label(text="Add Tree (at the 3D Cursor)", icon='OUTLINER_OB_FORCE_FIELD')
        if body is not None:
            grid = body.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
            for kind, label, _desc in generator.TYPE_ITEMS:
                op = grid.operator(FOREST_OT_add_tree.bl_idname, text=label, icon=_ICONS.get(kind, 'MESH_DATA'),
                                   depress=props.tree_type == kind)
                op.tree_type = kind

        col = layout.column(align=True)
        col.scale_y = 1.3
        col.operator(FOREST_OT_add_tree.bl_idname, text=f"Add {props.bl_rna.properties['tree_type'].enum_items[props.tree_type].name}",
                     icon='ADD')
        row = col.row(align=True)
        row.scale_y = 0.8
        row.operator(FOREST_OT_add_variants.bl_idname, icon='DUPLICATE')
        row.operator(FOREST_OT_add_types.bl_idname, text="All Types", icon='GRID')
        row = col.row(align=True)
        row.scale_y = 0.8
        row.operator(FOREST_OT_rebuild.bl_idname, icon='FILE_REFRESH')
        row.operator(FOREST_OT_pick.bl_idname, text="Get Settings", icon='EYEDROPPER')
        exporter.draw_export(layout, context)

        # the settings, in sections
        header, body = layout.panel("FOREST_SECTION_settings", default_closed=False)
        header.label(text="Settings", icon='PREFERENCES')
        if body is not None:
            body.prop(props, "live", icon='TIME')
            body.prop(props, "tree_type")
            for idname, title, closed, names in _SETTINGS:
                section = _section(body, idname, title, closed)
                if section is not None:
                    col = section.column(align=True)
                    for name in names:
                        col.prop(props, name)
            section = _section(body, "FOREST_SET_uv", "UV", True)
            if section is not None:
                section.prop(props, "uv_bake")
                section.prop(props, "uv_straight")
                section.prop(props, "uv_cut")
                col = section.column()
                col.active = not props.uv_bake
                col.prop(props, "uv_similar")
                section.prop(props, "uv_margin")
            rest = other_settings()
            if rest:
                section = _section(body, "FOREST_SET_other", "Other", True)
                if section is not None:
                    for name in rest:
                        section.prop(props, name)

        exporter.draw_presets(layout, context)


classes = (FOREST_PT_main,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
