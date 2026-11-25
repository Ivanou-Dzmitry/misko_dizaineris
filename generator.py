"""Low-poly trees: a bent trunk, branches that bend and branch, and foliage.

A tree stands at the origin, the ground is Z = 0, the trunk grows along +Z.

The crown is drawn as a silhouette with three levels:

    3  top of the crown        (branch_end,  radius crown_radius_top)
    2  the widest place        (crown_mid,   radius crown_radius_mid)
    1  bottom of the crown     (branch_start, radius crown_radius_bottom)

Every branch grows from the trunk at some height and reaches the silhouette at that height, so a round crown
(linden, willow) and a cone (spruce) are the same thing with different radii. `crown_round` blends from straight
lines (0) to an ellipse (1) between the levels.

Nothing is a straight pipe: the trunk wanders from ring to ring (`trunk_wobble`) and leans (`trunk_bend`); a branch
curves to one side and has a kink at every inner ring (`branch_wiggle`). A branch forks: smaller branches leave it in
a Y, and they fork again (`fork_levels` generations). Foliage (`foliage`) is a low-poly clump at the end of every
branch, or a flat skirt along it (conifers).

Trunk and branches are tubes of a few sides. Every tube is unwrapped as a strip (one island each); the islands are
laid out either at one texel size (tiled bark) or packed into 0..1 with one scale (to paint or to bake). The foliage
of the whole tree shares one square island, to the right of them.
"""

import math
import random
import tomllib
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


