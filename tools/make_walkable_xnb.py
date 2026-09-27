#!/usr/bin/env python3
"""Build walkable/Farm.xnb — a drop-in replacement for Content/Maps/Farm.xnb.

Pipeline:
  original/Farm.xnb  --LZX-->  tBIN  --> (structured edit) --> tBIN
                                                         |
  walkable/Farm.tmx  (source of truth for the edits) ----+--> diff-driven edits

The output is an *uncompressed* XNB using exactly the same header layout as
"[CP] Standard Clear Space]/assets/Farm.xnb" (flags 0x01, xnbLength, the
xTile.TideReader type-reader table, the tide 2-byte prefix + payload length),
which is a proven-to-load uncompressed Farm.xnb.

Edits are derived by DIFFING walkable/Farm.tmx against a fresh conversion of
the original XNB (so the XNB matches the validated walkable TMX exactly):
  * tileset index properties added/removed (Passable / Water / Passable=F),
  * Buildings-layer cells zeroed where they duplicated the Back tile,
  * per-cell TileData objects -> per-tile properties on the tBIN tiles.

Validation:
  1. structural round-trip: parse(serialize(parse(original))) == original,
  2. re-read the produced XNB end-to-end and convert it back to TMX,
  3. the re-converted TMX must be semantically identical to walkable/Farm.tmx
     (layer gids, properties, animations, objects — object ids ignored).
"""

from __future__ import annotations

import base64
import struct
import sys
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lzx import decompress_xnb_lzx  # noqa: E402
from tbin_to_tmx import convert, parse_tbin  # noqa: E402

SRC_XNB = Path("original/Farm.xnb")
WALKABLE_TMX = Path("walkable/Farm.tmx")
DST_XNB = Path("walkable/Farm.xnb")


# --------------------------------------------------------------- tBIN writer
class Writer:
    def __init__(self) -> None:
        self.buf = bytearray()

    def i32(self, v: int) -> None:
        self.buf += struct.pack("<i", v)

    def u8(self, v: int) -> None:
        self.buf.append(v & 0xFF)

    def s(self, v: str) -> None:
        raw = v.encode("utf-8")
        self.i32(len(raw))
        self.buf += raw


def write_props(w: Writer, props: list) -> None:
    w.i32(len(props))
    for key, ptype, val in props:
        w.s(key)
        w.u8(ptype)
        if ptype == 0:
            w.u8(1 if val else 0)
        elif ptype == 1:
            w.i32(val)
        elif ptype == 2:
            w.buf += struct.pack("<f", val)
        elif ptype == 3:
            w.s(val)
        else:
            raise ValueError(f"bad property type {ptype} for {key!r}")


def write_tile(w: Writer, tile: dict) -> None:
    w.i32(tile["index"])
    w.u8(tile["blend"])
    write_props(w, tile["props"])


