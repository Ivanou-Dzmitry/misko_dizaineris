import json

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty

from . import generator

STAMP_TYPE = "forest_type"          # custom property of a tree: which type it is
STAMP_PARAMS = "forest_params"      # ... and the settings it was made with, as JSON
STAMP_VERSION = "forest_version"    # ... and the add-on version that built it

STAMP_PART = "forest_part"          # custom property of a part of a tree: trunk, branches or leaves

_loading = False                    # True while settings are put into the panel: nothing is rebuilt and a type keeps the values


def tree_root(obj):
    """The tree an object belongs to: the empty that holds the stamps, or the parent of one of its parts."""
    if obj is None:
        return None
    if STAMP_TYPE in obj:
        return obj
    if obj.parent is not None and STAMP_TYPE in obj.parent:
        return obj.parent
    return None


def selected_roots(context):
    """The trees of the selection (a selected part counts for its tree) and of the active object."""
    roots = []
    for obj in list(getattr(context, "selected_objects", ())) + [getattr(context, "active_object", None)]:
        root = tree_root(obj)
        if root is not None and root not in roots:
            roots.append(root)
    return roots


def _rebuild_live(context):
    """Live update: rebuild the selected trees with the settings of the panel, at once."""
    props = context.scene.forest_props
    if _loading or not props.live or context.mode != 'OBJECT':
        return
    roots = selected_roots(context)
    if roots:
        params = settings(context.scene)
        for root in roots:
            build_tree(context, params, root)


def _on_changed(_self, context):
    _rebuild_live(context)


def _on_type_changed(self, context):
    """A new type puts its own settings into the panel (the seed, the randomness and the UV stay)."""
    global _loading
    if _loading:
        return
    _loading = True
    try:
        for key, value in generator.TYPE_PRESETS[self.tree_type].items():
            setattr(self, key, value)
    finally:
        _loading = False
    _rebuild_live(context)


def apply_settings(props, settings):
    """Put settings (a dict, maybe from an older version) into the panel, the type first and without its defaults."""
    global _loading
    _loading = True
    try:
        for key in ("tree_type",) + tuple(k for k in settings if k != "tree_type"):
            if key in settings and key in generator.PARAM_KEYS:
                try:
                    setattr(props, key, settings[key])
                except (AttributeError, TypeError, ValueError):
                    pass     # a setting that this version does not have, or a value out of range
    finally:
        _loading = False


D = generator.DEFAULTS