def _read_version():
    try:
        with open(Path(__file__).with_name("blender_manifest.toml"), "rb") as f:
            return tomllib.load(f)["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return ""


ADDON_VERSION = _read_version()     # the single source of the version is blender_manifest.toml

MATERIALS = (
    ("FT_Bark", (0.30, 0.20, 0.12, 1.0)),       # the trunk and the branches: one material (one texture, one UV atlas)
    ("FT_Leaf", (0.30, 0.52, 0.16, 1.0)),       # the foliage: clumps of leaves or needles
)

TYPE_ITEMS = [
    ('SPRUCE', "Spruce", "Spruce (ель): a straight trunk, a dense cone of drooping branches that starts low"),
    ('PINE', "Pine", "Pine (сосна): a tall bent trunk and a small crown on top"),
    ('POPLAR', "Poplar", "Poplar (тополь): tall, a narrow oval crown, branches go steeply up"),
    ('LINDEN', "Linden", "Linden (липа): a short trunk and a wide round crown"),
    ('WILLOW', "Willow", "Willow (ива): a thick trunk, a wide crown, long branches that hang down"),
    ('BIRCH', "Birch", "Birch (берёза): thin and bent, an oval crown"),
    ('BUSH', "Bush", "Bush (куст): no trunk, thin branches fan out from the ground"),
    ('BARE', "Bare Tree", "A tree without leaves (winter, dead): a flared, twisting trunk and bent limbs that fork again and again"),
]

FORK_PATTERN_ITEMS = [
    ('ALTERNATE', "Alternate", "One fork at a time, one side and then the other, mostly up and out (broadleaf trees)"),
    ('PAIRS', "Pairs", "Two opposite forks at every place, sideways and forward, longest at the base and shorter to the tip, "
                       "with a Y at the end: a herringbone like a spruce twig"),
]

BUSH_SHAPE_ITEMS = [
    ('SPHERE', "Ball", "A round bush (stretch it with Bush Length for a long one)"),
    ('BOX', "Box", "A rounded box: a hedge (stretch it with Bush Length for a long hedge)"),
    ('EGG', "Egg", "An egg: round at the bottom, narrower at the top (a thuja, a cypress)"),
]

FOLIAGE_ITEMS = [
    ('NONE', "None", "No foliage: the bare trunk and branches (winter)"),
    ('CLUMPS', "Clumps", "A low-poly clump of leaves at the end of every branch and fork (broadleaf trees, bushes)"),
    ('SHEATH', "Sheath", "A flat skirt of needles along every branch (spruce)"),
    ('BUSH', "Bush Blob", "A bush as one faceted blob: a ball, a box (a hedge), an egg, long or short (Bush Shape, Bush Length). No branches"),
    ('TIERS', "Tiers", "Instead of branches: tiers, skirts with a toothed hem stacked up the trunk, a classic low-poly spruce (few triangles)"),
]

# the settings that do not depend on the type
COMMON = {
    "tree_type": 'SPRUCE',
    "seed": 1,
    "randomness": 0.3,
    "trunk_sink": 0.26,
    "bottom_cap": False,
    "branch_collar": 0.35,
    "fork_lift": 0.3,
    "leaf_merge": 0.5,
    "smooth": True,
    "leaf_variation": 0.3,
    "leaf_lobes": 3,
    "leaf_taper": 0.35,
    "leaf_spread": 0.7,
    "bush_shape": 'SPHERE',
    "bush_width": 1.8,
    "bush_length": 1.8,
    "bush_blobs": 3,
    "bush_rough": 0.5,
    "bush_stem_radius": 0.4,
    "bush_stem_lean": math.radians(15.0),
    "bush_cloud": True,
    "stub_start": 0.55,
    "tier_lobes": 8,
    "tier_gap": 0.1795,
    "tier_bend": 0.29,
    "tier_thickness": 0.21,
    "tier_chamfer": 0.44,
    "tier_height": 0.91,
    "tier_layers": 1,
    "tier_notch": 0.6526,
    "uv_bake": True,
    "uv_straight": True,
    "uv_cut": 0,
    "uv_similar": 0.2,
    "uv_margin": 0.005,
}

# the settings of a type (angles in degrees here, radians in the settings)
_PRESETS_DEG = {
    'SPRUCE': dict(height=10.0, radius_base=0.33, radius_mid=0.16, radius_top=0.03, trunk_sides=8, trunk_segments=8,
                   trunk_bend=0.28, trunk_wobble=0.0, trunk_flare=0.57, trunk_stubs=0, stub_length=0.28, bush_lift=0.61, bush_stems=0, branch_spread=0.5842, branch_tip=0.3737,
                   branch_start=0.0064, branch_end=0.97, crown_mid=0.0, crown_radius_bottom=0.0, crown_radius_mid=3.17,
                   crown_radius_top=0.19, crown_round=0.0,
                   branch_levels=9, branches_per_level=6, branch_angle_bottom=85.87, branch_angle_top=61.41, branch_droop=-0.99,
                   branch_radius=0.3526, branch_sides=5, branch_segments=8, branch_wiggle=2.0,
                   branch_forks=3, fork_levels=1, fork_fade=1.0, fork_pattern='PAIRS', fork_top_skip=2, fork_start=0.2275, fork_angle=50.0, fork_length=0.5246, fork_radius=0.5508,
                   foliage='TIERS', leaf_size=0.73, leaf_flat=1.6, leaf_detail=1),
    'PINE': dict(height=14.0, radius_base=0.30, radius_mid=0.22, radius_top=0.10, trunk_sides=6, trunk_segments=6,
                 trunk_bend=1.00, trunk_wobble=0.18, trunk_flare=0.30, trunk_stubs=10, stub_length=0.5, bush_lift=0.0, bush_stems=0, branch_spread=0.5, branch_tip=0.1404,
                 branch_start=0.56, branch_end=1.0, crown_mid=0.45, crown_radius_bottom=2.2, crown_radius_mid=3.8,
                 crown_radius_top=1.4, crown_round=1.0,
                 branch_levels=6, branches_per_level=2, branch_angle_bottom=80, branch_angle_top=50, branch_droop=-0.15,
                 branch_radius=0.50, branch_sides=4, branch_segments=3, branch_wiggle=0.30,
                 branch_forks=2, fork_levels=1, fork_fade=1.0, fork_pattern='ALTERNATE', fork_top_skip=2, fork_start=0.45, fork_angle=50, fork_length=0.40, fork_radius=0.6,
                 foliage='CLUMPS', leaf_size=1.25, leaf_flat=0.38, leaf_detail=1),
    'POPLAR': dict(height=15.0, radius_base=0.35, radius_mid=0.22, radius_top=0.06, trunk_sides=7, trunk_segments=4,
                   trunk_bend=0.30, trunk_wobble=0.08, trunk_flare=0.25, trunk_stubs=0, stub_length=0.4, bush_lift=0.0, bush_stems=0, branch_spread=0.5, branch_tip=0.1404,
                   branch_start=0.15, branch_end=0.98, crown_mid=0.35, crown_radius_bottom=0.4, crown_radius_mid=1.7,
                   crown_radius_top=0.1, crown_round=0.8,
                   branch_levels=12, branches_per_level=3, branch_angle_bottom=40, branch_angle_top=22, branch_droop=-0.05,
                   branch_radius=0.45, branch_sides=3, branch_segments=2, branch_wiggle=0.15,
                   branch_forks=1, fork_levels=1, fork_fade=1.0, fork_pattern='ALTERNATE', fork_top_skip=2, fork_start=0.55, fork_angle=35, fork_length=0.35, fork_radius=0.6,
                   foliage='CLUMPS', leaf_size=0.95, leaf_flat=1.2, leaf_detail=1),
    'LINDEN': dict(height=7.98, radius_base=0.4, radius_mid=0.16, radius_top=0.08, trunk_sides=8, trunk_segments=12,
                   trunk_bend=0.29, trunk_wobble=0.25, trunk_flare=0.28, trunk_stubs=0, stub_length=0.4, bush_lift=0.0, bush_stems=0, branch_spread=0.5, branch_tip=0.1404,
                   branch_start=0.2504, branch_end=0.98, crown_mid=0.45, crown_radius_bottom=9.12, crown_radius_mid=3.02,
                   crown_radius_top=1.62, crown_round=1.0,
                   branch_levels=6, branches_per_level=3, branch_angle_bottom=78.3, branch_angle_top=36.1, branch_droop=-0.05,
                   branch_radius=0.4388, branch_sides=5, branch_segments=8, branch_wiggle=0.27,
                   branch_forks=2, fork_levels=2, fork_fade=1.0, fork_pattern='ALTERNATE', fork_top_skip=3, fork_start=0.3749, fork_angle=54.3, fork_length=0.66, fork_radius=0.9257,
                   foliage='CLUMPS', leaf_size=1.34, leaf_flat=0.91, leaf_detail=2),
    'WILLOW': dict(height=9.0, radius_base=0.45, radius_mid=0.32, radius_top=0.14, trunk_sides=6, trunk_segments=4,
                   trunk_bend=0.80, trunk_wobble=0.20, trunk_flare=0.40, trunk_stubs=0, stub_length=0.4, bush_lift=0.0, bush_stems=0, branch_spread=0.5, branch_tip=0.1404,
                   branch_start=0.30, branch_end=0.95, crown_mid=0.50, crown_radius_bottom=2.0, crown_radius_mid=3.8,
                   crown_radius_top=1.6, crown_round=1.0,
                   branch_levels=8, branches_per_level=4, branch_angle_bottom=40, branch_angle_top=25, branch_droop=1.10,
                   branch_radius=0.40, branch_sides=3, branch_segments=4, branch_wiggle=0.25,
                   branch_forks=2, fork_levels=1, fork_fade=1.0, fork_pattern='ALTERNATE', fork_top_skip=2, fork_start=0.35, fork_angle=40, fork_length=0.40, fork_radius=0.55,
                   foliage='CLUMPS', leaf_size=0.50, leaf_flat=2.40, leaf_detail=1),
    'BIRCH': dict(height=12.0, radius_base=0.14, radius_mid=0.10, radius_top=0.04, trunk_sides=5, trunk_segments=6,
                  trunk_bend=0.90, trunk_wobble=0.12, trunk_flare=0.15, trunk_stubs=6, stub_length=0.3, bush_lift=0.0, bush_stems=0, branch_spread=0.5, branch_tip=0.1404,
                  branch_start=0.30, branch_end=0.98, crown_mid=0.40, crown_radius_bottom=0.6, crown_radius_mid=1.6,
                  crown_radius_top=0.4, crown_round=0.8,
                  branch_levels=9, branches_per_level=3, branch_angle_bottom=45, branch_angle_top=28, branch_droop=0.25,
                  branch_radius=0.55, branch_sides=3, branch_segments=3, branch_wiggle=0.30,
                  branch_forks=1, fork_levels=1, fork_fade=1.0, fork_pattern='ALTERNATE', fork_top_skip=2, fork_start=0.40, fork_angle=40, fork_length=0.40, fork_radius=0.6,
                  foliage='CLUMPS', leaf_size=0.8, leaf_flat=1.1, leaf_detail=1),
    'BUSH': dict(height=1.6, radius_base=0.05, radius_mid=0.04, radius_top=0.03, trunk_sides=5, trunk_segments=2,
                 trunk_bend=0.10, trunk_wobble=0.03, trunk_flare=0.0, trunk_stubs=0, stub_length=0.4, bush_lift=0.45, bush_stems=4, branch_spread=0.5, branch_tip=0.1404,
                 branch_start=0.05, branch_end=1.0, crown_mid=0.50, crown_radius_bottom=0.5, crown_radius_mid=0.9,
                 crown_radius_top=0.3, crown_round=1.0,
                 branch_levels=4, branches_per_level=5, branch_angle_bottom=55, branch_angle_top=25, branch_droop=0.20,
                 branch_radius=0.80, branch_sides=3, branch_segments=2, branch_wiggle=0.35,
                 branch_forks=1, fork_levels=1, fork_fade=1.0, fork_pattern='ALTERNATE', fork_top_skip=2, fork_start=0.50, fork_angle=45, fork_length=0.45, fork_radius=0.7,
                 foliage='BUSH', leaf_size=0.42, leaf_flat=0.85, leaf_detail=2),
    'BARE': dict(height=8.0, radius_base=0.4, radius_mid=0.28, radius_top=0.04, trunk_sides=8, trunk_segments=8,
                 trunk_bend=1.03, trunk_wobble=0.28, trunk_flare=0.8, trunk_stubs=4, stub_length=0.19, bush_lift=0.0, bush_stems=0, branch_spread=0.2505, branch_tip=0.1879,
                 branch_start=0.3071, branch_end=0.98, crown_mid=0.5, crown_radius_bottom=6.0, crown_radius_mid=3.02,
                 crown_radius_top=2.01, crown_round=0.0,
                 branch_levels=4, branches_per_level=4, branch_angle_bottom=84.92, branch_angle_top=59.78, branch_droop=-0.07,
                 branch_radius=0.7, branch_sides=4, branch_segments=6, branch_wiggle=0.27,
                 branch_forks=3, fork_levels=2, fork_fade=0.3153, fork_pattern='ALTERNATE', fork_top_skip=1, fork_start=0.2411, fork_angle=46.66, fork_length=1.0, fork_radius=1.0,
                 foliage='NONE', leaf_size=0.80, leaf_flat=0.85, leaf_detail=1),
}
TYPE_PRESETS = {}
for _type, _preset in _PRESETS_DEG.items():
    _preset = dict(_preset)
    for _key in ("branch_angle_bottom", "branch_angle_top", "fork_angle"):
        _preset[_key] = math.radians(_preset[_key])
    TYPE_PRESETS[_type] = _preset

DEFAULTS = dict(COMMON, **TYPE_PRESETS[COMMON["tree_type"]])
PARAM_KEYS = tuple(DEFAULTS)
TYPE_KEYS = tuple(TYPE_PRESETS['SPRUCE'])       # the settings that a type sets

_EPS = 1e-5
_GOLDEN = math.pi * (3.0 - math.sqrt(5.0))      # 137.5 degrees: successive branches do not line up
_UP = Vector((0.0, 0.0, 1.0))


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def with_type(params, tree_type):
    """The settings of `params` with the settings of the type on top (the seed, the randomness and the UV stay)."""
    return dict(params, tree_type=tree_type, **TYPE_PRESETS[tree_type])


def resolve(p):
    """Clamp the raw settings into a consistent set of dimensions."""
    s = dict(p)
    s["height"] = max(float(p["height"]), 0.3)
    s["radius_base"] = max(float(p["radius_base"]), 0.005)
    s["radius_mid"] = max(float(p["radius_mid"]), 0.005)
    s["radius_top"] = max(float(p["radius_top"]), 0.0)
    s["trunk_sides"] = _clamp(int(p["trunk_sides"]), 3, 16)
    segments = _clamp(int(p["trunk_segments"]), 2, 24)
    s["trunk_segments"] = segments + segments % 2           # even: there is a ring at the middle, where radius_mid is
    s["trunk_sink"] = max(float(p["trunk_sink"]), 0.0)
    s["stub_start"] = _clamp(float(p["stub_start"]), 0.0, 0.95)
    s["trunk_stubs"] = _clamp(int(p["trunk_stubs"]), 0, 60)
    s["stub_length"] = _clamp(float(p["stub_length"]), 0.05, 3.0)
    s["trunk_flare"] = _clamp(float(p["trunk_flare"]), 0.0, 3.0)
    start = _clamp(float(p["branch_start"]), 0.0, 0.98)
    s["branch_start"] = start
    s["branch_end"] = _clamp(float(p["branch_end"]), start + 0.01, 1.0)
    s["crown_mid"] = _clamp(float(p["crown_mid"]), 0.0, 1.0)
    s["crown_round"] = _clamp(float(p["crown_round"]), 0.0, 1.0)
    s["branch_levels"] = max(int(p["branch_levels"]), 0)
    s["branches_per_level"] = max(int(p["branches_per_level"]), 1)
    s["branch_sides"] = _clamp(int(p["branch_sides"]), 3, 12)
    s["branch_segments"] = _clamp(int(p["branch_segments"]), 1, 8)
    s["branch_wiggle"] = _clamp(float(p["branch_wiggle"]), 0.0, 2.0)
    s["fork_lift"] = _clamp(float(p["fork_lift"]), 0.0, 1.0)
    s["branch_collar"] = _clamp(float(p["branch_collar"]), 0.0, 1.5)
    s["branch_tip"] = _clamp(float(p["branch_tip"]), 0.0, 1.0)
    s["branch_forks"] = _clamp(int(p["branch_forks"]), 0, 8)
    s["fork_fade"] = _clamp(float(p["fork_fade"]), 0.0, 1.0)
    s["fork_top_skip"] = _clamp(int(p["fork_top_skip"]), 0, 8)
    s["fork_levels"] = _clamp(int(p["fork_levels"]), 0, 4)
    s["fork_start"] = _clamp(float(p["fork_start"]), 0.05, 0.9)
    s["fork_length"] = _clamp(float(p["fork_length"]), 0.05, 1.0)
    s["fork_radius"] = _clamp(float(p["fork_radius"]), 0.05, 1.0)
    s["leaf_size"] = max(float(p["leaf_size"]), 0.02)
    s["leaf_flat"] = _clamp(float(p["leaf_flat"]), 0.1, 4.0)
    s["leaf_detail"] = _clamp(int(p["leaf_detail"]), 1, 3)
    s["randomness"] = _clamp(float(p["randomness"]), 0.0, 1.0)
    s["smooth"] = bool(p["smooth"])
    s["branch_spread"] = _clamp(float(p["branch_spread"]), 0.0, 1.5)
    s["leaf_merge"] = _clamp(float(p["leaf_merge"]), 0.0, 1.5)
    s["branch_radius"] = _clamp(float(p["branch_radius"]), 0.02, 1.0)
    s["leaf_lobes"] = _clamp(int(p["leaf_lobes"]), 0, 8)
    s["leaf_variation"] = _clamp(float(p["leaf_variation"]), 0.0, 0.9)
    s["leaf_taper"] = _clamp(float(p["leaf_taper"]), 0.0, 1.0)
    s["tier_chamfer"] = _clamp(float(p["tier_chamfer"]), 0.0, 2.0)
    s["tier_thickness"] = _clamp(float(p["tier_thickness"]), 0.0, 2.0)
    s["tier_bend"] = _clamp(float(p["tier_bend"]), 0.0, 2.0)
    s["tier_gap"] = _clamp(float(p["tier_gap"]), 0.05, 0.8)
    s["tier_lobes"] = _clamp(int(p["tier_lobes"]), 3, 24)
    s["tier_height"] = _clamp(float(p["tier_height"]), 0.1, 2.0)
    s["tier_layers"] = _clamp(int(p["tier_layers"]), 1, 3)
    s["tier_notch"] = _clamp(float(p["tier_notch"]), 0.3, 0.95)
    s["bush_shape"] = p["bush_shape"] if p["bush_shape"] in ('SPHERE', 'BOX', 'EGG') else 'SPHERE'
    s["bush_width"] = _clamp(float(p["bush_width"]), 0.2, 30.0)
    s["bush_length"] = _clamp(float(p["bush_length"]), 0.2, 30.0)
    s["bush_blobs"] = _clamp(int(p["bush_blobs"]), 1, 4)
    s["bush_rough"] = _clamp(float(p["bush_rough"]), 0.0, 1.0)
    s["bush_lift"] = _clamp(float(p["bush_lift"]), 0.0, 3.0)
    s["bush_stems"] = _clamp(int(p["bush_stems"]), 0, 16)
    s["bush_stem_lean"] = _clamp(float(p["bush_stem_lean"]), -1.2, 1.2)
    s["bush_stem_radius"] = _clamp(float(p["bush_stem_radius"]), 0.0, 4.0)
    s["bush_cloud"] = bool(p["bush_cloud"])
    s["leaf_spread"] = _clamp(float(p["leaf_spread"]), 0.0, 2.0)
    s["uv_bake"] = bool(p["uv_bake"])
    s["uv_straight"] = bool(p["uv_straight"])
    s["uv_cut"] = _clamp(int(p["uv_cut"]), 0, 8)
    s["uv_similar"] = _clamp(float(p["uv_similar"]), 0.0, 0.9)
    s["uv_margin"] = _clamp(float(p["uv_margin"]), 0.0, 0.05)
    return s


def _num(x):
    return f"{x:g}".replace(".", "p").replace("-", "m")


def tree_name(p):
    """<type><height>_s<seed>: spruce10_s1, birch12_s4."""
    s = resolve(p)
    return f"{s['tree_type'].lower()}{_num(round(s['height'], 2))}_s{int(s['seed'])}"


def footprint(p):
    """Half the width of the tree, to put trees in a row."""
    s = resolve(p)
    if s["foliage"] == 'BUSH':
        return max(s["bush_width"], s["bush_length"], 0.6) / 2.0
    wide = max(s["crown_radius_bottom"], s["crown_radius_mid"], s["crown_radius_top"])
    return max(wide + (s["leaf_size"] * 0.6 if s["foliage"] != 'NONE' else 0.0), s["radius_base"] * 2.0, 0.3)


# --------------------------------------------------------------------------------------
# the silhouette and the trunk
# --------------------------------------------------------------------------------------

_FLARE_HEIGHT = 0.12        # the base of the trunk is wider up to this part of the height


def _trunk_radius(s, t):
    """The width of the trunk at a height t (0..1): base - middle - top, straight between them, wider at the foot."""
    if t <= 0.5:
        radius = s["radius_base"] + (s["radius_mid"] - s["radius_base"]) * (t / 0.5)
    else:
        radius = s["radius_mid"] + (s["radius_top"] - s["radius_mid"]) * ((t - 0.5) / 0.5)
    if s["trunk_flare"] > 0.0 and t < _FLARE_HEIGHT:
        radius *= 1.0 + s["trunk_flare"] * (1.0 - t / _FLARE_HEIGHT) ** 2
    return radius


def _crown_reach(s, c):
    """How far the crown reaches from the trunk at a place c of the crown (0 = bottom, 1 = top)."""
    r1, r2, r3 = s["crown_radius_bottom"], s["crown_radius_mid"], s["crown_radius_top"]
    mid, k = s["crown_mid"], s["crown_round"]
    if c <= mid and mid > 1e-6:
        x = c / mid
        a, b, eased = r1, r2, math.sin(x * math.pi / 2.0)        # fast at first, then flat: the round belly
    else:
        x = _clamp((c - mid) / max(1.0 - mid, 1e-6), 0.0, 1.0)
        a, b, eased = r2, r3, 1.0 - math.cos(x * math.pi / 2.0)  # flat at first, then falling: the round top
    return a + (b - a) * (x * (1.0 - k) + eased * k)


def _trunk_path(s, rng):
    """Rings of the trunk, (centre, radius): from Trunk Sink below the ground to the top. The trunk leans to one side
    and wanders: every ring steps a little to a random side from the one below, so the trunk curves and kinks."""
    height, n = s["height"], s["trunk_segments"]
    ups = {height * i / n for i in range(n + 1)}
    if s["trunk_flare"] > 0.0:
        ups.add(height * _FLARE_HEIGHT * 0.45)                  # a ring in the flare, so that it has a curve
    heights = ([-s["trunk_sink"]] if s["trunk_sink"] > 0.0 else []) + sorted(ups)
    angle = rng.uniform(0.0, 2.0 * math.pi)
    lean = Vector((math.cos(angle), math.sin(angle), 0.0))
    walk = Vector((0.0, 0.0, 0.0))
    path = []
    for z in heights:
        t = _clamp(z / height, 0.0, 1.0)
        if z > 1e-6:
            walk += Vector((rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0), 0.0)) * s["trunk_wobble"]
        path.append((lean * (s["trunk_bend"] * t * t) + walk + Vector((0.0, 0.0, z)), _trunk_radius(s, t)))
    return _bend_straight_rings(path, random.Random(int(s["seed"]) * 7919 + 13))