def serialize_tbin(m: dict) -> bytes:
    w = Writer()
    w.buf += b"tBIN10"
    w.s(m["id"])
    w.s(m["desc"])
    write_props(w, m["props"])

    w.i32(len(m["sheets"]))
    for sh in m["sheets"]:
        w.s(sh["id"])
        w.s(sh["desc"])
        w.s(sh["image"])
        w.i32(sh["sheet_size"][0]); w.i32(sh["sheet_size"][1])
        w.i32(sh["tile_size"][0]); w.i32(sh["tile_size"][1])
        w.i32(sh["margin"][0]); w.i32(sh["margin"][1])
        w.i32(sh["spacing"][0]); w.i32(sh["spacing"][1])
        write_props(w, sh["props"])

    w.i32(len(m["layers"]))
    for lyr in m["layers"]:
        w.s(lyr["id"])
        w.u8(1 if lyr["visible"] else 0)
        w.s(lyr["desc"])
        w.i32(lyr["size"][0]); w.i32(lyr["size"][1])
        w.i32(lyr["tile_size"][0]); w.i32(lyr["tile_size"][1])
        write_props(w, lyr["props"])
        w_h = lyr["size"]
        for row in lyr["tiles"]:
            assert len(row) == w_h[0]
            ix = 0
            while ix < w_h[0]:
                tile = row[ix]
                if tile is None:
                    run = 0
                    while ix + run < w_h[0] and row[ix + run] is None:
                        run += 1
                    w.u8(ord("N"))
                    w.i32(run)
                    ix += run
                    continue
                if tile.get("animated"):
                    w.u8(ord("A"))
                    w.i32(tile["interval"])
                    w.i32(len(tile["frames"]))
                    for frame in tile["frames"]:
                        # always announce the sheet (frame-local state starts empty)
                        w.u8(ord("T"))
                        w.s(frame["sheet"])
                        w.u8(ord("S"))
                        write_tile(w, frame)
                    write_props(w, tile["props"])
                else:
                    w.u8(ord("T"))
                    w.s(tile["sheet"])
                    w.u8(ord("S"))
                    write_tile(w, tile)
                ix += 1
    return bytes(w.buf)


# --------------------------------------------------------------- TMX semantics
def tmx_props(el: ET.Element | None) -> list:
    if el is None:
        return []
    out = []
    for p in el:
        ptype = p.get("type", "string")
        if ptype == "bool":
            out.append((p.get("name"), 0, p.get("value") == "true"))
        elif ptype == "int":
            out.append((p.get("name"), 1, int(p.get("value"))))
        elif ptype == "float":
            out.append((p.get("name"), 2, float(p.get("value"))))
        else:
            out.append((p.get("name"), 3, p.get("value")))
    return out


def tmx_semantics(root: ET.Element) -> dict:
    """Comparable representation; object ids / nextobjectid excluded."""
    sem: dict = {
        "map_attrs": {k: root.get(k) for k in
                      ("width", "height", "tilewidth", "tileheight",
                       "orientation", "infinite")},
        "map_props": sorted(tmx_props(root.find("properties"))),
    }
    sem["tilesets"] = {}
    for ts in root.findall("tileset"):
        tiles = {}
        anims = {}
        for t in ts.findall("tile"):
            tid = int(t.get("id"))
            tiles[tid] = sorted(tmx_props(t.find("properties")))
            anim = t.find("animation")
            if anim is not None:
                anims[tid] = [(f.get("tileid"), f.get("duration")) for f in anim]
        sem["tilesets"][ts.get("name")] = {
            "firstgid": ts.get("firstgid"),
            "tilecount": ts.get("tilecount"),
            "columns": ts.get("columns"),
            "image": (ts.find("image").get("source"),
                      ts.find("image").get("width"),
                      ts.find("image").get("height")),
            "props": sorted(tmx_props(ts.find("properties"))),
            "tiles": tiles,
            "anims": anims,
        }
    sem["layers"] = {}
    for lyr in root.findall("layer"):
        raw = zlib.decompress(base64.b64decode("".join(lyr.find("data").text.split())))
        gids = list(struct.unpack(f"<{len(raw)//4}I", raw))
        sem["layers"][lyr.get("name")] = {
            "gids": gids,
            "props": sorted(tmx_props(lyr.find("properties"))),
            "visible": lyr.get("visible", "1"),
        }
    sem["objects"] = {}
    for og in root.findall("objectgroup"):
        cells = {}
        for obj in og.findall("object"):
            key = (obj.get("x"), obj.get("y"))
            props = tuple(sorted((n, t, v) for n, t, v in tmx_props(obj.find("properties"))))
            val = (obj.get("name"), obj.get("width"), obj.get("height"), props)
            cells.setdefault(key, []).append(val)
        sem["objects"][og.get("name")] = sorted(
            (k, tuple(sorted(v))) for k, v in cells.items())
    return sem


