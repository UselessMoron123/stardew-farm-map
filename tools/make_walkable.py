#!/usr/bin/env python3
"""Generate walkable/Farm.tmx from original/Farm.tmx.

Goal: every tile on the farm becomes walkable for the player, with zero
visual change, so the whole map can be traversed (e.g. for screenshots).

Collision rules (stardewvalleywiki.com/Modding:Maps + GameLocation.isTilePassable):
  * A tile on the Buildings layer blocks the player unless the tile *index*
    has property `Passable` (any non-empty value), or the placed tile itself
    has a per-position `Passable` property (TileData object in the Buildings
    objectgroup).
  * A tile on the Back layer blocks if it has `Water` or `Passable`
    (index-level or per-position).
  * Paths / Front / AlwaysFront / AlwaysFront2 never affect collision.

Edits performed:
  1. Indices used ONLY on Buildings (never on Back) get index-level
     `Passable=T` (and lose `Water` if present).
  2. Indices used on Back that carry `Water` (or a `Passable=F` marker) get
     those props stripped → pond and edges become walkable. Tile art and
     animations are untouched, so the map looks identical.
  3. Buildings cells whose index is *also* used on Back (index-level marking
     would break the Back uses) are handled per cell:
       - REMOVED when their gid equals the Back gid beneath (pixel-identical
         duplicates → invisible change, robust in every engine path);
       - otherwise a per-position TileData object with `Passable=T` is added
         to the Buildings objectgroup (the mechanism documented by the wiki).
  4. Empty Back cells are reported but left untouched (original out-of-bounds
     pockets behind the farmhouse / map edges).

Validation re-parses the output and asserts:
  * all layer data except Buildings is byte-identical to the source;
  * Buildings layer differs exactly at the removed duplicate cells;
  * all property edits are present;
  * a walkability simulation reports only the known empty pockets as blocked.
"""

from __future__ import annotations

import base64
import struct
import sys
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

SRC = Path("original/Farm.tmx")
DST = Path("walkable/Farm.tmx")

BUILDINGS_PASSABLE_VALUE = "T"


def decode_layer(layer: ET.Element) -> list[int]:
    raw = zlib.decompress(base64.b64decode("".join(layer.find("data").text.split())))
    return list(struct.unpack(f"<{len(raw)//4}I", raw))


def encode_layer(gids: list[int]) -> str:
    return base64.b64encode(zlib.compress(struct.pack(f"<{len(gids)}I", *gids), 9)).decode("ascii")


def tile_props(tileset: ET.Element, local_id: int) -> ET.Element | None:
    tile = find_tile(tileset, local_id)
    if tile is None:
        return None
    return tile.find("properties")


def find_tile(tileset: ET.Element, local_id: int) -> ET.Element | None:
    for tile in tileset.findall("tile"):
        if int(tile.get("id")) == local_id:
            return tile
    return None


def prop_value(properties: ET.Element | None, name: str) -> str | None:
    if properties is None:
        return None
    for prop in properties:
        if prop.get("name") == name:
            return prop.get("value")
    return None


def ensure_property(tileset: ET.Element, local_id: int, name: str, value: str) -> None:
    """Add/overwrite a string property on a tileset tile index (creates the
    <tile> entry and <properties> as needed, keeping <properties> before
    <animation>)."""
    tile = find_tile(tileset, local_id)
    if tile is None:
        tile = ET.SubElement(tileset, "tile", {"id": str(local_id)})
    props = tile.find("properties")
    if props is None:
        props = ET.Element("properties")
        anim = tile.find("animation")
        if anim is None:
            tile.append(props)
        else:
            tile.insert(0, props)
    for prop in props:
        if prop.get("name") == name:
            prop.set("value", value)
            return
    ET.SubElement(props, "property", {"name": name, "value": value})