def _bend_straight_rings(path, rng, share=0.03):
    """Where a ring lies on (or almost on) the line between its two neighbours, the trunk is a dead straight pipe there. Move such
    a ring sideways by `share` of the length of its two segments: a small bend at every section. The rings that already bend more
    are not touched. A separate random generator, so that the branches do not change."""
    path = list(path)
    for i in range(1, len(path) - 1):
        (a, _ra), (p, rp), (b, _rb) = path[i - 1], path[i], path[i + 1]
        if p.z <= 1e-6 or b.z - a.z < 1e-6:
            continue
        mid = a.lerp(b, (p.z - a.z) / (b.z - a.z))
        off = Vector((p.x - mid.x, p.y - mid.y, 0.0))
        need = share * (b - a).length
        if off.length >= need:
            continue
        if off.length > 1e-6:
            direction = off.normalized()
        else:
            k = rng.uniform(0.0, 2.0 * math.pi)
            direction = Vector((math.cos(k), math.sin(k), 0.0))
        path[i] = (Vector((mid.x + direction.x * need, mid.y + direction.y * need, p.z)), rp)
    return path


def _trunk_at(path, z):
    """Centre and radius of the trunk at a height z."""
    for (c0, r0), (c1, r1) in zip(path, path[1:]):
        if c1.z >= z - _EPS:
            f = _clamp((z - c0.z) / max(c1.z - c0.z, _EPS), 0.0, 1.0)
            return c0.lerp(c1, f), r0 + (r1 - r0) * f
    return path[-1]


# --------------------------------------------------------------------------------------
# tubes and their UV islands
# --------------------------------------------------------------------------------------

def _tube(bm, islands, path, sides, ref, bottom_cap=False, straight=True, phase=0.5):
    """A tube along `path`, a list of (centre, radius). The last ring may have radius 0 (a point). The end is cut flat. `phase`: 0.5
    turns the rings half a step (flat sides on the ref side, a square is a square: the trunk), 0 puts a corner there (a square
    is a diamond: the branches, where a flat edge would show on the round trunk).
    The UV island is a strip: u round the tube, v along it, in metres; the seam is on the `ref` side. `straight`: the strip
    is as wide at every ring (a rectangle, the mean width), so the islands pack without dead corners; the texture is
    stretched where the tube is thin. Adds the island to `islands`: width, height, faces with their local UV, and for
    cutting the ring row of every face, the length along the tube at every ring and the width at every ring."""
    path = list(path)
    flat_end = path[-1][1] > _EPS               # the end is cut flat (a square, not a pyramid); a ring of radius 0 is a point
    count = len(path)
    centres = [c for c, _r in path]
    radii = [r for _c, r in path]
    point = [r <= _EPS for r in radii]          # a ring that is a single vertex

    tangents = []
    for i in range(count):
        t = centres[min(i + 1, count - 1)] - centres[max(i - 1, 0)]
        tangents.append(t.normalized() if t.length > 1e-9 else Vector((0.0, 0.0, 1.0)))

    rings, frames, normal = [], [], None
    for i in range(count):
        t = tangents[i]
        if normal is None:
            normal = ref - t * ref.dot(t)
            if normal.length < 1e-4:
                normal = Vector((1.0, 0.0, 0.0)) - t * t.x
        else:
            normal = normal - t * normal.dot(t)
        normal = normal.normalized()
        binormal = t.cross(normal)
        frames.append((normal, binormal))
        if point[i]:
            rings.append([bm.verts.new(centres[i])])
        else:
            ring = []
            for k in range(sides):
                a = 2.0 * math.pi * (k + phase) / sides     # phase 0.5 (the trunk): the seam is the middle of a face, on the ref side; 0 (branches): a point is on the ref side, a square is a diamond
                ring.append(bm.verts.new(centres[i] + (normal * math.cos(a) + binormal * math.sin(a)) * radii[i]))
            rings.append(ring)

    # along the surface (slant length), and the width of every ring
    along = [0.0]
    for i in range(1, count):
        along.append(along[-1] + math.hypot((centres[i] - centres[i - 1]).length, radii[i] - radii[i - 1]))
    chord = 2.0 * math.sin(math.pi / sides)
    perimeter = [sides * radii[i] * chord for i in range(count)]
    if straight:
        real = [p for p in perimeter if p > 0.0]
        widths = [max(sum(real) / max(len(real), 1), 0.01)] * count
    else:
        widths = [max(p, 0.0) for p in perimeter]
    width = max(max(widths), 0.01)

    def u(k, i):
        return width / 2.0 + (k / sides - 0.5) * widths[i] if not point[i] else width / 2.0

    faces, rows = [], []
    for i in range(count - 1):
        for k in range(sides):
            k2 = (k + 1) % sides
            if point[i + 1]:
                verts = [rings[i][k], rings[i][k2], rings[i + 1][0]]
                uvs = [(u(k, i), along[i]), (u(k + 1, i), along[i]), (u(k, i + 1), along[i + 1])]
            else:
                verts = [rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]]
                uvs = [(u(k, i), along[i]), (u(k + 1, i), along[i]), (u(k + 1, i + 1), along[i + 1]), (u(k, i + 1), along[i + 1])]
            faces.append((bm.faces.new(verts), uvs))
            rows.append(i)
    height = along[-1]
    if flat_end:
        r = radii[-1]
        cap = bm.faces.new(rings[-1])           # the order of the ring: the normal looks along the branch
        cap.tag = True                          # a flat face: no smooth shading
        normal, binormal = frames[-1]
        uvs = []
        for vert in cap.verts:
            d = vert.co - centres[-1]
            uvs.append((width / 2.0 + d.dot(normal), along[-1] + r + d.dot(binormal)))      # seen from the tip: right = normal, up = binormal
        faces.append((cap, uvs))
        rows.append(count - 2)
        height += 2.0 * r                       # the cap is on the strip, above its end
    islands.append({"w": width, "h": height, "faces": faces, "rows": rows, "along": along, "widths": widths})

    if bottom_cap and not point[0]:
        r = radii[0]
        face = bm.faces.new(list(reversed(rings[0])))
        face.tag = True
        normal, binormal = frames[0]
        uvs = []
        for vert in face.verts:
            d = vert.co - centres[0]
            uvs.append((r - d.dot(normal), r + d.dot(binormal)))        # seen from below, the right hand is -normal
        islands.append({"w": 2.0 * r, "h": 2.0 * r, "faces": [(face, uvs)]})


# --------------------------------------------------------------------------------------
# UV layout
# --------------------------------------------------------------------------------------