class ForestProps(bpy.types.PropertyGroup):
    tree_type: EnumProperty(name="Type", description="The kind of tree. Choosing one puts its settings into the panel; tune them after",
                            items=generator.TYPE_ITEMS, default=D["tree_type"], update=_on_type_changed)
    seed: IntProperty(name="Seed", description="Random seed: the lean of the trunk and the place, angle and length of every branch. "
                      "Written in the name: _s1", default=D["seed"], min=0, max=100000)
    randomness: FloatProperty(name="Randomness", description="How much the branches differ from the ideal pattern: angle, length, height, "
                              "thickness. 0 = every whorl is the same", default=D["randomness"], min=0.0, max=1.0)

    live: BoolProperty(name="Live Update", description="Rebuild the selected trees at once when a setting changes: drag a slider and watch. "
                       "Turn it off for a heavy tree and press Rebuild Selected", default=True)
    smooth: BoolProperty(name="Smooth Shading", description="Smooth shading on the trunk, the branches and the foliage. Off = faceted (flat)",
                         default=D["smooth"])

    height: FloatProperty(name="Height", description="Height of the tree, metres: from the ground (Z = 0) to the top of the trunk",
                          default=D["height"], min=0.3, max=60.0, unit='LENGTH')
    radius_base: FloatProperty(name="Width at Base", description="Radius of the trunk at the ground",
                               default=D["radius_base"], min=0.005, max=5.0, unit='LENGTH')
    radius_mid: FloatProperty(name="Width in Middle", description="Radius of the trunk at half the height",
                              default=D["radius_mid"], min=0.005, max=5.0, unit='LENGTH')
    radius_top: FloatProperty(name="Width at End", description="Radius of the trunk at the top (0 = the trunk ends in a point)",
                              default=D["radius_top"], min=0.0, max=5.0, unit='LENGTH')
    trunk_sides: IntProperty(name="Trunk Sides", description="Sides of the trunk", default=D["trunk_sides"], min=3, max=16)
    trunk_segments: IntProperty(name="Trunk Segments", description="Rings along the trunk (rounded up to an even number, so that "
                                "the ring in the middle has Width in Middle)", default=D["trunk_segments"], min=2, max=24)
    trunk_bend: FloatProperty(name="Bend", description="How far the top of the trunk leans to one side, metres",
                              default=D["trunk_bend"], min=0.0, max=10.0, unit='LENGTH')
    trunk_wobble: FloatProperty(name="Wobble", description="Random shift of every ring of the trunk, metres",
                                default=D["trunk_wobble"], min=0.0, max=2.0, unit='LENGTH')
    trunk_stubs: IntProperty(name="Stubs", description="Short stubs (the stumps of dead branches) along the bare trunk below the crown, like on a pine. "
                             "0 = none", default=D["trunk_stubs"], min=0, max=60)
    stub_start: FloatProperty(name="Stubs Start", description="Where the stubs begin, as a part of the bare trunk below the crown: 0 = from the "
                              "ground, 0.55 = from the middle of the bare part, 0.9 = only just below the first branches. They end at the first branches",
                              default=D["stub_start"], min=0.0, max=0.95, subtype='FACTOR')
    stub_length: FloatProperty(name="Stub Length", description="Length of the longest stubs, the ones nearest the crown; lower ones are shorter",
                               default=D["stub_length"], min=0.05, max=3.0, unit='LENGTH')
    trunk_sink: FloatProperty(name="Sink", description="How far the trunk goes below the ground, so that it stands on a slope. "
                              "0 = it starts at Z = 0", default=D["trunk_sink"], min=0.0, max=2.0, unit='LENGTH')
    trunk_flare: FloatProperty(name="Flare", description="How much wider the foot of the trunk is than the trunk above it (roots), "
                               "as a part of the radius at the base", default=D["trunk_flare"], min=0.0, max=3.0)
    bottom_cap: BoolProperty(name="Bottom Cap", description="Close the bottom of the trunk", default=D["bottom_cap"])

    branch_start: FloatProperty(name="1: Crown Bottom", description="Level 1: where the lowest branches grow, a part of the height "
                                "(below it the trunk is bare)", default=D["branch_start"], min=0.0, max=0.98, subtype='FACTOR')
    crown_mid: FloatProperty(name="2: Widest Place", description="Level 2: where the crown is the widest, a part of the crown "
                             "(0 = at the bottom, like a spruce; 1 = at the top)", default=D["crown_mid"], min=0.0, max=1.0,
                             subtype='FACTOR')
    branch_end: FloatProperty(name="3: Crown Top", description="Level 3: where the highest branches grow, a part of the height",
                              default=D["branch_end"], min=0.01, max=1.0, subtype='FACTOR')
    crown_radius_bottom: FloatProperty(name="Radius 1", description="How far the branches reach from the trunk at the bottom of the crown",
                                       default=D["crown_radius_bottom"], min=0.0, max=30.0, unit='LENGTH')
    crown_radius_mid: FloatProperty(name="Radius 2", description="How far the branches reach at the widest place",
                                    default=D["crown_radius_mid"], min=0.0, max=30.0, unit='LENGTH')
    crown_radius_top: FloatProperty(name="Radius 3", description="How far the branches reach at the top of the crown",
                                    default=D["crown_radius_top"], min=0.0, max=30.0, unit='LENGTH')
    crown_round: FloatProperty(name="Roundness", description="The outline between the levels: 0 = straight lines (a cone), "
                               "1 = an ellipse (a ball)", default=D["crown_round"], min=0.0, max=1.0, subtype='FACTOR')

    branch_levels: IntProperty(name="Levels", description="Rows of branches along the crown, from the bottom to the top",
                               default=D["branch_levels"], min=0, max=60)
    branches_per_level: IntProperty(name="Per Level", description="Branches in a row. 1 = a spiral up the trunk (a broadleaf tree), "
                                    "4 - 6 = whorls (a spruce)", default=D["branches_per_level"], min=1, max=16)
    branch_spread: FloatProperty(name="Height Spread", description="The branches of a row do not leave the trunk at one height: the row is a "
                                 "baseline, every branch is a little above or below it, by up to this part of the distance between the rows. "
                                 "0 = all on the line", default=D["branch_spread"], min=0.0, max=1.5, subtype='FACTOR')
    branch_angle_bottom: FloatProperty(name="Angle Bottom", description="Angle of the lowest branches from the trunk (90 = horizontal)",
                                       default=D["branch_angle_bottom"], min=0.1, max=2.1, subtype='ANGLE')
    branch_angle_top: FloatProperty(name="Angle Top", description="Angle of the highest branches from the trunk. The angle changes "
                                    "evenly from the bottom to the top", default=D["branch_angle_top"], min=0.1, max=2.1,
                                    subtype='ANGLE')
    branch_droop: FloatProperty(name="Droop", description="How much a branch bends down, as a part of its length. Negative = the "
                                "branches curl up. A willow has 1 or more", default=D["branch_droop"], min=-1.0, max=2.0)
    branch_radius: FloatProperty(name="Thickness", description="Radius of a branch where it leaves the trunk, as a part of the radius of the trunk "
                                 "at that height. A branch is always thinner than the trunk, and thinner the more of them leave in a row", default=D["branch_radius"], min=0.02, max=1.0, subtype='FACTOR')
    branch_tip: FloatProperty(name="Tip Thickness", description="Radius of a branch at its end, as a part of the radius at the trunk. The end is cut flat "
                              "(a square, not a pyramid). 0 = a point", default=D["branch_tip"], min=0.0, max=1.0, subtype='FACTOR')
    branch_collar: FloatProperty(name="Collar", description="Where a branch leaves the trunk (or a fork leaves its branch) it is wider, by up to this much, and narrows "
                                 "to its own thickness over twice the thickness of the trunk, like the collar of a real branch: the join is less "
                                 "visible. 0 = a plain tube", default=D["branch_collar"], min=0.0, max=1.5, subtype='FACTOR')
    branch_sides: IntProperty(name="Branch Sides", description="Sides of a branch (3 = a triangle, the cheapest)",
                              default=D["branch_sides"], min=3, max=12)
    branch_segments: IntProperty(name="Branch Segments", description="Pieces of a branch along its length (more = a smoother bend)",
                                 default=D["branch_segments"], min=1, max=8)

    branch_wiggle: FloatProperty(name="Wiggle", description="How crooked the branches are: every branch curves to one side and has a kink "
                                 "at every inner ring (needs Branch Segments of 3 or more to kink). 0 = straight",
                                 default=D["branch_wiggle"], min=0.0, max=2.0)
    branch_forks: IntProperty(name="Forks", description="Forks on the biggest branches: smaller branches that leave it in a Y, shorter the nearer the tip. With Pairs the number of pairs. 0 = plain sticks",
                              default=D["branch_forks"], min=0, max=8)
    fork_fade: FloatProperty(name="Fork Fade", description="The smaller the branch, the less detail. A branch is small where the crown radius "
                             "is small (the bottom and the top edge, Radius 1 and 3): it gets fewer forks, fewer generations, fewer sides and "
                             "segments. 0 = every branch has the same, 1 = in proportion to the crown radius there",
                             default=D["fork_fade"], min=0.0, max=1.0, subtype='FACTOR')
    fork_top_skip: IntProperty(name="Fork Top Skip", description="The top rows of branches have no forks at all (and simpler branches): "
                               "a tidy top of the crown", default=D["fork_top_skip"], min=0, max=8)
    fork_pattern: EnumProperty(name="Pattern", description="How the forks sit on a branch: Alternate = one at a time, one side then the other "
                               "(broadleaf); Pairs = two opposite forks at every place, sideways and forward, a herringbone like a spruce "
                               "twig (then Forks is the number of pairs)", items=generator.FORK_PATTERN_ITEMS, default=D["fork_pattern"])
    fork_lift: FloatProperty(name="Fork Lift", description="How far a fork goes up from the plane of its branch: 0 = sideways in the plane of the branch (flat), "
                             "0.2 = a little up, 1 = straight up. The angle to the branch is Fork Angle either way", default=D["fork_lift"],
                             min=0.0, max=1.0, subtype='FACTOR')
    fork_levels: IntProperty(name="Fork Levels", description="Generations of forks: forks that fork again. 1 = forks on branches, "
                             "3 = a bare winter tree. The number of branches grows fast", default=D["fork_levels"], min=0, max=4)
    fork_start: FloatProperty(name="Fork Start", description="Where the first fork leaves the branch, a part of its length "
                              "(the rest are spread to the tip)", default=D["fork_start"], min=0.05, max=0.9, subtype='FACTOR')
    fork_angle: FloatProperty(name="Fork Angle", description="Angle between a fork and the branch it leaves",
                              default=D["fork_angle"], min=0.1, max=1.6, subtype='ANGLE')
    fork_length: FloatProperty(name="Fork Length", description="Length of a fork, as a part of the length of its branch",
                               default=D["fork_length"], min=0.05, max=1.0, subtype='FACTOR')
    fork_radius: FloatProperty(name="Fork Thickness", description="Radius of a fork where it leaves, as a part of the radius of the branch there",
                               default=D["fork_radius"], min=0.05, max=1.0, subtype='FACTOR')

    foliage: EnumProperty(name="Foliage", description="The leaves: a low-poly clump at the end of every branch and fork, a flat skirt "
                          "along every branch (conifers), Tiers (skirts stacked up the trunk, instead of branches), or none (bare). Material FT_Leaf",
                          items=generator.FOLIAGE_ITEMS, default=D["foliage"])
    leaf_size: FloatProperty(name="Leaf Size", description="Radius of a clump (the width of a skirt), metres",
                             default=D["leaf_size"], min=0.02, max=10.0, unit='LENGTH')
    leaf_flat: FloatProperty(name="Leaf Height", description="Height of a clump compared to its width: below 1 = flat, "
                             "above 1 = long (hanging strands of a willow, an oval crown of a poplar)",
                             default=D["leaf_flat"], min=0.1, max=4.0)
    leaf_detail: IntProperty(name="Leaf Detail", description="Subdivisions of a clump: 1 = 20 triangles, 2 = 80, 3 = 320",
                             default=D["leaf_detail"], min=1, max=3)
    leaf_merge: FloatProperty(name="Merge Leaves", description="What is not seen is not made: a clump whose centre is on the spot of another or that sits mostly inside "
                              "one is dropped, and so are the faces that are inside another ball of the foliage (a puff inside its clump). "
                              "Fewer triangles, the look is the same. 0 = keep everything",
                              default=D["leaf_merge"], min=0.0, max=1.5, subtype='FACTOR')
    leaf_lobes: IntProperty(name="Puffs", description="Small puffs on the surface of every clump of leaves, so that it looks fluffy like a cloud "
                            "and not like a ball (each one is a small ball, 20 triangles at Leaf Detail 2). 0 = a plain ball. Not for needle skirts",
                            default=D["leaf_lobes"], min=0, max=8)
    leaf_spread: FloatProperty(name="Spread", description="Clumps of leaves are scattered: each sits somewhere near the end of its branch and is "
                               "thrown to a side by up to this part of its size. 0 = all on the tips (tight, overlapping)",
                               default=D["leaf_spread"], min=0.0, max=2.0, subtype='FACTOR')
    tier_lobes: IntProperty(name="Tier Lobes", description="Tiers: the lobes of the hem of a skirt (wide, with cuts between them)", default=D["tier_lobes"], min=3, max=24)
    tier_bend: FloatProperty(name="Tier Bend", description="Tiers: the skirt is bent along the lobes: steep near the trunk, flatter towards the hem "
                             "(0 = a straight cone, 1 = a clear bend)", default=D["tier_bend"], min=0.0, max=2.0)
    tier_gap: FloatProperty(name="Tier Cut Width", description="Tiers: how wide the cut between two lobes is at the hem, as a part of the step between "
                            "the lobes; the cut narrows to a point towards the trunk (0.05 = a slit, 0.5 = a wide wedge)", default=D["tier_gap"], min=0.05, max=0.8, subtype='FACTOR')
    tier_height: FloatProperty(name="Tier Height", description="Tiers: how tall a skirt is, as a part of its radius (the tiers overlap)",
                               default=D["tier_height"], min=0.1, max=2.0)
    tier_thickness: FloatProperty(name="Tier Thickness", description="Tiers: a rim along the hem of every skirt, this thick (like Solidify with "
                                  "Only Rim and no bottom): a chunky tier, nothing under it. 0 = a thin skirt", default=D["tier_thickness"],
                                  min=0.0, max=2.0, unit='LENGTH')
    tier_chamfer: FloatProperty(name="Tier Chamfer", description="Tiers: the end of the rim is a slope, not a box: the lower edge of the rim is drawn in under "
                                "the lobe by this much (in thicknesses). 0 = a vertical rim (a box), 1 = a clear wedge", default=D["tier_chamfer"],
                                min=0.0, max=2.0)
    tier_layers: IntProperty(name="Tier Layers", description="Tiers: 1 = one skirt, 2-3 = a smaller skirt inside, hanging lower, like "
                             "a second layer (more triangles)", default=D["tier_layers"], min=1, max=3)
    tier_notch: FloatProperty(name="Tier Notch", description="Tiers: how deep the cuts between the lobes are. The radius of the bottom of a cut "
                              "as a part of the radius of a lobe: 0.7 = deep, 0.95 = shallow", default=D["tier_notch"],
                              min=0.3, max=0.95, subtype='FACTOR')
    bush_shape: EnumProperty(name="Bush Shape", description="Bush Blob: the shape of the bush", items=generator.BUSH_SHAPE_ITEMS, default=D["bush_shape"])
    bush_width: FloatProperty(name="Bush Width", description="Bush Blob: the width of the bush (across), metres", default=D["bush_width"], min=0.2, max=30.0,
                              unit='LENGTH')
    bush_length: FloatProperty(name="Bush Length", description="Bush Blob: the length of the bush (along), metres. A different value from the width "
                               "makes it oval or a long hedge", default=D["bush_length"], min=0.2, max=30.0, unit='LENGTH')
    bush_blobs: IntProperty(name="Bush Blobs", description="Bush Blob, Ball shape: how many round blobs the bush is made of: the biggest and tallest in "
                            "the middle, the others round it, smaller and lower. 1 = one ball (a cloud with puffs if Bush Cloud is on)", default=D["bush_blobs"],
                            min=1, max=4)
    bush_rough: FloatProperty(name="Bush Rough", description="Bush Blob: how uneven the surface is (every point is pushed in or out): 0 = smooth shape, "
                              "1 = spiky", default=D["bush_rough"], min=0.0, max=1.0, subtype='FACTOR')
    bush_lift: FloatProperty(name="Bush Lift", description="Bush Blob: the bottom of the blob is this high above the ground (with Bush Stems: "
                             "a bush on stems)", default=D["bush_lift"], min=0.0, max=3.0, unit='LENGTH')
    bush_stems: IntProperty(name="Bush Stems", description="Bush Blob: thin stems from the ground up into the blob (best with Bush Lift)",
                            default=D["bush_stems"], min=0, max=16)
    bush_stem_lean: FloatProperty(name="Stem Lean", description="Bush Stems: the angle of the stems from the vertical: 0 = straight up (90 degrees to the ground), "
                                  "plus = they lean out, like a fan, minus = in, towards the centre. Every stem is a little different",
                                  default=D["bush_stem_lean"], min=-1.2, max=1.2, subtype='ANGLE')
    bush_cloud: BoolProperty(name="Bush Cloud", description="Bush Blob, Ball shape: the crown is a cloud, a ball with puffs on it (bumps, the lower side "
                             "ones hang lower). Off: one plain rough ball. Only for Bush Blobs = 1: with 2 or more blobs they are always shown", default=D["bush_cloud"])
    bush_stem_radius: FloatProperty(name="Roots Radius", description="Bush Stems: the feet of the stems are at random places in a circle of this "
                                    "radius round the centre of the bush (0 = all from one point)", default=D["bush_stem_radius"], min=0.0, max=4.0,
                                    unit='LENGTH')
    leaf_variation: FloatProperty(name="Size Variation", description="Every clump is up to this part bigger or smaller than its place in the crown "
                                  "says (0.3 = 30%). 0 = all of one size", default=D["leaf_variation"], min=0.0, max=0.9, subtype='FACTOR')
    leaf_taper: FloatProperty(name="Size Falloff", description="The biggest clumps are in the middle of the crown, at its widest place; "
                              "the higher up and the narrower the crown there, the smaller the clump. 0 = the same size everywhere",
                              default=D["leaf_taper"], min=0.0, max=1.0, subtype='FACTOR')
    export_merge_wood: BoolProperty(name="Merge Trunk and Branches", description="Export: the trunk and the branches go into the file as one mesh "
                                    "(they have one material and one UV atlas), the foliage as another: two meshes, two materials. The scene "
                                    "is not changed", default=True)
    export_separate: BoolProperty(name="Separate Files", description="Export: one FBX file per tree. Off: all the trees in one file",
                                  default=True)
    export_at_origin: BoolProperty(name="At Origin", description="Export: every tree at the world origin with no rotation, "
                                   "whatever its place in the scene", default=True)
    export_filename: StringProperty(name="File Name", description="Export: name of the file when Separate Files is off",
                                    default="trees")
    uv_bake: BoolProperty(name="Unique UV (Bake)", description="For baking (AO, normals): nothing overlaps. Every island has a place of its own and every "
                          "ball of the foliage is unwrapped into its own island. Off: for a tiling texture: similar islands lie on each other "
                          "(Overlap Similar) and all clumps share one leaf square (a bake would mix them)", default=D["uv_bake"])
    uv_straight: BoolProperty(name="Straight Strips", description="Every strip of a trunk or a branch is as wide along its whole length (a rectangle): "
                              "they pack without dead corners. The texture stretches where the tube is thin. Off: the strip follows the shape (a trapezoid)",
                              default=D["uv_straight"])
    uv_cut: IntProperty(name="Cut Trunk", description="Cut the UV of a tall trunk across into this many pieces (a very tall island limits the scale "
                        "of the whole tile). 0 = as many as needed, 1 = do not cut", default=D["uv_cut"], min=0, max=8)
    uv_similar: FloatProperty(name="Overlap Similar", description="Put UV islands of a similar size on top of each other to save space: "
                              "the width and the height differ by no more than this part (0.2 = 20%). Only islands of one group stack "
                              "(trunk, branches, foliage). 0 = only equal ones", default=D["uv_similar"], min=0.0, max=0.9,
                              subtype='FACTOR')
    uv_margin: FloatProperty(name="UV Margin", description="Gap between the places of the islands, a part of the tile",
                             default=D["uv_margin"], min=0.0, max=0.05, precision=3)


