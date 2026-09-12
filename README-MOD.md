# Square Farm — modified `Farm.xnb` (revision 3)

A rebuilt **standard farm map** (the vanilla `Maps/Farm.xnb`): one clean rectangle of
plain green ground, no decoration, no litter spawns, every gameplay feature kept.
Revisions: v1 square field → v2 fixed report 277–287 → **v3 fixed report 288–294
("keep textures simple and universal")**.

![preview](preview_comparison.png)

## What the map looks like now (v3)

| Area | Change |
|---|---|
| **Shape** | One clean rectangle (x3–76, y9–58). West mountain bite, jagged NE corner and the receding SE corner are filled in. |
| **Ground** | A **single universal tile** everywhere below the north band: plain green lawn 351. No colour variants, no dirt patches, no pebbles/holes, no flowers, no paths, no stone patio look, no water. Each tile carries `Diggable=T / Type=Dirt / CanPlantTrees=T` (hoe, trees, buildings work like on the vanilla field) **and `NoSpawn="All"`**. |
| **No litter, ever** | `NoSpawn="All"` on every ground tile means weeds, stones, twigs and grass can neither spawn nor spread anywhere on the farm. (Objects already baked into an *old save* are not part of the map — they disappear only in a new save.) |
| **No pond** | Removed completely (289). There is no water on the farm any more. |
| **No trees** | All tree tokens removed, including the two tidy rows (292). |
| **Kept verbatim from vanilla** | North band y0–8: hill, Grandpa's shrine, greenhouse + cave doors, the fences, and the cliff-base shadow row y8 (288: helps blending). Yard Buildings layer x55–79 / y9–20: the fence lines (complete — no walk-through gap, 291) and the east border. Forest exit corridor x40–42 / y59–64. |
| **Kept as function, not as look** | The yard ground became plain lawn too, but keeps the vanilla tile properties: spouse-patio `Buildable "f"` markers and the patio stones' `NoSpawn/Type/placeable` props (the patio still works, it just looks like grass), shipping-bin & mailbox ground, cave/greenhouse approaches. |
| **Border** | Invisible blockers on lawn: west x2, east x77 (gate y15–18 open), south row y59, and the whole bottom band y60–64 except the Forest warp corridor — you cannot step off the map. |
| **Layers** | No Front / AlwaysFront tile below y9: nothing draws over the player or chops graphics. |
| **Paths layer** | Only the 14 multiplayer-cabin markers and one grass-init token (index 22), hidden under the farmhouse so the mandatory start-tuft is invisible (294). |
| **Preserved** | All warps + approaches, cave door + frame, farm sign, cabin markers + `Order`, tilesheets untouched (recolor mods keep working). |

## Play-test report 288–294 → fix

| Screen | Note | Fix |
|---|---|---|
| 288 | cliff-base "shadow" row liked | kept verbatim (north band y0–8 untouched) |
| 289 | remove pond | pond and all water removed |
| 290 | tree textures; wrong grass tile at the red square | trees removed entirely; the whole yard/field is one uniform tile, so there is no mismatching tile anywhere |
| 291 | grass cut the fence; two fence tiles walkable | the fence line y9 (x55–68 + x73–76) and the vertical fence x78 are restored complete from vanilla; the two-tile gap is closed |
| 292 | remove trees, stone textures, grass textures, flowers, path to the box, pebbles/holes, sprouts; prevent litter at all | all of them gone (uniform lawn, patio/path/pebbles replaced by lawn, no tokens); `NoSpawn="All"` on every ground tile stops all future weed/stone/grass spawns — yes, litter can be prevented completely (in a new save) |
| 293 | darker dots and lighter patches unwanted | the speckle variants are gone — one flat tile everywhere |
| 294 | "nothing down there?" + stray grass object in the corner | the south band is intentionally a sealed plain-grass strip (invisible wall + map edge); the stray grass tuft was the mandatory grass-init token — it now sits under the farmhouse where it is invisible |

> **Existing saves:** anything already baked into a save (v1/v2 tree rows, weeds, stones,
> grass tufts, tilled soil) survives any map swap. Use a **new save** to see v3 exactly
> as designed — and with `NoSpawn="All"` everywhere, it will also stay litter-free.

## Install

1. **Back up** your Stardew folder's original file: `Content/Maps/Farm.xnb`.
2. Copy `output/Farm.xnb` into `Content/Maps/`, replacing the original.
3. Start the game (best on a new save). Remove the file (restore the backup) to go back to vanilla.

## Files

- `output/Farm.xnb` — the modified map, ready to install (uncompressed XNB, loads fine in the game/SMAPI).
- `tools/tbin.py` — TBin (tIDE) parser/writer (byte-exact round-trip verified).
- `tools/build_farm.py` — the whole rebuild as reproducible code, with a validation pass (warps, gates, door frames, patio props, fence continuity, cabin markers, uniform tillable no-spawn lawn, sealed border, no water, no front-layer tiles…).
- `tools/pack_xnb.py` — wraps the tbin into the uncompressed XNB (reader block reused, size fields patched, round-trip verified).
- `tools/render_farm.py` — schematic renderer used for the previews.
- `work/Farm.tbin` / `work/Farm_modified.tbin` — extracted vanilla & modified maps; `work/xnb_shell.bin` — the 50-byte XNB header/reader prefix.

## Want tweaks?

Everything is a constant at the top of `tools/build_farm.py`: field rectangle
(`FX0..FY1`), the ground tile (`LAWN`), wall row (`WALL_Y`), yard block (`NX0..NY1`),
corridor (`CX0..CX1`), hidden grass-init position (`HOUSE_HIDE`). Then re-run
`python3 tools/build_farm.py && python3 tools/pack_xnb.py`.