def _stack_groups(islands, tolerance):
    """Group islands of a similar size, like Stack Similar in TechArt Tools. An island joins the first group whose first
    island (the anchor, the tallest ones come first) has both the width and the height within `tolerance` (0.2 = 20%)
    of its own; otherwise it starts a new group. The islands of a group lie on each other. An island with "solo" stays
    alone. Returns lists of indices."""
    order = sorted(range(len(islands)), key=lambda n: -islands[n]["h"])
    groups, anchors = [], []
    for n in order:
        w, h = islands[n]["w"], islands[n]["h"]
        if islands[n].get("solo"):
            groups.append([n])
            anchors.append(None)
            continue
        for g, anchor in enumerate(anchors):
            if anchor is not None and abs(w - anchor[0]) <= max(w, anchor[0]) * tolerance and abs(h - anchor[1]) <= max(h, anchor[1]) * tolerance:
                groups[g].append(n)
                break
        else:
            groups.append([n])
            anchors.append((w, h))
    return groups


def _cut_island(island, pieces):
    """Cut a strip across, at the rings, into `pieces` pieces of about the same length (like Cut Height in ConstructionBuilder):
    a very tall island would limit the scale of the whole tile. Returns the pieces (the island itself when it is not cut)."""
    rows = island.get("rows")
    along = island.get("along")
    if pieces <= 1 or not rows or len(along) < 3:
        return [island]
    last = len(along) - 1
    cuts = sorted({min(range(1, last), key=lambda n: abs(along[n] - along[-1] * k / pieces)) for k in range(1, pieces)})
    result = []
    for r0, r1 in zip([0] + cuts, cuts + [last]):
        members = [(face, uvs) for (face, uvs), row in zip(island["faces"], rows) if r0 <= row < r1]
        if not members:
            continue
        width = max(island["widths"][r0:r1 + 1])
        shift, drop = (island["w"] - width) / 2.0, along[r0]
        moved = [(face, [(u - shift, v - drop) for u, v in uvs]) for face, uvs in members]
        result.append({"w": width, "h": max(v for _f, uvs in moved for _u, v in uvs), "faces": moved, "layer": island["layer"]})
    return result


def _skyline(rects, side, pad):
    """Pack rectangles into a square of the given side (no rotation): the tallest first, every one into the lowest place
    where it fits (a skyline). Returns the (x, y) of every rectangle, or None when they do not fit."""
    order = sorted(range(len(rects)), key=lambda n: (-rects[n]["h"], -rects[n]["w"]))
    line = [[0.0, 0.0, side]]                           # the skyline: [x, height, width] from the left, no gaps
    place = [None] * len(rects)
    for n in order:
        w, h = rects[n]["w"] + pad, rects[n]["h"] + pad
        if w > side + 1e-9 or h > side + 1e-9:
            return None
        best = None
        for first in range(len(line)):
            x = line[first][0]
            if x + w > side + 1e-9:
                break
            y, covered, k = 0.0, 0.0, first
            while covered < w - 1e-9 and k < len(line):
                y = max(y, line[k][1])
                covered += line[k][2]
                k += 1
            if covered < w - 1e-9 or y + h > side + 1e-9:
                continue
            if best is None or y < best[0] - 1e-9:
                best = (y, x)
        if best is None:
            return None
        y, x = best
        place[n] = (x, y)
        new = []
        for sx, sy, sw in line:
            if sx + sw <= x + 1e-12 or sx >= x + w - 1e-12:
                new.append([sx, sy, sw])
                continue
            if sx < x:
                new.append([sx, sy, x - sx])
            if sx + sw > x + w:
                new.append([x + w, sy, sx + sw - x - w])
        new.append([x, y + h, w])
        new.sort(key=lambda seg: seg[0])
        line = [new[0]]
        for seg in new[1:]:
            if abs(seg[1] - line[-1][1]) < 1e-9:
                line[-1][2] += seg[2]
            else:
                line.append(seg)
    return place


def _write_uv(parts, s):
    """One UV tile 0..1 for the whole tree. `parts` is a list of lists of islands: the trunk, the branches, the foliage.
    A tall trunk is cut into pieces (Cut Trunk; 0 = as many as needed to make the tile smaller). Islands of a similar size
    lie on each other (Overlap Similar) unless the UV is for baking (Unique UV): then nothing overlaps. The islands are
    packed in the smallest square (a skyline), one scale for all (the same density), not rotated, all inside 0..1."""
    bake = s["uv_bake"]

    def stacks_of(groups):
        stacks, rects = [], []
        for part in groups:
            for indices in ([[n] for n in range(len(part))] if bake else _stack_groups(part, s["uv_similar"])):
                members = [part[n] for n in indices]
                stacks.append(members)
                rects.append({"w": max(m["w"] for m in members), "h": max(m["h"] for m in members)})
        return stacks, rects

    stacks, rects = stacks_of(parts)
    pieces = s["uv_cut"]
    if pieces == 0 and parts[0]:
        wanted = math.sqrt(1.25 * sum(r["w"] * r["h"] for r in rects))       # the side of the tile if everything packed well
        pieces = min(6, max(1, math.ceil(max(isl["h"] for isl in parts[0]) / max(wanted, 1e-6) - 0.05)))
    if pieces > 1:
        cut = []
        for island in parts[0]:
            cut += _cut_island(island, pieces)
        parts = [cut] + list(parts[1:])
        stacks, rects = stacks_of(parts)
    total = sum(r["w"] * r["h"] for r in rects)
    floor = max(max(r["w"] for r in rects), max(r["h"] for r in rects), math.sqrt(total))
    side, place, pad = floor * 4.0, None, 0.0
    for factor in (1.03, 1.08, 1.14, 1.21, 1.3, 1.4, 1.55, 1.8, 2.2, 3.0, 4.0):
        side = floor * factor
        pad = s["uv_margin"] * side
        place = _skyline(rects, side, pad)
        if place is not None:
            break
    if place is None:                                   # cannot happen: 4 x the floor holds everything; one column, to be safe
        place, y = [], 0.0
        for r in rects:
            place.append((0.0, y))
            y += r["h"] + pad
        side = max(y, floor)
    scale = 1.0 / side
    for members, (x, y) in zip(stacks, place):
        for island in members:
            layer = island["layer"]
            for face, uvs in island["faces"]:
                for loop, (u, v) in zip(face.loops, uvs):
                    loop[layer].uv = ((x + pad / 2.0 + u) * scale, (y + pad / 2.0 + v) * scale)


# --------------------------------------------------------------------------------------
# branches and forks
# --------------------------------------------------------------------------------------

def _curve(s, rng, start, heading, length, base_r, droop, segments, collar=0.0, reach=0.0):
    """Rings of a branch, (centre, radius): along `heading`, sagging by `droop`, with a smooth arc to one side and a
    kink to a random side at every inner ring (Wiggle). The branch is not a straight pipe; a long one (over 1.4 m) always bends
    a little, even with Wiggle 0. `collar` (Branch Collar) and `reach` (the radius of the trunk or the branch it leaves): the
    base of the branch is wider, up to this part more at the trunk, and narrows to its own radius over twice the reach,
    like the collar of a real branch: the join does not show as a thin tube cut into a thick one. A ring is added at the
    place where the branch comes out of the trunk."""
    wiggle = s["branch_wiggle"]
    if length > 1.4:
        wiggle = max(wiggle, 0.12)
    side = heading.cross(_UP)
    side = side.normalized() if side.length > 1e-4 else Vector((1.0, 0.0, 0.0))
    up = side.cross(heading).normalized()
    roll = rng.uniform(0.0, 2.0 * math.pi)
    arc = (side * math.cos(roll) + up * math.sin(roll)) * (wiggle * length * rng.uniform(0.4, 1.0) * 0.5)
    us = [q / segments for q in range(segments + 1)]
    if collar > 0.0 and reach > 0.0:
        coming_out = _clamp(reach / max(length, 1e-6), 0.03, 0.45)
        if all(abs(coming_out - u) > 0.04 for u in us):
            us = sorted(us + [coming_out])
    path = []
    for n, u in enumerate(us):
        pos = start + heading * (length * u) + Vector((0.0, 0.0, -droop * length * u * u)) + arc * (u * u)
        if 0 < n < len(us) - 1 and u > 0.12:
            k = rng.uniform(0.0, 2.0 * math.pi)
            ramp = _clamp((u - 0.12) / 0.25, 0.0, 1.0)             # the kinks grow from the trunk: the base of a branch is straight, no steps at the junction
            pos += (side * math.cos(k) + up * math.sin(k)) * (wiggle * length * 0.2 * rng.uniform(0.3, 1.0) * ramp)
        swell = 1.0 + collar * _clamp(1.0 - u * length / (2.0 * reach), 0.0, 1.0) if collar > 0.0 and reach > 0.0 else 1.0
        if swell > 1.0:
            swell = min(swell, max(1.0, 0.9 * reach / base_r))     # the collar is not wider than the trunk: the first ring stays inside it
        path.append((pos, base_r * (1.0 - u * (1.0 - s["branch_tip"])) * swell))
    return path


def _fork_segments(s, length):
    """Segments of a fork by its length: a short one a few, a long one at least 3 (so that it can bend), not more than
    Branch Segments (or 3)."""
    n = max(2, round(length / 0.8))
    if length >= 1.4:
        n = max(n, 3)
    return int(_clamp(n, 1, max(s["branch_segments"], 3)))


def _fit(s, trunk, start, heading, length, droop):
    """Shorten a branch until its tip is inside the crown outline (and under Height). The tips then follow the
    outline, so the top of the crown is round, not a flat line of tips that were all cut at the same height."""
    height, first, last = s["height"], s["branch_start"], s["branch_end"]
    for _ in range(10):
        tip = start + heading * length + Vector((0.0, 0.0, -droop * length))
        c = (tip.z / height - first) / (last - first)           # where the tip is in the crown, 0 = bottom, 1 = top
        if c <= 0.0:
            return length                                       # below the crown (hanging branches): nothing to check
        axis, _radius = _trunk_at(trunk, min(tip.z, height))
        reach = _crown_reach(s, 1.0) if c > 1.0 else _crown_reach(s, c)
        if c <= 1.0 and math.hypot(tip.x - axis.x, tip.y - axis.y) <= reach * 1.05 + 0.15:
            return length
        length = max(length * 0.85, 0.12)
    return length


def _along(path, u):
    """Centre, radius and direction of a path at a part u (0..1) of its length (by rings)."""
    f = _clamp(u, 0.0, 1.0) * (len(path) - 1)
    i = min(int(f), len(path) - 2)
    (c0, r0), (c1, r1) = path[i], path[i + 1]
    return c0.lerp(c1, f - i), r0 + (r1 - r0) * (f - i), (c1 - c0).normalized()