def sem_diff(a: dict, b: dict) -> list[str]:
    diffs = []
    for k in ("map_attrs", "map_props"):
        if a[k] != b[k]:
            diffs.append(f"{k}: {a[k]} != {b[k]}")
    if set(a["tilesets"]) != set(b["tilesets"]):
        diffs.append(f"tilesets {set(a['tilesets'])} != {set(b['tilesets'])}")
    for name in a["tilesets"]:
        if name not in b["tilesets"]:
            continue
        ta, tb = a["tilesets"][name], b["tilesets"][name]
        for f in ("firstgid", "tilecount", "columns", "image", "props", "anims"):
            if ta[f] != tb[f]:
                diffs.append(f"tileset {name}.{f} differs")
        if ta["tiles"] != tb["tiles"]:
            bad = [tid for tid in set(ta["tiles"]) | set(tb["tiles"])
                   if ta["tiles"].get(tid) != tb["tiles"].get(tid)]
            diffs.append(f"tileset {name} index props differ at tiles {sorted(bad)[:10]}")
    if set(a["layers"]) != set(b["layers"]):
        diffs.append(f"layer names {set(a['layers'])} != {set(b['layers'])}")
    for name in a["layers"]:
        if name not in b["layers"]:
            continue
        la, lb = a["layers"][name], b["layers"][name]
        if la["gids"] != lb["gids"]:
            bad = [i for i, (x, y) in enumerate(zip(la["gids"], lb["gids"])) if x != y]
            diffs.append(f"layer {name}: {len(bad)} gid diffs, first {bad[:8]}")
        for f in ("props", "visible"):
            if la[f] != lb[f]:
                diffs.append(f"layer {name}.{f} differs")
    for name in a["objects"]:
        if name not in b["objects"]:
            continue
        if a["objects"][name] != b["objects"][name]:
            sa, sb = a["objects"][name], b["objects"][name]
            only_a = [c for c in sa if c not in sb]
            only_b = [c for c in sb if c not in sa]
            diffs.append(f"objects[{name}]: only-orig {only_a[:3]} only-new {only_b[:3]}")
    return diffs


# --------------------------------------------------------------- XNB plumbing
def load_original() -> tuple[bytes, bytes, dict, bytes]:
    """-> (readers_region, tide_prefix_2bytes, parsed map, original tBIN bytes)"""
    xnb = SRC_XNB.read_bytes()
    content = decompress_xnb_lzx(xnb[10:], struct.unpack_from("<i", xnb, 10)[0])
    tbin_at = content.find(b"tBIN")
    assert tbin_at >= 6, "tBIN not found"
    prefix = content[tbin_at - 6:tbin_at]
    # prefix layout: 2 unknown bytes (00 01) + int32 payload length
    assert prefix[:2] == b"\x00\x01", f"unexpected tide prefix {prefix[:2].hex()}"
    plen = struct.unpack_from("<i", prefix, 2)[0]
    assert plen == len(content) - tbin_at, (
        f"payload length {plen} != {len(content) - tbin_at}")
    readers = content[:tbin_at - 6]
    m = parse_tbin(content[tbin_at:])
    return readers, prefix[:2], m, content[tbin_at:]


def build_xnb(readers: bytes, tide_head: bytes, tbin: bytes) -> bytes:
    out = bytearray(b"XNBw\x05\x01")
    out += struct.pack("<i", 0)  # placeholder xnbLength
    out += readers
    out += tide_head
    out += struct.pack("<i", len(tbin))
    out += tbin
    struct.pack_into("<i", out, 6, len(out))
    return bytes(out)


# --------------------------------------------------------------- edit diffing
def layer_gids_by_name(sem: dict) -> dict:
    return {n: l["gids"] for n, l in sem["layers"].items()}