def strip_properties(tileset: ET.Element, local_id: int, *names: str) -> None:
    """Remove properties by name; drop empty containers / empty tiles."""
    tile = find_tile(tileset, local_id)
    if tile is None:
        return
    props = tile.find("properties")
    if props is None:
        return
    for prop in list(props):
        if prop.get("name") in names:
            props.remove(prop)
    if len(props) == 0:
        tile.remove(props)
    if len(tile) == 0:  # no properties, no animation
        tileset.remove(tile)


def main() -> int:
    tree = ET.parse(SRC)
    root = tree.getroot()

    width = int(root.get("width"))
    height = int(root.get("height"))
    tilecount = width * height

    # tileset lookup: firstgid -> element (sorted ascending)
    tilesets = sorted(root.findall("tileset"), key=lambda ts: int(ts.get("firstgid")))

    def locate(gid: int) -> tuple[ET.Element, int] | None:
        if gid == 0:
            return None
        found = None
        for ts in tilesets:
            fg = int(ts.get("firstgid"))
            if fg <= gid < fg + int(ts.get("tilecount")):
                found = (ts, gid - fg)
        return found

    layers = {lyr.get("name"): lyr for lyr in root.findall("layer")}
    gids = {name: decode_layer(lyr) for name, lyr in layers.items()}
    for name, arr in gids.items():
        assert len(arr) == tilecount, f"layer {name}: bad size"
    src_gids = {name: arr[:] for name, arr in gids.items()}  # pristine snapshot
    src_data_text = {name: "".join(lyr.find("data").text.split())
                     for name, lyr in layers.items()}

    # ---- classify tile indices -------------------------------------------
    back_used: set[tuple] = set()
    buildings_used: set[tuple] = set()
    for name, arr in gids.items():
        for gid in arr:
            loc = locate(gid)
            if loc is None:
                continue
            key = (loc[0].get("name"), loc[1])
            if name == "Back":
                back_used.add(key)
            elif name == "Buildings":
                buildings_used.add(key)

    shared_idx = buildings_used & back_used
    buildings_only_idx = buildings_used - back_used

    # water / Passable markers per index, per tileset
    index_props: dict[tuple, dict[str, str]] = {}
    for ts in tilesets:
        for tile in ts.findall("tile"):
            props = tile.find("properties")
            if props is None:
                continue
            key = (ts.get("name"), int(tile.get("id")))
            index_props[key] = {p.get("name"): p.get("value") for p in props}

    back_water_idx = {
        key
        for key, props in index_props.items()
        if "Water" in props and key in back_used
    }
    back_passable_idx = {  # e.g. the Passable=F markers on water tiles
        key
        for key, props in index_props.items()
        if "Passable" in props and key in back_used
    }

    edits = {"index_passable_added": 0, "water_stripped": 0, "passable_stripped": 0,
             "cells_removed": 0, "pos_objects": 0}

    # ---- edit 1: Buildings-only indices -> Passable=T (+ no Water) --------
    def ts_for(key: tuple) -> ET.Element:
        for ts in tilesets:
            if ts.get("name") == key[0]:
                return ts
        raise KeyError(key)

    for key in sorted(buildings_only_idx):
        ts = ts_for(key)
        if prop_value(tile_props(ts, key[1]), "Passable") != BUILDINGS_PASSABLE_VALUE:
            ensure_property(ts, key[1], "Passable", BUILDINGS_PASSABLE_VALUE)
            edits["index_passable_added"] += 1
        if prop_value(tile_props(ts, key[1]), "Water") is not None:
            strip_properties(ts, key[1], "Water")
            edits["water_stripped"] += 1

    # ---- edit 2: Back-used water indices lose Water / Passable ------------
    for key in sorted(back_water_idx):
        strip_properties(ts_for(key), key[1], "Water", "Passable")
        edits["water_stripped"] += 1
        if key in back_passable_idx:
            edits["passable_stripped"] += 1
    for key in sorted(back_passable_idx - back_water_idx):
        strip_properties(ts_for(key), key[1], "Passable")
        edits["passable_stripped"] += 1

    # ---- edit 3: shared-index Buildings cells -----------------------------
    buildings_objgroup = None
    for og in root.findall("objectgroup"):
        if og.get("name") == "Buildings":
            buildings_objgroup = og
    assert buildings_objgroup is not None, "missing Buildings objectgroup"

    existing_objects: dict[tuple[int, int], ET.Element] = {}
    max_oid = 0
    for og in root.findall("objectgroup"):
        for obj in og.findall("object"):
            oid = int(obj.get("id"))
            max_oid = max(max_oid, oid)
            if og is buildings_objgroup:
                existing_objects[(int(obj.get("x")) // 16, int(obj.get("y")) // 16)] = obj

    next_oid = max_oid + 1
    removed_cells: list[int] = []          # indexes into Back/Buildings arrays
    position_cells: list[int] = []          # cells getting a TileData object

    for i, gid in enumerate(gids["Buildings"]):
        loc = locate(gid)
        if loc is None:
            continue
        key = (loc[0].get("name"), loc[1])
        if key not in shared_idx:
            continue
        if gids["Back"][i] == gid:
            # exact duplicate of the Back tile beneath → remove invisibly
            gids["Buildings"][i] = 0
            removed_cells.append(i)
            continue
        position_cells.append(i)

    # objects for the rest
    for i in position_cells:
        x, y = i % width, i // width
        obj = existing_objects.get((x, y))
        if obj is not None:
            props = obj.find("properties")
            if props is None:
                props = ET.SubElement(obj, "properties")
            if not any(p.get("name") == "Passable" for p in props):
                ET.SubElement(props, "property", {"name": "Passable", "value": "T"})
        else:
            obj = ET.SubElement(buildings_objgroup, "object", {
                "id": str(next_oid), "name": "TileData",
                "x": str(x * 16), "y": str(y * 16),
                "width": "16", "height": "16",
            })
            props = ET.SubElement(obj, "properties")
            ET.SubElement(props, "property", {"name": "Passable", "value": "T"})
            existing_objects[(x, y)] = obj
            next_oid += 1
        edits["pos_objects"] += 1

    root.set("nextobjectid", str(next_oid))

    # ---- write output ------------------------------------------------------
    # Buildings layer data is the only one we re-encode (removed duplicates).
    data_el = layers["Buildings"].find("data")
    data_el.text = encode_layer(gids["Buildings"])

    ET.indent(tree, space="  ")
    xml_body = ET.tostring(root, encoding="unicode")
    DST.parent.mkdir(parents=True, exist_ok=True)
    content = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_body + "\n"
    DST.write_text(content, encoding="utf-8")

    # keep the Content Patcher test pack's asset in sync
    pack_asset = Path("[CP] Walkable Farm/assets/Farm.tmx")
    pack_asset.parent.mkdir(parents=True, exist_ok=True)
    pack_asset.write_text(content, encoding="utf-8")

    # ---- validation --------------------------------------------------------
    problems: list[str] = []

    out = ET.parse(DST).getroot()
    out_layers = {lyr.get("name"): lyr for lyr in out.findall("layer")}
    out_gids = {name: decode_layer(lyr) for name, lyr in out_layers.items()}

    # 1. untouched layers identical (raw text); Buildings is checked in section 2
    for name in src_gids:
        if name == "Buildings":
            continue
        out_text = "".join(out_layers[name].find("data").text.split())
        if src_data_text[name] != out_text:
            problems.append(f"layer {name} data changed unexpectedly")

    # 2. Buildings differs exactly at removed cells, and each removal was a Back duplicate
    changed = [i for i in range(tilecount)
               if src_gids["Buildings"][i] != out_gids["Buildings"][i]]
    if sorted(changed) != sorted(removed_cells):
        problems.append(f"Buildings changes {changed[:10]}... != removed {removed_cells[:10]}...")
    for i in removed_cells:
        if out_gids["Buildings"][i] != 0 or src_gids["Buildings"][i] != src_gids["Back"][i]:
            problems.append(f"cell {i % width},{i // width}: removal not a Back duplicate")

    # 3. property edits present in output
    out_index_props: dict[tuple, dict[str, str]] = {}
    for ts in out.findall("tileset"):
        for tile in ts.findall("tile"):
            props = tile.find("properties")
            if props is None:
                continue
            out_index_props[(ts.get("name"), int(tile.get("id")))] = {
                p.get("name"): p.get("value") for p in props
            }
    for key in buildings_only_idx:
        if out_index_props.get(key, {}).get("Passable") != BUILDINGS_PASSABLE_VALUE:
            problems.append(f"missing Passable=T on {key}")
        if "Water" in out_index_props.get(key, {}):
            problems.append(f"Water not stripped from {key}")
    for key in back_water_idx:
        if "Water" in out_index_props.get(key, {}):
            problems.append(f"Water not stripped from Back-used {key}")
    for key in back_passable_idx:
        if "Passable" in out_index_props.get(key, {}):
            problems.append(f"Passable not stripped from Back water {key}")

    # 4. position objects cover every kept shared cell
    out_obj_cells = set()
    for og in out.findall("objectgroup"):
        if og.get("name") != "Buildings":
            continue
        for obj in og.findall("object"):
            props = obj.find("properties")
            has_passable = props is not None and any(
                p.get("name") == "Passable" and p.get("value") for p in props
            )
            if has_passable:
                out_obj_cells.add((int(obj.get("x")) // 16, int(obj.get("y")) // 16))
    for i in position_cells:
        cell = (i % width, i // width)
        if cell not in out_obj_cells:
            problems.append(f"missing position Passable object at {cell}")

    # 5. walkability simulation --------------------------------------------
    def index_has(out_key_cell_gid: int, prop: str) -> bool:
        loc = locate(out_key_cell_gid)
        if loc is None:
            return False
        return prop in out_index_props.get((loc[0].get("name"), loc[1]), {})

    src_back = decode_layer(layers["Back"])
    back_null_pockets = [i for i, g in enumerate(src_back) if g == 0]

    def model(position_honored: bool) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
        blocked = []
        for i in range(tilecount):
            b_gid = out_gids["Buildings"][i]
            bk_gid = out_gids["Back"][i]
            cell = (i % width, i // width)
            if position_honored and cell in out_obj_cells:
                continue  # per-position Passable → walkable
            if b_gid != 0:
                walkable = index_has(b_gid, "Passable")
            elif bk_gid == 0:
                walkable = False
            else:
                walkable = not (index_has(bk_gid, "Water") or index_has(bk_gid, "Passable"))
            if not walkable:
                blocked.append(cell)
        return blocked, back_null_pockets

    blocked_a, pockets = model(position_honored=True)
    blocked_b, _ = model(position_honored=False)

    # pockets = empty Back cells that have no Buildings tile at all in the OUTPUT
    expected_pockets = [(i % width, i // width) for i in pockets
                        if out_gids["Buildings"][i] == 0]
    if sorted(blocked_a) != sorted(expected_pockets):
        problems.append(f"model A blocked {sorted(blocked_a)} != expected pockets {sorted(expected_pockets)}")

    # ---- report ------------------------------------------------------------
    print(f"wrote {DST} ({DST.stat().st_size} bytes)")
    print("edits:", edits)
    print(f"indices: buildings-used={len(buildings_used)} "
          f"buildings-only={len(buildings_only_idx)} shared-with-back={len(shared_idx)}")
    print(f"shared Buildings cells: removed-as-duplicate={len(removed_cells)} "
          f"position-objects={len(position_cells)}")
    print(f"Back water indices stripped of Water: {len(back_water_idx)}; "
          f"Passable markers stripped: {len(back_passable_idx)}")
    print(f"model A (per-position honored) blocked cells: {len(blocked_a)} -> {blocked_a}")
    print(f"model B (index-only fallback) blocked cells: {len(blocked_b)} "
          f"(the shared-index overlay cells above)")
    if problems:
        print("VALIDATION FAILED:")
        for p in problems:
            print("  -", p)
        return 1
    print("validation: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