def _fork_paths(s, rng, trunk, path, length):
    """The forks of one branch, as (path, length). Alternate: one fork at a time, one side and then the other, mostly up and
    out. Pairs: two opposite forks at every place, sideways and forward (a herringbone, like a spruce twig). Either way
    the nearer the tip, the shorter the fork: the first is the longest."""
    r = s["randomness"]
    count, first = s["branch_forks"], s["fork_start"]
    pairs = s["fork_pattern"] == 'PAIRS'
    side_sign = 1.0 if rng.random() < 0.5 else -1.0
    result = []
    for f in range(count):
        u = first + (min(first + 0.8 * (1.0 - first), 0.9) - first) * (f / (count - 1)) if count > 1 else first
        centre, radius, tangent = _along(path, u)
        side = tangent.cross(_UP)
        side = side.normalized() if side.length > 1e-4 else Vector((1.0, 0.0, 0.0))
        lift = _UP - tangent * tangent.z
        lift = lift.normalized() if lift.length > 1e-4 else side
        for sign in ((1.0, -1.0) if pairs else (side_sign,)):
            roll = s["fork_lift"] * math.pi / 2.0 + rng.uniform(-0.5, 0.5) * r     # Fork Lift: 0 = in the plane of the branch, sideways; 1 = straight up
            sideways = (side * math.cos(roll) * sign + lift * math.sin(roll)).normalized()
            a = s["fork_angle"] + rng.uniform(-0.2, 0.2) * r
            heading = (tangent * math.cos(a) + sideways * math.sin(a)).normalized()
            flen = max(length * s["fork_length"] * (0.25 + 0.75 * (1.0 - u) / max(1.0 - first, 1e-6)) * (1.0 + rng.uniform(-0.2, 0.2) * r), 0.08)
            droop = s["branch_droop"] * 0.5
            flen = _fit(s, trunk, centre, heading, flen, droop)                 # the tip stays inside the crown outline
            base_r = min(max(radius * s["fork_radius"], flen * 0.03, 0.005), radius * 0.9)          # a fork is thinner than its branch
            result.append((_curve(s, rng, centre, heading, flen, base_r, droop, _fork_segments(s, flen), s["branch_collar"], radius), flen))
        side_sign = -side_sign
    return result


def _branch_detail(s, j, levels, size):
    """The settings for one branch: the smaller it is, the less detail. `size` is the reach of the crown where the
    branch grows, as a part of the widest reach (a thin branch near the bottom or the top edge of the crown, where
    the radius is small, is small): fewer forks and generations, fewer sides and segments. Fork Fade is how fast the
    detail falls (0 = the same everywhere, 1 = in proportion to the size). The top Fork Top Skip rows have no forks."""
    rows = max(levels - s["fork_top_skip"], 1)                  # the rows that may fork
    detail = 1.0 - s["fork_fade"] * (1.0 - _clamp(size, 0.0, 1.0))
    sides = max(3, round(s["branch_sides"] * (0.6 + 0.4 * detail)))
    segments = max(min(s["branch_segments"], 2), round(s["branch_segments"] * (0.5 + 0.5 * detail)))
    forks = round(s["branch_forks"] * detail) if j < rows else 0
    generations = round(s["fork_levels"] * detail)
    if forks < 1 or generations < 1:
        forks = generations = 0
    return dict(s, branch_forks=forks, fork_levels=generations, branch_sides=sides, branch_segments=segments)


def _grow(s, rng, trunk, path, length, generation=1):
    """The forks of a branch and their forks, Fork Levels generations deep: a list of (path, generation)."""
    if generation > s["fork_levels"] or not s["branch_forks"]:
        return []
    result = []
    for fork, flen in _fork_paths(s, rng, trunk, path, length):
        result.append((fork, generation))
        result += _grow(s, rng, trunk, fork, flen, generation + 1)
    return result


# --------------------------------------------------------------------------------------
# foliage
# --------------------------------------------------------------------------------------

_ICO = {}       # detail -> (points of a unit icosphere, faces as lists of point numbers)


def _icosphere(detail):
    if detail not in _ICO:
        tmp = bmesh.new()
        bmesh.ops.create_icosphere(tmp, subdivisions=detail, radius=1.0)
        tmp.verts.ensure_lookup_table()
        tmp.faces.ensure_lookup_table()
        _ICO[detail] = ([v.co.copy() for v in tmp.verts], [[v.index for v in f.verts] for f in tmp.faces])
        tmp.free()
    return _ICO[detail]


_CUBE = {}      # cuts -> (points of a subdivided cube, faces as lists of point numbers)


def _cube_grid(cuts):
    """A cube from -1 to 1 with every edge cut into cuts + 1 pieces: a grid of quads on every side (a box that can be bent)."""
    if cuts not in _CUBE:
        tmp = bmesh.new()
        bmesh.ops.create_cube(tmp, size=2.0)
        bmesh.ops.subdivide_edges(tmp, edges=tmp.edges[:], cuts=cuts, use_grid_fill=True)
        tmp.verts.ensure_lookup_table()
        tmp.faces.ensure_lookup_table()
        _CUBE[cuts] = ([v.co.copy() for v in tmp.verts], [[v.index for v in f.verts] for f in tmp.faces])
        tmp.free()
    return _CUBE[cuts]


def _frame(axis):
    """Three unit vectors a, b, c: a is the axis, b is sideways (horizontal), c = a x b, so that b x c = a."""
    a = axis.normalized()
    b = a.cross(_UP)
    b = b.normalized() if b.length > 1e-4 else Vector((1.0, 0.0, 0.0))
    return a, b, a.cross(b)


def _blob(s, centre, axis, ra, rb, rc, puffs=False):
    """A clump of foliage is only noted here; _build_leaves makes the clumps, the biggest first, and drops the ones that
    would hide inside another. `puffs`: a clump of leaves gets small puffs on its surface (a fluffy cloud), a skirt of needles does not."""
    s["_specs"].append((centre.copy(), axis.copy(), ra, rb, rc, puffs))


def _ball_geometry(rng, s, centre, axis, ra, rb, rc, puffs):
    """The balls of one clump of foliage, as plain data: an icosphere stretched to radii ra (along the axis), rb, rc, with
    every point pushed a little in or out, and Puffs small icospheres sitting on its surface (more on the top than on the
    bottom): a fluffy cloud. Returns a list of (centre, radius of the ball that surely lies inside, points, faces, uv of
    the points for the shared leaf square, points of the unit sphere, mean radius). The shared UV: the side view of the
    main ball, u across (b), v along the axis (a); a puff gets the gradient of its place."""
    a, b, c = _frame(axis)
    shapes = [(centre, ra, rb, rc, s["leaf_detail"])]
    for _ in range(s["leaf_lobes"] if puffs else 0):
        d = Vector((rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0), rng.uniform(-0.4, 1.0)))
        if d.length < 1e-3:
            continue
        d.normalize()
        k = rng.uniform(0.45, 0.65)                                 # the size of a puff
        shapes.append((centre + a * (d.z * ra * 0.75) + b * (d.x * rb * 0.75) + c * (d.y * rc * 0.75),
                       ra * k, rb * k, rc * k, max(1, s["leaf_detail"] - 1)))
    balls = []
    for place, pa, pb, pc, detail in shapes:
        points, faces = _icosphere(detail)
        jitter = [1.0 + rng.uniform(-0.4, 0.4) * s["randomness"] for _ in points]
        verts = [place + a * (p.z * pa * j) + b * (p.x * pb * j) + c * (p.y * pc * j) for p, j in zip(points, jitter)]
        uvs = [(0.5 + 0.5 * _clamp((v - centre).dot(b) / max(rb, 1e-6), -1.0, 1.0),
                0.5 + 0.5 * _clamp((v - centre).dot(a) / max(ra, 1e-6), -1.0, 1.0)) for v in verts]
        balls.append((place, min(pa, pb, pc), verts, faces, uvs, points, (pa + pb + pc) / 3.0))
    return balls


def _unwrap_ball(units, faces, side):
    """UV of a ball for baking: a cylinder round its axis, cut at one seam (a face over the seam is moved to the far side).
    `side` is the height of the island in metres. Returns the UV of every face and the width of the island."""
    azimuth = [math.atan2(p.y, p.x) / (2.0 * math.pi) + 0.5 for p in units]
    result, width = [], 1.0
    for face in faces:
        us = [azimuth[i] for i in face]
        if max(us) - min(us) > 0.5:
            us = [u + 1.0 if u < 0.5 else u for u in us]
        width = max(width, max(us))
        result.append([(u * side, _clamp(units[i].z * 0.5 + 0.5, 0.0, 1.0) * side) for u, i in zip(us, face)])
    return result, width * side


