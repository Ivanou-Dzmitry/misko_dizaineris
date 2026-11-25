# MiskoDizaineris: how to work

[Русский](HOWTO.ru.md) | **English**

A short guide from installation to a ready FBX. All the parameters are described in the [README](../README.md).

## 1. Install

1. Download `misko_dizaineris.zip` from the [Releases](https://github.com/Ivanou-Dzmitry/misko_dizaineris/releases) page.
2. In Blender 5.2+: **Edit → Preferences → Get Extensions → the down arrow at the top right → Install from Disk…** and pick the zip.
3. Panel: **3D View → N → MiskoDizaineris**. A tree can also be added with **Add → Mesh → Tree**.

If you had ForestConstructor or ForestTree installed: remove it in Extensions, it is a separate extension. Copy the presets from the old folder to the new one (see "Presets").

## 2. The first tree

1. Put the 3D cursor where the tree should stand.
2. At the top of the panel press a type button (Spruce, Pine, Poplar, Linden, Willow, Birch, Bush, Bare Tree). The tree appears at the cursor, the settings of the type are loaded into the panel.
3. Keep **Live Update** on, select the tree and drag the parameters: it is rebuilt on the fly (6–18 ms).

**All Types** puts one tree of every type in a row (to compare), **Add Variants** puts a row of trees of the current type with different `Seed`.

Important: Live Update changes the **selected** trees. If nothing is selected, nothing changes. **Get Settings** takes the settings of the active tree into the panel (handy to go back to an old tree).

## 3. Where to start with the shape

Go down the panel sections, from the big to the small:

| Section | What you decide |
|---------|-----------------|
| **Tree** | `Seed` (another variant of the same tree), `Randomness`, `Smooth Shading` |
| **Trunk** | `Height`, trunk radii at the ground, in the middle and at the top, the bend (`Bend`, `Wobble`), the flare at the root (`Flare`) |
| **Crown (3 Levels)** | the crown silhouette: where the lower and upper branches grow and how far they reach from the trunk |
| **Branches** | how many rows (`Levels`) and branches per row (`Per Level`), angles, droop, thickness (`Thickness`), bend (`Wiggle`), collar (`Collar`) |
| **Forks** | forks on the branches and their generations; 0 = plain sticks |
| **Foliage** | foliage: `Clumps`, `Sheath`, `Tiers` (spruce), `Bush Blob` (bush) or `None` |

Tips:
- A tree is never taller than `Height`: branches that would go higher are shortened.
- The smaller the branch, the less detail on it (forks, sides, segments). This is on purpose, for low-poly.
- Branches too thick: lower `Thickness` (a part of the trunk thickness at that place). Wire-thin branches come at a value around 0.02.
- The place where a branch leaves the trunk looks bad: lower `Collar` or `Wiggle`.

## 4. Bush

Type **Bush**: no trunk, thin stems come out of the ground, blobs of foliage over them.

- `Bush Shape`: Ball, Box (a rounded box) or Egg.
- `Bush Width` and `Bush Length`: the size in metres; different values make an oval bush or a hedge. `Height` is the height.
- `Bush Blobs`: 1–4 round blobs (Ball only). The biggest and tallest in the middle, the others round it. With 1 it is one cloud (`Bush Cloud` turns on the puffs).
- `Bush Rough` is the roughness of the surface, `Bush Lift` is how high the blob is lifted above the ground, `Bush Stems` and `Roots Radius` are the stems and the radius of their spread, `Stem Lean` is the lean.

## 5. Spruce

Type **Spruce**: `Foliage` = Tiers, tiers (skirts) instead of branches. The main controls: `Branches → Levels` (the number of tiers), `Crown Bottom` (how low the lowest tier starts), `Tier Lobes`, `Tier Notch`, `Tier Bend`, `Tier Thickness`. The topmost tier is always a cone.

## 6. Presets

In the **Presets** group you can save the current settings under a name and load them later. One preset is one JSON in the folder:

```
%APPDATA%\Blender Foundation\Blender\<version>\extensions\.user\user_default\misko_dizaineris\presets
```

The folder button opens it, the circle button re-reads the files. You can put a preset into the folder by hand and press "re-read". To move to another computer, just copy the JSON files.

## 7. What you get in the scene

A tree is an **Empty** (the root) and three objects under it: `<name>_trunk`, `<name>_branches`, `<name>_leaves`. There are two materials: `FT_Bark` (trunk and branches) and `FT_Leaf` (foliage). Move and rotate the root, you do not need to pick the parts: selecting any part selects the whole tree.

## 8. UV and baking

One shared UV map 0..1 for the whole tree, islands do not overlap and are not rotated, the density is the same.

- **Unique UV (Bake)** (on by default): every branch and every foliage ball has its own island. Ready for baking AO and normals.
- Turn it off if you need a tiling texture: similar islands lie in a stack, and the foliage is on one shared square.
- `Straight Strips`, `Cut Trunk`, `UV Margin` are fine tuning (see the README).

## 9. FBX export

1. In the **Export** group set the folder and press **Export FBX**.
2. The selected trees are exported (or all, if nothing is selected).
3. `Merge Trunk and Branches` (on): the trunk and branches as one mesh `<name>_wood`, the foliage as a separate `<name>_leaves`: two meshes, two materials.
4. `Separate Files`: one file per tree. `At Origin`: the tree at the zero point.
5. Scale and axes are baked into the mesh (for Unity/Unreal).

## 10. If something is wrong

| Symptom | What to do |
|---------|------------|
| The parameters do not change the tree | Select the tree (or any part of it); check `Live Update` |
| The tree is heavy, the interface lags | Turn off `Live Update`, change the parameters and press **Rebuild Selected** |
| You need the settings of an existing tree back | Select it and press **Get Settings** |
| The presets disappeared after the rename | Copy the JSON files from `...\user_default\forest_constructor\presets` to `...\misko_dizaineris\presets` |
| The bush blobs are not visible | Type Bush, `Foliage` = Bush Blob, `Bush Shape` = Ball, `Bush Blobs` above 1 |