for _key in generator.PARAM_KEYS:
    if _key != "tree_type":
        ForestProps.__annotations__[_key].keywords["update"] = _on_changed


def settings(scene):
    props = scene.forest_props
    return {key: getattr(props, key) for key in generator.PARAM_KEYS}


def _stamp(obj, params):
    obj[STAMP_TYPE] = params["tree_type"]
    obj[STAMP_PARAMS] = json.dumps(params)
    obj[STAMP_VERSION] = generator.ADDON_VERSION


def build_tree(context, params, root=None, location=(0.0, 0.0, 0.0)):
    """Build a tree, or rebuild the one under `root`: an empty that holds the settings, and under it the parts as
    separate objects, each with its own mesh, material and UV: trunk, branches, leaves (none when there is no foliage)."""
    name = generator.tree_name(params)
    parts = generator.build_parts(params)
    if root is None:
        root = bpy.data.objects.new(name, None)
        root.empty_display_type = 'PLAIN_AXES'
        root.empty_display_size = 0.5
        root.location = location
        context.collection.objects.link(root)
    else:
        root.name = name
    collections = root.users_collection or (context.collection,)
    children = {child.get(STAMP_PART): child for child in root.children}
    for part in generator.PARTS:
        bm, child = parts[part], children.get(part)
        if bm is None:
            if child is not None:
                mesh = child.data
                bpy.data.objects.remove(child)
                bpy.data.meshes.remove(mesh)
            continue
        if child is None:
            mesh = bpy.data.meshes.new(f"{name}_{part}")
            child = bpy.data.objects.new(f"{name}_{part}", mesh)
            child[STAMP_PART] = part
            child.parent = root
            for collection in collections:
                collection.objects.link(child)
        else:
            mesh = child.data
            child.name = f"{name}_{part}"
            mesh.name = f"{name}_{part}"
        generator.fill_mesh(mesh, bm, part)
    _stamp(root, params)
    return root