def _build_leaves(bm, leaves, rng, s):
    """Make the foliage, the biggest clump first. Nothing that is not seen is made (Merge Leaves, 0 = make everything):
    a clump whose centre is on the spot of a clump that is already there, or that sits mostly inside one, is dropped; and
    so is every face that lies inside another ball of the foliage (a puff inside its clump, a ball inside its neighbour).
    A face goes when all its points are well inside a ball other than its own; the balls are looked up in a grid.
    UV: Unique UV (for baking): every ball has an island of its own, unwrapped; otherwise all clumps share one square."""
    merge = s["leaf_merge"]
    kept, balls = [], []                                # kept: (centre, radius of the ball inside); balls: all balls of the kept clumps
    for centre, axis, ra, rb, rc, puffs in sorted(s["_specs"], key=lambda spec: -max(spec[2], spec[3], spec[4])):
        inner, outer = min(ra, rb, rc), max(ra, rb, rc)
        if merge > 0.0 and any((old - centre).length < merge * min(old_inner, inner)             # on the same spot
                               or (old - centre).length + 0.6 * merge * outer < old_inner         # inside a bigger one
                               for old, old_inner in kept):
            continue
        kept.append((centre, inner))
        balls += _ball_geometry(rng, s, centre, axis, ra, rb, rc, puffs)
    if not balls:
        return
    grid, cell = {}, 1.0
    if merge > 0.0:
        cell = 2.0 * max(max(ball[1] for ball in balls), 1e-3)
        for number, ball in enumerate(balls):
            place, inner = ball[0], ball[1]
            lo = [int((place[k] - inner) // cell) for k in range(3)]
            hi = [int((place[k] + inner) // cell) for k in range(3)]
            for x in range(lo[0], hi[0] + 1):
                for y in range(lo[1], hi[1] + 1):
                    for z in range(lo[2], hi[2] + 1):
                        grid.setdefault((x, y, z), []).append((place, (0.85 * inner) ** 2, number))
    for number, (_place, _inner, verts, faces, uvs, units, mean) in enumerate(balls):
        made, shown = {}, []
        for index, face in enumerate(faces):
            points = [verts[i] for i in face]
            if grid:
                mid = sum(points, Vector()) / len(points)
                if any(other != number and all((p - centre).length_squared < limit for p in points)
                       for centre, limit, other in grid.get((int(mid.x // cell), int(mid.y // cell), int(mid.z // cell)), ())):
                    continue
            for i in face:
                if i not in made:
                    made[i] = bm.verts.new(verts[i])
            shown.append((bm.faces.new([made[i] for i in face]), index))
        if not shown:
            continue
        if s["uv_bake"]:
            side = 0.6 * mean                                   # a ball is small: its island is small, the density is lower than the bark's
            unwrapped, width = _unwrap_ball(units, faces, side)
            s["_leaf_islands"].append({"w": width, "h": side, "solo": True, "faces": [(face, unwrapped[index]) for face, index in shown]})
        else:
            for face, index in shown:
                leaves.append((face, [uvs[i] for i in faces[index]]))


def _oriented(bm, verts, toward):
    """A face whose normal looks the way of `toward` (the order of the points is turned when it does not)."""
    normal = (verts[1].co - verts[0].co).cross(verts[2].co - verts[0].co)
    if normal.dot(toward) < 0.0:
        verts = list(reversed(verts))
    return bm.faces.new(verts)


def _bush_stems(bm, islands, rng, s, rx, ry, crown_z):
    """The stems of a bush that is lifted off the ground (Bush Lift, Bush Stems): Bush Stems separate stems, their feet at
    random places in a circle of the radius Roots Radius round the centre (not all from one point), leaning by Stem Lean (the angle from the vertical: 0 = vertical, plus = out like a fan, minus = in). They
    stop just inside the bottom of the crown: nothing inside it. Every third stem has one short side branch below the crown.
    Thin tubes, part of the branches."""
    count, lift = s["bush_stems"], s["bush_lift"]
    if count <= 0:
        return
    spread = s["bush_stem_radius"]
    thick = max(0.025 * s["height"], 0.012)
    down = Vector((0.0, 0.0, -1.0))
    top = lift + 0.18 * (s["height"] - lift)                       # just into the crown
    for k in range(count):
        angle = rng.uniform(0.0, 2.0 * math.pi)
        distance = spread * math.sqrt(rng.uniform(0.05, 1.0))      # even over the circle
        foot = Vector((math.cos(angle) * distance, math.sin(angle) * distance, 0.0))
        lean = s["bush_stem_lean"] + rng.uniform(-0.1, 0.1)                        # Stem Lean: the angle from the vertical, out (+) or in (-), a little different for every stem
        head = Vector((foot.x + math.cos(angle) * top * math.tan(lean), foot.y + math.sin(angle) * top * math.tan(lean), top))
        middle = foot.lerp(head, 0.5) + Vector((rng.uniform(-0.04, 0.04), rng.uniform(-0.04, 0.04), 0.0))
        _tube(bm, islands, [(foot, thick), (middle, thick * 0.85), (head, thick * 0.7)], 4, down, False, s["uv_straight"], 0.0)
        if k % 3 == 0:                                             # one short side branch, below the crown
            start = foot.lerp(head, 0.45)
            end = start + Vector((math.cos(angle + 0.9) * 0.25 * max(spread, 0.2), math.sin(angle + 0.9) * 0.25 * max(spread, 0.2), (top - start.z) * 0.7))
            _tube(bm, islands, [(start, thick * 0.6), (end, thick * 0.45)], 4, down, False, s["uv_straight"], 0.0)


def _bush(bm_leaves, leaves, bm_branches, branch_islands, rng, s):
    """A bush as one faceted blob (the Bush Blob foliage): an icosphere (Leaf Detail) made into a ball, a rounded box or an egg
    (Bush Shape; a box is a cube cut into a grid), as wide as 2 x Radius 2 (`crown_radius_mid`), Bush Length times as long, and `height` high from Bush Lift
    up. Every point is pushed in or out (Bush Rough): uneven, like a low-poly bush. The bottom is flat (it stands on the
    ground). Bush Stems: thin stems from the ground up into a lifted blob. UV: unwrapped round the axis, one island."""
    shape, lift = s["bush_shape"], s["bush_lift"]
    rx = max(s["bush_width"] / 2.0, 0.1)                            # Bush Width and Bush Length are the whole size, in metres
    ry = max(s["bush_length"] / 2.0, 0.1)
    if shape == 'SPHERE' and (s["bush_cloud"] or s["bush_blobs"] > 1):   # blobs: balls made (and trimmed) like clumps of leaves; Bush Cloud is for the single one
        rzc = max(s["height"] - lift, 0.2) / 2.0
        blobs = s["bush_blobs"]
        if blobs <= 1:                                              # one cloud: a ball with puffs
            s["leaf_lobes"] = max(s["leaf_lobes"], 5)
            _blob(s, Vector((0.0, 0.0, lift + rzc)), _UP, rzc, rx, ry, True)
        else:                                                       # Bush Blobs balls: the biggest and the tallest in the middle, the rest round it, lower and smaller
            for k in range(blobs):
                if k == 0:
                    size, cx, cy, tall = 0.75, 0.0, 0.0, 1.0
                else:
                    size = rng.uniform(0.5, 0.65)
                    a = 2.0 * math.pi * (k - 1) / (blobs - 1) + rng.uniform(-0.4, 0.4) + 0.6
                    cx, cy, tall = math.cos(a) * rx * 0.5, math.sin(a) * ry * 0.5, rng.uniform(0.6, 0.85)
                rz = rzc * tall
                _blob(s, Vector((cx, cy, lift + rz)), _UP, rz, rx * size, ry * size, False)
        _bush_stems(bm_branches, branch_islands, rng, s, rx, ry, lift + 0.55 * (s["height"] - lift))
        return
    rz = max(s["height"] - lift, 0.2) / 1.85                        # the blob goes from -0.85 to 1 of its z radius
    centre = Vector((0.0, 0.0, lift + 0.85 * rz))
    if shape == 'BOX':
        points, faces = _cube_grid(max(1, s["leaf_detail"]))        # a box: a cube cut into a grid, the corners a little rounded
    else:
        points, faces = _icosphere(s["leaf_detail"])
    faces = [tri for face in faces for tri in ([face] if len(face) == 3 else [[face[0], face[1], face[2]], [face[0], face[2], face[3]]])]
    verts = []
    for p in points:
        d = p.copy()
        if shape == 'BOX':
            d = d.lerp(d.normalized() * 1.25, 0.3)
        if shape == 'EGG':
            squeeze = 1.0 - 0.4 * max(d.z, 0.0)
            d = Vector((d.x * squeeze, d.y * squeeze, d.z))
        jitter = 1.0 + rng.uniform(-1.0, 1.0) * 0.24 * s["bush_rough"]
        verts.append(bm_leaves.verts.new(centre + Vector((d.x * rx * jitter, d.y * ry * jitter, max(d.z, -0.85) * rz * jitter))))
    made = []
    for face in faces:
        f = bm_leaves.faces.new([verts[i] for i in face])
        made.append(f)
    side = 0.8 * max(rx, ry, rz)
    unwrapped, width = _unwrap_ball(points, faces, side)
    if s["uv_bake"]:
        s["_leaf_islands"].append({"w": width, "h": side, "solo": True, "faces": list(zip(made, unwrapped))})
    else:
        leaves.extend((f, [(u / width, v / side) for u, v in uvs]) for f, uvs in zip(made, unwrapped))
    _bush_stems(bm_branches, branch_islands, rng, s, rx, ry, lift + 0.55 * (s["height"] - lift))


def _cap_cone(bm, leaves, rng, s, trunk, z_base, radius, top_z):
    """The top tier of a conifer: a plain cone (a triangle in the side view) from its hem up to `top_z`, over the end of the
    trunk, instead of a tier with lobes and cuts (it would be a thin blade). Three rings (the base and two above it) and a
    slightly concave profile, wider at the foot; Tier Lobes sides; the top view UV."""
    lobes, height = s["tier_lobes"], s["height"]
    axis, _r = _trunk_at(trunk, z_base)
    axis_top, _r2 = _trunk_at(trunk, height)
    turn = rng.uniform(0.0, 2.0 * math.pi)
    rings = []
    for u in (0.0, 0.34, 0.68):
        z = z_base + (top_z - z_base) * u
        centre = Vector(axis).lerp(Vector(axis_top), u)
        rad = radius * (1.0 - u) ** 1.4                           # concave: narrower in the middle than a straight cone
        rings.append([bm.verts.new((centre.x + math.cos(turn + 2.0 * math.pi * k / lobes) * rad,
                                    centre.y + math.sin(turn + 2.0 * math.pi * k / lobes) * rad, z)) for k in range(lobes)])
    apex = bm.verts.new((axis_top.x, axis_top.y, top_z))
    triangles = []
    for index in range(len(rings) - 1):
        for k in range(lobes):
            k2 = (k + 1) % lobes
            lower, upper = rings[index], rings[index + 1]
            triangles += [(lower[k], lower[k2], upper[k2]), (lower[k], upper[k2], upper[k])]
    for k in range(lobes):
        triangles.append((rings[-1][k], rings[-1][(k + 1) % lobes], apex))
    scale = 1.15 * radius
    shown = []
    for tri in triangles:
        face = _oriented(bm, list(tri), Vector((0.0, 0.0, 1.0)))
        shown.append((face, [(0.5 + 0.5 * (v.co.x - axis.x) / scale, 0.5 + 0.5 * (v.co.y - axis.y) / scale) for v in face.verts]))
    if s["uv_bake"]:
        side = 1.6 * radius
        s["_leaf_islands"].append({"w": side, "h": side, "solo": True,
                                   "faces": [(face, [(u * side, v * side) for u, v in uvs]) for face, uvs in shown]})
    else:
        leaves.extend(shown)


def _tiers(bm, leaves, rng, s, trunk):
    """The foliage of a conifer as tiers: Levels skirts stacked up the trunk instead of branches. Every tier is a cone with a
    scalloped hem seen from above as a circle with cuts: Tier Lobes wide lobes with a straight edge (two corners, on one
    radius) and a cut between them that narrows to a point towards the trunk (Tier Cut Width: how wide at the hem, Tier Notch: how deep). A collar round
    the trunk and a little roof over it. The hem radius is the crown radius at the height of the tier (the same silhouette
    as for branches); Tier Height is how tall the skirt is, as a part of its radius, and a tier is always tall enough to
    overlap the next one, so that no bare trunk shows between them; the top tier ends in the top of the tree. Tier
    Thickness: a rim along the hem, like Solidify with Only Rim and no bottom (a chunky tier, nothing under it); Tier
    Chamfer: the end of the rim is a slope, not a box (the lower edge is drawn in under the lobe). Tier
    Layers: a smaller skirt inside, hanging lower. One smoothing group (Smooth Shading). UV: the top view; every lobe of the rim is a strip."""
    count, lobes, layers = max(s["branch_levels"], 1), s["tier_lobes"], s["tier_layers"]
    first, last, height, r, thick = s["branch_start"], s["branch_end"], s["height"], s["randomness"], s["tier_thickness"]
    step = 2.0 * math.pi / lobes
    half = 0.5 * step * (1.0 - s["tier_gap"])               # half the width of a lobe, as an angle
    spacing = height * (last - first) / count
    widest = max(s["crown_radius_bottom"], s["crown_radius_mid"], s["crown_radius_top"], 1e-6)
    small = count - 1                                               # only the top tier is a cone, all the others are tiers
    last_hem = height * (first + (last - first) * ((count - 0.5) / count))
    top_z = height + max(0.25 * (height - last_hem), 0.15)       # the common top of the small tiers, a little over the trunk: its end is inside
    for tier in range(count):
        c = (tier + 0.5) / count
        radius = _crown_reach(s, c)
        hem = height * (first + (last - first) * c)
        if tier >= small:
            if True:                                                # the top tier: a plain cone up over the end of the trunk
                _cap_cone(bm, leaves, rng, s, trunk, hem, max(radius * 1.25, 0.1 * widest), top_z)
            continue
        if radius < 0.05:
            continue
        rise = max(s["tier_height"] * radius, 1.7 * spacing)       # tall enough to overlap the next tier
        roof = 0.35 * rise
        if tier == count - 1 or hem + rise + roof > height:        # the top tier ends in the top of the tree, the rest do not go over it
            rise = max((height - hem) / 1.35, 0.1)
            roof = 0.35 * rise
        spin = rng.uniform(0.0, step)
        for layer in range(layers):
            scale = 1.0 - 0.3 * layer                               # the inner layers are smaller ...
            rl = radius * scale
            z_hem = hem - 0.3 * rise * layer                        # ... and hang lower
            z_top = z_hem + rise * scale
            axis_hem, _r = _trunk_at(trunk, z_hem)
            axis_top, trunk_r = _trunk_at(trunk, z_top)
            collar = max(trunk_r * 1.5, 0.12 * rl)
            turn = spin + 0.5 * step * layer                        # a layer is turned half a step: its lobes are over the cuts of the outer one

            def point(angle, radius_, z):
                return bm.verts.new((axis_hem.x + math.cos(angle) * radius_, axis_hem.y + math.sin(angle) * radius_, z))

            # the cuts: every one a little different (the place and the width), so the lobes between them differ too
            cuts = []
            for k in range(lobes):
                middle = turn + (k + 0.5) * step + rng.uniform(-0.2, 0.2) * step * r
                width = max(step * s["tier_gap"] * (1.0 + rng.uniform(-0.9, 0.9) * r), 0.02 * step)
                cuts.append((middle, width))
            rings = [[]]                                            # the collar, then the inner rings that bend the skirt, in the middle of the lobes
            bend = s["tier_bend"]
            marks = (0.3, 0.6) if bend > 0.0 else ()                # closer to the trunk than the bottom of the cuts: the top view does not fold
            rings += [[] for _mark in marks]
            hem_points = []
            for k in range(lobes):
                before = cuts[k - 1][0] - (2.0 * math.pi if k == 0 else 0.0), cuts[k - 1][1]
                start, end = before[0] + before[1] / 2.0, cuts[k][0] - cuts[k][1] / 2.0        # the angles of the two corners of the lobe
                a = (start + end) / 2.0
                lobe_r = rl * (1.0 + rng.uniform(-0.5, 0.5) * r)
                z_lobe = z_hem - rng.uniform(0.0, 0.12) * rise * r
                notch_r = lobe_r * s["tier_notch"] * (1.0 + rng.uniform(-0.12, 0.12) * r)
                z_notch = z_hem + 0.18 * rise * scale
                rings[0].append(bm.verts.new((axis_top.x + math.cos(a) * collar, axis_top.y + math.sin(a) * collar, z_top)))
                for ring, mark in zip(rings[1:], marks):            # steep near the trunk, flatter towards the hem: a bent profile
                    drop = 1.0 - (1.0 - mark) ** (1.0 + bend)
                    ring.append(point(a, mark * lobe_r, z_top - rise * scale * drop * (z_top - z_lobe) / max(z_top - z_hem, 1e-6)))
                hem_points.append((point(start, lobe_r, z_lobe), point(end, lobe_r, z_lobe),                    # the two corners of a lobe
                                   point(cuts[k][0], notch_r, z_notch)))                  # the bottom of the cut: one point, the cut narrows to it
            top, outer_ring = rings[0], rings[-1]
            apex = bm.verts.new((axis_top.x, axis_top.y, z_top + roof * scale))
            triangles = []
            for index in range(len(rings) - 1):                     # between the inner rings
                for k in range(lobes):
                    k2 = (k + 1) % lobes
                    inner, outer = rings[index], rings[index + 1]
                    triangles += [(inner[k], inner[k2], outer[k2]), (inner[k], outer[k2], outer[k])]
            for k in range(lobes):
                k2 = (k + 1) % lobes
                (a0, b0, n), a1 = hem_points[k], hem_points[k2][0]
                triangles += [(outer_ring[k], a0, b0), (outer_ring[k], b0, n), (outer_ring[k], n, outer_ring[k2]), (outer_ring[k2], n, a1),
                              (top[k], top[k2], apex)]
            face_scale = 1.15 * rl
            shown = []
            for tri in triangles:
                face = _oriented(bm, list(tri), Vector((0.0, 0.0, 1.0)))
                shown.append((face, [(0.5 + 0.5 * (v.co.x - axis_hem.x) / face_scale, 0.5 + 0.5 * (v.co.y - axis_hem.y) / face_scale)
                                     for v in face.verts]))
            rim = []                                                # (lobe, quad, its place along the hem, its length)
            band = thick                                            # the width of the rim face, along its slope
            if thick > 0.0:
                ring = [v for points in hem_points for v in points]
                length = math.hypot(rl, rise * scale)
                drop, inward = thick * rl / length, thick * rise * scale / length       # the thickness along the normal of the skirt, upside down
                inward += s["tier_chamfer"] * thick * 3.0          # a chamfer: the lower edge goes in under the lobe, the end is a slope, not a box
                band = math.hypot(drop, inward)
                lower = []
                for v in ring:
                    out = Vector((v.co.x - axis_hem.x, v.co.y - axis_hem.y, 0.0))
                    out = out.normalized() if out.length > 1e-6 else Vector((1.0, 0.0, 0.0))
                    lower.append(bm.verts.new((v.co.x - out.x * inward, v.co.y - out.y * inward, v.co.z - drop)))
                edges = [(ring[m].co - ring[(m + 1) % len(ring)].co).length for m in range(len(ring))]
                position = 0.0
                for m in range(len(ring)):
                    m2 = (m + 1) % len(ring)
                    middle = (ring[m].co + ring[m2].co) / 2.0
                    face = _oriented(bm, [ring[m], lower[m], lower[m2], ring[m2]],
                                     Vector((middle.x - axis_hem.x, middle.y - axis_hem.y, 0.0)))
                    rim.append((m // 3, face, position, edges[m]))
                    position += edges[m]
            if s["uv_bake"]:
                side = 1.6 * rl                                     # an island of its own, the top view, a bit lower density than the bark
                s["_leaf_islands"].append({"w": side, "h": side, "solo": True,
                                           "faces": [(face, [(u * side, v * side) for u, v in uvs]) for face, uvs in shown]})
                for lobe in range(lobes):                           # a strip of its own for every lobe of the rim (a long strip would not fit)
                    pieces = [item for item in rim if item[0] == lobe]
                    if not pieces:
                        continue
                    start = pieces[0][2]
                    quads = []
                    for _lobe, face, pos, edge in pieces:
                        uvs = {0: (pos - start, band), 1: (pos - start, 0.0), 2: (pos - start + edge, 0.0), 3: (pos - start + edge, band)}
                        quads.append((face, [uvs[min(i, 3)] for i in range(len(face.verts))]))
                    s["_leaf_islands"].append({"w": sum(item[3] for item in pieces), "h": band, "solo": True, "faces": quads})
            else:
                leaves.extend(shown)
                total = max(sum(edges), 1e-6) if rim else 1.0
                for _lobe, face, pos, edge in rim:                   # the shared square: the rim is a thin strip along its bottom edge
                    leaves.append((face, [(pos / total, 0.04), (pos / total, 0.0), ((pos + edge) / total, 0.0), ((pos + edge) / total, 0.04)]))


def _leaf_scale(s, rng, c, ratio):
    """The size of a clump compared to Leaf Size. Falloff: the biggest are in the middle of the crown, at the widest place (and
    nearer the bottom than the top); the smaller the crown radius there (`ratio` = the radius as a part of the widest one) and
    the higher (`c`, 0 = bottom, 1 = top), the smaller. Variation: every clump is up to this part bigger or smaller."""
    falloff = 1.0 - s["leaf_taper"] * (0.6 * (1.0 - _clamp(ratio, 0.0, 1.0)) + 0.4 * c)
    return max(falloff, 0.2) * (1.0 + rng.uniform(-1.0, 1.0) * s["leaf_variation"])


def _clear_of_trunk(s, place, reach, away):
    """Move a clump of leaves sideways, away from the trunk, until the trunk is not inside it: at the height of the clump its
    centre is at least the trunk radius plus `reach` (the horizontal radius of the clump) from the axis of the trunk.
    `away` is the direction to move in when the centre is right on the axis."""
    axis, trunk_r = _trunk_at(s["_trunk"], place.z)
    off = Vector((place.x - axis.x, place.y - axis.y, 0.0))
    need = trunk_r + reach
    if off.length >= need:
        return place
    if off.length > 1e-4:
        away = off
    elif away.length < 1e-4:
        away = Vector((1.0, 0.0, 0.0))
    return Vector((axis.x, axis.y, place.z)) + away.normalized() * need


def _foliage(bm, leaves, rng, s, path, weight):
    """The foliage of one branch (or fork) `path`; `weight` makes the forks smaller than the branch."""
    size = s["leaf_size"] * weight
    tip, start = path[-1][0], path[0][0]
    if s["foliage"] == 'CLUMPS':
        # not all on the tips: a clump sits somewhere near the end of the branch and is thrown a little to a side (Spread)
        spread = s["leaf_spread"]
        centre, _radius, direction = _along(path, 1.0 - rng.uniform(0.0, 0.5) * min(spread, 1.0))
        throw = Vector((rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0), rng.uniform(-0.6, 0.6)))
        place = centre - direction * (size * 0.3) + throw * (spread * size * 0.9)
        place = _clear_of_trunk(s, place, 0.8 * size, Vector((tip.x - start.x, tip.y - start.y, 0.0)))      # not through the trunk
        _blob(s, place, _UP, size * s["leaf_flat"], size, size, True)
    elif s["foliage"] == 'SHEATH':
        chord = tip - start
        if chord.length > 1e-4:
            _blob(s, start + chord * 0.58, chord, chord.length * 0.55, size, size * s["leaf_flat"])


def _foliage_top(bm, leaves, rng, s, apex):
    """The crown of the tree: a clump on the top of the trunk, or a spire for a conifer."""
    size = s["leaf_size"]
    if s["foliage"] == 'CLUMPS':
        _blob(s, apex - _UP * (size * 0.2), _UP, size * s["leaf_flat"], size, size, True)
    elif s["foliage"] == 'SHEATH':
        _blob(s, apex - _UP * (size * 0.9), _UP, size * 2.2, size * 0.7, size * 0.7)


# --------------------------------------------------------------------------------------
# the tree
# --------------------------------------------------------------------------------------

PARTS = ('trunk', 'branches', 'leaves')


def _stubs(bm, islands, rng, s, trunk):
    """Short stubs along the bare trunk below the crown, like the stubs of dead branches on a pine: Trunk Stubs of them in a
    spiral, from Stubs Start (a part of the way from the ground to the first branches) up to the first branches, level or a
    little down; the nearer the crown, the longer (up to Stub Length). They are part of the branches."""
    count = s["trunk_stubs"]
    if count <= 0 or s["branch_start"] < 0.08:
        return
    t0, t1 = s["branch_start"] * s["stub_start"], s["branch_start"]
    turn = rng.uniform(0.0, 2.0 * math.pi)
    for i in range(count):
        f = (i + rng.uniform(0.1, 0.9)) / count
        azimuth = turn + i * _GOLDEN
        centre, trunk_r = _trunk_at(trunk, (t0 + (t1 - t0) * f) * s["height"])
        out = Vector((math.cos(azimuth), math.sin(azimuth), 0.0))
        heading = (out + Vector((0.0, 0.0, rng.uniform(-0.35, 0.1)))).normalized()
        length = s["stub_length"] * (0.45 + 0.55 * f) * rng.uniform(0.7, 1.3)           # the nearer the crown, the longer
        base_r = min(max(trunk_r * 0.3, 0.015), trunk_r * 0.5)
        path = [(centre + out * (trunk_r * 0.6), base_r), (centre + out * trunk_r + heading * length, base_r * max(s["branch_tip"], 0.6))]
        _tube(bm, islands, path, 4, Vector((0.0, 0.0, -1.0)), False, s["uv_straight"], 0.0)


def build_parts(p):
    """The tree as three separate meshes (bmesh), each with its own UV in 0..1 and its own material:
    the trunk, the branches (with the forks) and the foliage. The foliage is None when there is none."""
    s = resolve(p)
    s["_specs"] = []                       # the clumps of foliage, noted by _blob and made by _build_leaves
    s["_leaf_islands"] = []                # the UV islands of the balls (Unique UV)
    rng = random.Random(int(s["seed"]))
    r = s["randomness"]
    bm_trunk, bm_branches, bm_leaves = bmesh.new(), bmesh.new(), bmesh.new()
    uv_trunk, uv_branches, uv_leaves = (b.loops.layers.uv.new("UVMap") for b in (bm_trunk, bm_branches, bm_leaves))
    trunk_islands, branch_islands, leaves = [], [], []

    trunk = _trunk_path(s, rng)
    s["_trunk"] = trunk
    bush = s["foliage"] == 'BUSH'                     # a bush is one blob: no trunk, no branches
    if not bush:
        _tube(bm_trunk, trunk_islands, trunk, s["trunk_sides"], Vector((0.0, 1.0, 0.0)), s["bottom_cap"], s["uv_straight"])

    tiers = s["foliage"] == 'TIERS'                   # tiers instead of branches
    levels, per = (0 if (tiers or bush) else s["branch_levels"]), s["branches_per_level"]
    first, last = s["branch_start"], s["branch_end"]
    spacing = (last - first) / max(levels - 1, 1)
    rotation = rng.uniform(0.0, 2.0 * math.pi)
    down = Vector((0.0, 0.0, -1.0))
    for j in range(levels):
        c = j / (levels - 1) if levels > 1 else 0.5             # place in the crown, 0 = bottom, 1 = top
        for m in range(per):
            azimuth = rotation + j * _GOLDEN + m * 2.0 * math.pi / per + rng.uniform(-0.5, 0.5) * (2.0 * math.pi / per) * r
            t = _clamp(first + (last - first) * c + rng.uniform(-1.0, 1.0) * spacing * s["branch_spread"], first, last)
            angle = _clamp(s["branch_angle_bottom"] + (s["branch_angle_top"] - s["branch_angle_bottom"]) * c
                           + rng.uniform(-0.26, 0.26) * r, 0.1, 2.1)
            ideal = _crown_reach(s, _clamp((t - first) / (last - first), 0.0, 1.0))
            reach = ideal * (1.0 + rng.uniform(-0.25, 0.25) * r)
            widest = max(s["crown_radius_bottom"], s["crown_radius_mid"], s["crown_radius_top"], 1e-6)
            sj = _branch_detail(s, j, levels, ideal / widest)         # the smaller the branch, the less detail
            forking = sj["branch_forks"] > 0 and sj["fork_levels"] > 0
            length = max(reach / max(math.sin(angle), 0.25), 0.12)
            if forking:
                length /= 1.0 + min(0.3 * sj["fork_length"] * sj["fork_levels"], 0.6)    # the forks add to the reach: keep the outline
            heading = Vector((math.sin(angle) * math.cos(azimuth), math.sin(angle) * math.sin(azimuth), math.cos(angle)))
            outward = Vector((math.cos(azimuth), math.sin(azimuth), 0.0))
            centre, trunk_r = _trunk_at(trunk, t * s["height"])
            # the thickness where the branch leaves: a part of the trunk at that height, and always thinner than the trunk; the more
            # branches leave in a row, the thinner each (together they are not thicker than the trunk)
            cap = trunk_r * min(0.8, 1.1 / math.sqrt(per))
            # a long branch is not thinner than a few cm (length * 0.03), but not for a low Thickness: there the floor goes down with it
            floor = length * 0.03 * _clamp(s["branch_radius"] / 0.3, 0.0, 1.0)
            base_r = min(max(trunk_r * s["branch_radius"] * (1.0 + rng.uniform(-0.2, 0.2) * r), floor, 0.006), cap)
            # the first ring (with the collar) is inside the trunk: its edge, sideways, must not come out of the trunk surface
            ring = base_r * (1.0 + s["branch_collar"]) * 1.05 if s["branch_collar"] > 0.0 else base_r * 1.05
            ring = min(ring, trunk_r * 0.95)
            inside = math.sqrt(max(trunk_r * trunk_r - ring * ring, 0.0))
            start = centre + outward * _clamp(inside * 0.9, 0.0, trunk_r * 0.55)
            length = _fit(s, trunk, start, heading, length, s["branch_droop"])
            path = _curve(sj, rng, start, heading, length, base_r, sj["branch_droop"], sj["branch_segments"], s["branch_collar"], trunk_r)
            _tube(bm_branches, branch_islands, path, s["branch_sides"], down, False, s["uv_straight"], 0.0)
            forks = _grow(sj, rng, trunk, path, length) if forking else []
            for fork, generation in forks:
                _tube(bm_branches, branch_islands, fork, max(3, sj["branch_sides"] - generation), down, False, s["uv_straight"], 0.0)
            if s["foliage"] != 'NONE':
                ratio = ideal / widest
                _foliage(bm_leaves, leaves, rng, s, path, _leaf_scale(s, rng, c, ratio))
                if s["foliage"] == 'CLUMPS':            # a skirt of needles covers the branch with its shoots: one skirt
                    for fork, generation in forks:
                        _foliage(bm_leaves, leaves, rng, s, fork, _leaf_scale(s, rng, c, ratio) * 0.8 ** generation)

    if not tiers and not bush:
        _stubs(bm_branches, branch_islands, rng, s, trunk)
    if bush:
        _bush(bm_leaves, leaves, bm_branches, branch_islands, rng, s)
    elif tiers:
        _tiers(bm_leaves, leaves, rng, s, trunk)
    elif s["foliage"] != 'NONE':
        _foliage_top(bm_leaves, leaves, rng, s, trunk[-1][0])
    _build_leaves(bm_leaves, leaves, rng, s)
    for island in trunk_islands:
        island["layer"] = uv_trunk
    for island in branch_islands:
        island["layer"] = uv_branches
    groups = [trunk_islands, branch_islands]
    if s["uv_bake"]:
        for island in s["_leaf_islands"]:
            island["layer"] = uv_leaves
        if s["_leaf_islands"]:
            groups.append(s["_leaf_islands"])
    elif leaves:
        tallest = max((island["h"] for island in trunk_islands), default=1.0)
        side = max(2.0 * s["leaf_size"], 0.3 * tallest)      # the foliage: one square for all clumps, a good part of the tile
        groups.append([{"w": side, "h": side, "layer": uv_leaves,
                        "faces": [(face, [(u * side, v * side) for u, v in uvs]) for face, uvs in leaves]}])
    _write_uv(groups, s)
    parts = {'trunk': bm_trunk if trunk_islands else None, 'branches': bm_branches if branch_islands else None, 'leaves': bm_leaves if (leaves or s["_leaf_islands"]) else None}
    for bm in (bm_trunk, bm_branches, bm_leaves):
        if parts['trunk'] is bm or bm in parts.values():
            for face in bm.faces:
                face.smooth = s["smooth"] and not face.tag
        else:
            bm.free()
    return parts


_PART_MATERIAL = {'trunk': 0, 'branches': 0, 'leaves': 1}      # the index in MATERIALS: 2 materials, as in the FBX


def ensure_material(part):
    name, color = MATERIALS[_PART_MATERIAL[part]]
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf is not None:
            bsdf.inputs["Base Color"].default_value = color
            bsdf.inputs["Roughness"].default_value = 0.9
        mat.diffuse_color = color       # viewport colour, set last: use_nodes may reset it
    return mat


def fill_mesh(mesh, bm, part):
    """(Re)build `mesh` in place from `bm` (one part of the tree) and free `bm`."""
    mesh.clear_geometry()
    mesh.materials.clear()
    mesh.materials.append(ensure_material(part))
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