def obj_cells_by_layer(sem: dict) -> dict:
    """{layer: {(tile_x, tile_y): [ (name,w,h,props), ... ]}} — tile coords."""
    out = {}
    for layer, entries in sem["objects"].items():
        cells = {}
        for (x, y), vals in entries:
            xi, yi = int(x), int(y)
            assert xi % 16 == 0 and yi % 16 == 0, f"object at non-tile pos {x},{y}"
            cells[(xi // 16, yi // 16)] = list(vals)
        out[layer] = cells
    return out


def main() -> int:
    problems: list[str] = []

    # ---- load & structural round-trip -------------------------------------
    readers, tide_head, m_orig, orig_tbin = load_original()
    print(f"original tBIN: {len(orig_tbin)} bytes, "
          f"{len(m_orig['sheets'])} sheets, {len(m_orig['layers'])} layers")

    rt = parse_tbin(serialize_tbin(m_orig))
    if rt != m_orig:
        # find first mismatch for diagnosis
        for key in m_orig:
            if rt.get(key) != m_orig.get(key):
                problems.append(f"round-trip mismatch in {key}")
        if not problems:
            problems.append("round-trip mismatch (unknown key)")
    else:
        print("structural round-trip: OK")

    # ---- diff walkable TMX vs original conversion -------------------------
    orig_tmx_root = ET.parse(
        Path("original/Farm.tmx")).getroot()  # validated == convert(original)
    walk_root = ET.parse(WALKABLE_TMX).getroot()
    sem_orig = tmx_semantics(orig_tmx_root)
    sem_walk = tmx_semantics(walk_root)

    ds = sem_diff(sem_orig, sem_walk)
    print(f"TMX diff (original -> walkable): {len(ds)} differences")
    for d in ds:
        print("   ", d)

    # ---- apply diffs to the tBIN structure --------------------------------
    m = m_orig
    sheets_by_id = {sh["id"]: sh for sh in m["sheets"]}
    layers_by_id = {ly["id"]: ly for ly in m["layers"]}

    # 1. tileset index props: recompute from TMX tile entries directly
    def index_props_by_sheet(root: ET.Element) -> dict:
        out = {}
        for ts in root.findall("tileset"):
            per = {}
            for t in ts.findall("tile"):
                per[int(t.get("id"))] = sorted(tmx_props(t.find("properties")))
            out[ts.get("name")] = per
        return out

    idx_orig = index_props_by_sheet(orig_tmx_root)
    idx_walk = index_props_by_sheet(walk_root)
    add_props = 0
    del_props = 0
    for sheet, per in idx_walk.items():
        sh = sheets_by_id[sheet]
        orig_per = idx_orig.get(sheet, {})
        for tid, props in per.items():
            orig_list = orig_per.get(tid, [])
            added = [p for p in props if p not in orig_list]
            removed = [n for n, _, _ in orig_list
                       if n not in {pn for pn, _, _ in props}]
            orig_by_name = {n: (t, v) for n, t, v in orig_list}
            for n, t, v in props:
                if n in orig_by_name and orig_by_name[n] != (t, v):
                    problems.append(
                        f"value change of {sheet}[{tid}].{n} unsupported")
            for name, ptype, val in added:
                key = f"@TileIndex@{tid}@{name}"
                assert not any(k == key for k, _, _ in sh["props"]), (
                    f"{key} already present")
                sh["props"].append((key, ptype, val))
                add_props += 1
            for name in removed:
                key = f"@TileIndex@{tid}@{name}"
                before = len(sh["props"])
                sh["props"] = [p for p in sh["props"] if p[0] != key]
                assert len(sh["props"]) == before - 1, f"{key} not found"
                del_props += 1
        # props removed on tiles absent from walk (no <tile> entry left)
        for tid, orig_list in orig_per.items():
            if tid not in per:
                for name, _, _ in orig_list:
                    key = f"@TileIndex@{tid}@{name}"
                    before = len(sh["props"])
                    sh["props"] = [p for p in sh["props"] if p[0] != key]
                    assert len(sh["props"]) == before - 1, f"{key} not found"
                    del_props += 1
    print(f"index props: +{add_props} added, -{del_props} removed")

    # 2. layer gids: cells zeroed (Buildings duplicates)
    g_orig = layer_gids_by_name(sem_orig)
    g_walk = layer_gids_by_name(sem_walk)
    removed_cells = 0
    for name, gids_o in g_orig.items():
        gids_w = g_walk[name]
        lyr = layers_by_id[name]
        assert len(gids_o) == len(gids_w)
        for i, (a, b) in enumerate(zip(gids_o, gids_w)):
            if a == b:
                continue
            assert a != 0 and b == 0, f"{name}[{i}] changed {a}->{b} (only zeroing allowed)"
            lyr["tiles"][i // lyr["size"][0]][i % lyr["size"][0]] = None
            removed_cells += 1
    print(f"cells zeroed: {removed_cells}")

    # 3. object diff -> per-tile props
    o_orig = obj_cells_by_layer(sem_orig)
    o_walk = obj_cells_by_layer(sem_walk)
    added_tile_props = 0
    for layer, cells_w in o_walk.items():
        cells_o = o_orig.get(layer, {})
        lyr = layers_by_id[layer]
        w, h = lyr["size"]
        for (x, y), vals in cells_w.items():
            for name, width, height, props in vals:
                tile = lyr["tiles"][y][x]
                assert tile is not None, f"{layer} ({x},{y}): object on empty tile"
                orig_props = []
                if (x, y) in cells_o:
                    orig_props = list(cells_o[(x, y)][0][3])
                for p in props:
                    if p not in orig_props:
                        assert p not in tile["props"], f"dup prop {p} at {layer}({x},{y})"
                        tile["props"].append(p)
                        added_tile_props += 1
        # no objects may disappear or change in-place
        for (x, y), vals in cells_o.items():
            assert (x, y) in cells_w, f"object at {layer}({x},{y}) removed"
            assert vals == cells_w[(x, y)], f"object at {layer}({x},{y}) changed"
    print(f"tile position props added: {added_tile_props}")

    # ---- serialize & wrap --------------------------------------------------
    new_tbin = serialize_tbin(m)
    out = build_xnb(readers, tide_head, new_tbin)
    DST_XNB.write_bytes(out)
    print(f"wrote {DST_XNB} ({len(out)} bytes; tBIN {len(new_tbin)})")

    # ---- validate the produced XNB end-to-end ------------------------------
    data = DST_XNB.read_bytes()
    assert data[:3] == b"XNB" and data[3:6] == b"w\x05\x01", "bad header"
    xnb_len = struct.unpack_from("<i", data, 6)[0]
    if xnb_len != len(data):
        problems.append(f"xnbLength {xnb_len} != {len(data)}")

    # rebuild logical content and convert to TMX
    body = data[10:]
    tbin_at = body.find(b"tBIN")
    assert tbin_at >= 6
    plen = struct.unpack_from("<i", body, tbin_at - 4)[0]
    if plen != len(body) - tbin_at:
        problems.append(f"payload length {plen} != {len(body) - tbin_at}")
    content = data[10:]  # readers + tide head + payload (uncompressed content)
    xml_bytes, m_check = convert(content)
    root_check = ET.fromstring(xml_bytes)
    sem_check = tmx_semantics(root_check)
    final_diffs = sem_diff(sem_check, sem_walk)
    if final_diffs:
        problems.append("re-converted XNB TMX != walkable/Farm.tmx:")
        problems.extend("  " + d for d in final_diffs)
    else:
        print("re-converted XNB == walkable/Farm.tmx (semantics): OK")

    # reader table unchanged
    if content[:tbin_at - 6] != readers:
        problems.append("reader table changed")
    if data[10:10 + len(readers)] != bytes(readers):
        problems.append("reader region mismatch")

    if problems:
        print("VALIDATION FAILED:")
        for p in problems:
            print("  -", p)
        return 1
    print("validation: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