def make_tree(context, params, location=(0.0, 0.0, 0.0)):
    return build_tree(context, params, None, location)


def _select_only(context, roots):
    """Select the trees with their parts; the last tree is the active object."""
    for o in context.selected_objects:
        o.select_set(False)
    for root in roots:
        root.select_set(True)
        for child in root.children:
            child.select_set(True)
    if roots:
        context.view_layer.objects.active = roots[-1]


def _object_mode():
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')


def _tri_count(roots):
    return sum(sum(len(poly.vertices) - 2 for poly in child.data.polygons) for root in roots for child in root.children)


def _place_row(context, entries, origin, gap):
    """Create trees in a row along +X from `origin`; each takes room by the width of its crown."""
    objs, x = [], 0.0
    for index, params in enumerate(entries):
        half = generator.footprint(params)
        x += half if index == 0 else gap + half
        objs.append(make_tree(context, params, (origin[0] + x, origin[1], origin[2])))
        x += half
    return objs


class FOREST_OT_add_tree(bpy.types.Operator):
    bl_idname = "forest.add_tree"
    bl_label = "Add Tree"
    bl_description = "Add a tree at the 3D cursor (the settings of the MiskoDizaineris panel)"
    bl_options = {'REGISTER', 'UNDO'}

    tree_type: StringProperty(name="Type", description="Take the settings of this type first (it also goes into the panel). "
                              "Empty = the panel as it is", default="", options={'SKIP_SAVE'})

    def execute(self, context):
        _object_mode()
        props = context.scene.forest_props
        if self.tree_type in generator.TYPE_PRESETS:
            props.tree_type = self.tree_type
        obj = make_tree(context, settings(context.scene), context.scene.cursor.location)
        _select_only(context, [obj])
        self.report({'INFO'}, f"{obj.name}: {_tri_count([obj])} tris")
        return {'FINISHED'}


