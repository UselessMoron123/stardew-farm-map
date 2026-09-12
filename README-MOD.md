# Square Farm — modified `Farm.xnb` (revision 2)

A rebuilt **standard farm map** (the vanilla `Maps/Farm.xnb`): the farmable land is one
clean rectangle of **green lawn**, all runtime/gameplay features kept, and the whole
play-test report (screens 277–287) fixed.

![preview](preview_comparison.png)

## What the map looks like now

| Area | Change |
|---|---|
| **Shape** | One clean rectangle (x3–76, y9–58). West mountain bite, jagged NE corner and the receding SE corner are filled in. |
| **Ground** | Uniform **green lawn** — tile 351 and its vanilla neighbours (300/304/305/329/352/354/355), the same grass family the original uses around the farmhouse and the north hill. Each field tile carries `Diggable=T / Type=Dirt / CanPlantTrees=T`, so the hoe, trees and buildings behave exactly like on the vanilla field. |
| **Kept verbatim from vanilla** | The whole north band y0–8 (hill, Grandpa's shrine, greenhouse + cave doors, fences, Backwoods corridor), the **north-east yard block x57–79 / y8–20** (farmhouse lawn, shipping-bin & mailbox ground, the **spouse patio** with its `Buildable` stone tiles, the BusStop gate) and the Forest exit corridor x40–42 / y59–64. Nothing the game draws at runtime lost its ground. |
| **Pond** | One pond, copied tile-for-tile (water + sparkle animation) from the vanilla east pond, placed **inside** the square at the south-west (x8–13, y50–55). Reachable from every side, fully on-screen, fishable / crab-pottable. |
| **Border** | Invisible blockers on plain lawn (west x2, east x77, south y59) — every one carries `NoSpawn="All"`, so grass and weeds can never grow on the un-interactable line. The whole bottom band y60–64 is sealed except the Forest corridor: you can't step off the map any more. |
| **Trees** | Every vanilla scatter token removed. Two tidy rows (oak/maple/pine) behind the border at x=1 and x=78 — crowns stay inside the map and stay clear of the BusStop gate. |
| **Debris** | Every weed / stone / twig / stump / log / boulder / bush spawn token stripped. |
| **Preserved** | All warps + approaches, cave door + frame, greenhouse approach, farm sign, the 14 multiplayer-cabin markers with their `Order` values, the grass-init token the game requires, tilesheets untouched (recolor mods keep working). |

## Play-test report → fix

| Screen | Complaint | Fix |
|---|---|---|
| 277 | path to the bus stop blocked by trees | tree rows no longer cross the gate (east row starts at y21); gate corridor x77–79 / y15–18 is verbatim vanilla and open |
| 278 | textures; want the **green** ground like the original where the spouse zone / shipping bin / mailbox / well are | ground is green lawn now; the whole NE yard block (house lawn, bin, mailbox, spouse patio) is copied verbatim from vanilla |
| 279 | ground textures don't blend | no more tan-dirt-vs-green clash: one lawn family everywhere, and the square meets vanilla terrain only along vanilla's own transition rows (y8 cliff base, yard edge) |
| 280 | random pink tree — "what if you remove all trees?" | That pink tree was not a spawn token: it was leftover vanilla **front-layer tree graphics** on the west cliff edge, which is why removing trees would not have made it disappear. v2 removes every Front/AlwaysFront tile below the north band *and* every scatter token; the only trees left are the two tidy rows (oak/maple/pine) |
| 281 | could walk down outside the map; pond unreachable behind an invisible line | bottom band y60–64 fully sealed (except the Forest warp corridor); the outside pond + its walled nook are gone — the pond now sits inside the field with walkable shore on all four sides |
| 282 | "hid behind the grass texture" | the vanilla Front-layer grass fringe (and every Front/AlwaysFront tile below y9) is removed — nothing draws over the player any more |
| 283 | water tiles don't blend | the pond is no longer hand-assembled: it is the vanilla pond copied verbatim, including its animated sparkle tiles |
| 284 | un-interactable line where grass still grew | every blocker tile carries `NoSpawn="All"` — grass/weeds cannot spawn on walls or the sealed band |
| 285 / 286 | tree textures cut; pond outside the map | tree crowns kept ≥1 tile inside the map edge (rows at x=1 / x=78); no Front-layer fringe left to chop crowns; pond moved inside the map |
| 287 | standing where grass ground should be | the tan diggable-dirt (587) is gone from the play area; everything is the green lawn family |

> **Existing saves:** objects that are already *baked into a save* are not part of the
> map — they survive any map swap. That includes the tree rows, weeds and grass grown
> from the **previous** version of this mod (e.g. the trees hugging the west/east map
> edge, or grass tufts on the old wall line). Start a **new save** to see the map exactly
> as designed.

## Install

1. **Back up** your Stardew folder's original file: `Content/Maps/Farm.xnb`.
2. Copy `output/Farm.xnb` into `Content/Maps/`, replacing the original.
3. Start the game (best on a new save). Remove the file (restore the backup) to go back to vanilla.

## Files

- `output/Farm.xnb` — the modified map, ready to install (uncompressed XNB, loads fine in the game/SMAPI).
- `tools/tbin.py` — TBin (tIDE) parser/writer (byte-exact round-trip verified).
- `tools/build_farm.py` — the whole rebuild as reproducible code, with a validation pass (warps, gates, door frames, patio props, cabin markers, lawn, walls, pond reachability, no front-layer tiles below the north band…).
- `tools/pack_xnb.py` — wraps the tbin into the uncompressed XNB (reader block reused, size fields patched, round-trip verified).
- `tools/render_farm.py` — schematic renderer used for the previews.
- `work/Farm.tbin` / `work/Farm_modified.tbin` — extracted vanilla & modified maps; `work/xnb_shell.bin` — the 50-byte XNB header/reader prefix.

## Want tweaks?

Easy one-line changes in `tools/build_farm.py`: field rectangle (`FX0..FY1`), lawn palette
(`LAWN_BASE` / `LAWN_SPECKLE`), pond position (`POND_DST`) or size (`POND_SRC` window),
tree rows (the two `put('Paths', …)` loops), wall row (`WALL_Y`). Then re-run
`python3 tools/build_farm.py && python3 tools/pack_xnb.py`.