class FOREST_OT_add_types(bpy.types.Operator):
    bl_idname = "forest.add_types"
    bl_label = "Add All Types (Preview)"
    bl_description = ("Add one tree of every type in a row from the 3D cursor to compare them (the seed, the randomness and the "
                      "UV settings of the panel; the rest of every type is its own)")
    bl_options = {'REGISTER', 'UNDO'}

    gap: FloatProperty(name="Gap", default=2.0, min=0.0, unit='LENGTH')

    def execute(self, context):
        _object_mode()
        params = settings(context.scene)
        entries = [generator.with_type(params, kind) for kind, _label, _desc in generator.TYPE_ITEMS]
        objs = _place_row(context, entries, context.scene.cursor.location, self.gap)
        _select_only(context, objs)
        self.report({'INFO'}, f"{len(objs)} trees, {_tri_count(objs)} tris")
        return {'FINISHED'}


class FOREST_OT_add_variants(bpy.types.Operator):
    bl_idname = "forest.add_variants"
    bl_label = "Add Variants"
    bl_description = "Add several trees of the current type in a row from the 3D cursor, each with its own seed (Seed, Seed + 1, ...)"
    bl_options = {'REGISTER', 'UNDO'}

    count: IntProperty(name="Count", default=5, min=1, max=50)
    gap: FloatProperty(name="Gap", default=1.0, min=0.0, unit='LENGTH')

    def execute(self, context):
        _object_mode()
        params = settings(context.scene)
        entries = [dict(params, seed=params["seed"] + i) for i in range(self.count)]
        objs = _place_row(context, entries, context.scene.cursor.location, self.gap)
        _select_only(context, objs)
        self.report({'INFO'}, f"{len(objs)} trees, {_tri_count(objs)} tris")
        return {'FINISHED'}


class FOREST_OT_rebuild(bpy.types.Operator):
    bl_idname = "forest.rebuild"
    bl_label = "Rebuild Selected"
    bl_description = "Rebuild the selected trees with the current panel settings (with Live Update this happens by itself)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(selected_roots(context))

    def execute(self, context):
        _object_mode()
        params = settings(context.scene)
        roots = selected_roots(context)
        for root in roots:
            build_tree(context, params, root)
        self.report({'INFO'}, f"Rebuilt {len(roots)}")
        return {'FINISHED'}


class FOREST_OT_pick(bpy.types.Operator):
    bl_idname = "forest.pick_settings"
    bl_label = "Get Settings from Active"
    bl_description = "Put the settings the active tree was made with into the panel (then change them: with Live Update the tree follows)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return tree_root(context.active_object) is not None

    def execute(self, context):
        try:
            data = json.loads(tree_root(context.active_object)[STAMP_PARAMS])
        except ValueError:
            self.report({'ERROR'}, "The settings of this tree are not readable")
            return {'CANCELLED'}
        apply_settings(context.scene.forest_props, data)
        return {'FINISHED'}


classes = (ForestProps, FOREST_OT_add_tree, FOREST_OT_add_types, FOREST_OT_add_variants, FOREST_OT_rebuild, FOREST_OT_pick)


def _menu_add(self, context):
    self.layout.menu("FOREST_MT_add")


class FOREST_MT_add(bpy.types.Menu):
    bl_idname = "FOREST_MT_add"
    bl_label = "Tree"

    def draw(self, context):
        for kind, label, _desc in generator.TYPE_ITEMS:
            self.layout.operator(FOREST_OT_add_tree.bl_idname, text=label).tree_type = kind


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.utils.register_class(FOREST_MT_add)
    bpy.types.Scene.forest_props = PointerProperty(type=ForestProps)
    bpy.types.VIEW3D_MT_mesh_add.append(_menu_add)


def unregister():
    bpy.types.VIEW3D_MT_mesh_add.remove(_menu_add)
    del bpy.types.Scene.forest_props
    bpy.utils.unregister_class(FOREST_MT_add)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
