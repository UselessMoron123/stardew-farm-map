"""Convert a Stardew Valley tBIN map (inside an XNB) to a Content-Patcher-ready TMX.

Format references:
 - tbin layout: Tiled's tbin plugin (src/plugins/tbin/tbin/Map.cpp, MIT)
 - TMX conventions: mirrors the shipped "Clean Map - Standard Farm" TMX
   (map/layer/objectgroup/tileset structure known to load via Content Patcher)
"""
from __future__ import annotations

import base64
import struct
import zlib
import xml.etree.ElementTree as ET
from collections import defaultdict


# ------------------------------------------------------------------ reading
class Reader:
    def __init__(self, data: bytes, pos: int = 0):
        self.data = data
        self.pos = pos

    def i32(self) -> int:
        v = struct.unpack_from("<i", self.data, self.pos)[0]
        self.pos += 4
        return v

    def u8(self) -> int:
        v = self.data[self.pos]
        self.pos += 1
        return v

    def s(self) -> str:
        n = self.i32()
        v = self.data[self.pos:self.pos + n].decode("utf-8")
        self.pos += n
        return v

    def eof(self) -> bool:
        return self.pos >= len(self.data)


def read_props(r: Reader) -> list:
    out = []
    for _ in range(r.i32()):
        key = r.s()
        ptype = r.u8()
        if ptype == 0:
            val = r.u8() > 0
        elif ptype == 1:
            val = r.i32()
        elif ptype == 2:
            val = struct.unpack_from("<f", r.data, r.pos)[0]
            r.pos += 4
        elif ptype == 3:
            val = r.s()
        else:
            raise ValueError(f"bad property type {ptype} for {key!r}")
        out.append((key, ptype, val))
    return out


def read_tile(r: Reader, sheet: str) -> dict:
    """One 'S' static tile: tileIndex, blendMode, props."""
    return {
        "sheet": sheet,
        "index": r.i32(),
        "blend": r.u8(),
        "props": read_props(r),
    }


def read_animated_tile(r: Reader) -> dict:
    """One 'A' animated tile. Note: 'T' sheet switches don't count toward
    frameCount — only 'S' frames do (matches tbin's reference reader)."""
    interval = r.i32()
    frame_count = r.i32()
    frames = []
    sheet = ""
    while len(frames) < frame_count:
        c = chr(r.u8())
        if c == "T":
            sheet = r.s()
        elif c == "S":
            frames.append(read_tile(r, sheet))
        else:
            raise ValueError(f"bad animated frame marker {c!r}")
    return {"animated": True, "interval": interval, "frames": frames,
            "props": read_props(r)}


def parse_tbin(data: bytes) -> dict:
    if data[:6] != b"tBIN10":
        raise ValueError("not a tBIN 1.0 file")
    r = Reader(data, 6)
    m = {"id": r.s(), "desc": r.s(), "props": read_props(r)}
    sheets = []
    for _ in range(r.i32()):
        sheets.append({
            "id": r.s(), "desc": r.s(), "image": r.s(),
            "sheet_size": (r.i32(), r.i32()),
            "tile_size": (r.i32(), r.i32()),
            "margin": (r.i32(), r.i32()),
            "spacing": (r.i32(), r.i32()),
            "props": read_props(r),
        })
    m["sheets"] = sheets
    layers = []
    for _ in range(r.i32()):
        layer = {
            "id": r.s(),
            "visible": r.u8() > 0,
            "desc": r.s(),
            "size": (r.i32(), r.i32()),
            "tile_size": (r.i32(), r.i32()),
            "props": read_props(r),
        }
        w, h = layer["size"]
        tiles = [[None] * w for _ in range(h)]
        sheet = ""
        for iy in range(h):
            ix = 0
            while ix < w:
                c = chr(r.u8())
                if c == "N":
                    ix += r.i32()
                elif c == "S":
                    tiles[iy][ix] = read_tile(r, sheet)
                    ix += 1
                elif c == "A":
                    tiles[iy][ix] = read_animated_tile(r)
                    ix += 1
                elif c == "T":
                    sheet = r.s()
                else:
                    raise ValueError(f"bad tile marker {c!r} at {layer['id']} ({ix},{iy})")
            if ix != w:
                raise ValueError(f"row overrun in layer {layer['id']}: {ix} != {w}")
        layer["tiles"] = tiles
        layers.append(layer)
    m["layers"] = layers
    return m


# ------------------------------------------------------------------ writing
def _fmt_props(props, parent, indent="   "):
    """Write <properties>; bool -> type="bool", int/float typed, str plain
    (matches the Clean Map TMX conventions)."""
    if not props:
        return
    pe = ET.SubElement(parent, "properties")
    for key, ptype, val in props:
        e = ET.SubElement(pe, "property", {"name": key})
        if ptype == 0:
            e.set("type", "bool")
            e.set("value", "true" if val else "false")
        elif ptype == 1:
            e.set("type", "int")
            e.set("value", str(val))
        elif ptype == 2:
            e.set("type", "float")
            e.set("value", repr(val))
        else:
            e.set("value", val)


def _indent(elem, level=0, spacing="  "):
    """Pretty-print with Tiled-style indentation."""
    pad = "\n" + spacing * level
    if len(elem):
        if not (elem.text or "").strip():
            elem.text = pad + spacing
        for child in elem:
            _indent(child, level + 1, spacing)
        last = list(elem)[-1]
        if not (last.tail or "").strip():
            last.tail = pad
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = pad


def tbin_to_tmx(m: dict) -> ET.Element:
    sheets = m["sheets"]
    layers = m["layers"]
    w, h = layers[0]["size"]
    for lyr in layers:
        if lyr["size"] != (w, h):
            raise ValueError(f"mixed layer sizes: {lyr['id']} {lyr['size']} vs {(w, h)}")
        if lyr["tile_size"] != layers[0]["tile_size"]:
            raise ValueError(f"mixed tile sizes: {lyr['id']}")
    tw, th = layers[0]["tile_size"]

    # firstgid per sheet, assigned in file order (ascending, like Tiled)
    firstgid = {}
    gid = 1
    for ts in sheets:
        firstgid[ts["id"]] = gid
        gid += ts["sheet_size"][0] * ts["sheet_size"][1]

    root = ET.Element("map", {
        "version": "1.10",
        "tiledversion": "1.11.2",
        "orientation": "orthogonal",
        "renderorder": "right-down",
        "width": str(w),
        "height": str(h),
        "tilewidth": str(tw),
        "tileheight": str(th),
        "infinite": "0",
        "nextlayerid": str(2 * len(layers) + 1),
    })
    _fmt_props(m["props"], root)

    for ts in sheets:
        cols, rows = ts["sheet_size"]
        tsn = ET.SubElement(root, "tileset", {
            "firstgid": str(firstgid[ts["id"]]),
            "name": ts["id"],
            "tilewidth": str(ts["tile_size"][0]),
            "tileheight": str(ts["tile_size"][1]),
            "tilecount": str(cols * rows),
            "columns": str(cols),
        })
        if ts["margin"] != (0, 0):
            tsn.set("margin", str(ts["margin"][0]))
        if ts["spacing"] != (0, 0):
            tsn.set("spacing", str(ts["spacing"][0]))
        src = ts["image"]
        if not src.lower().endswith(".png"):
            src += ".png"
        ET.SubElement(tsn, "image", {
            "source": src,
            "width": str(cols * ts["tile_size"][0]),
            "height": str(rows * ts["tile_size"][1]),
        })
        # non-@ props stay on the tileset; @TileIndex@N@X become tile entries
        plain, per_tile = [], defaultdict(list)
        for key, ptype, val in ts["props"]:
            parts = key.split("@")
            if len(parts) == 4 and parts[0] == "" and parts[1] == "TileIndex":
                per_tile[int(parts[2])].append((parts[3], ptype, val))
            else:
                plain.append((key, ptype, val))
        _fmt_props(plain, tsn, indent="    ")
        for tid in sorted(per_tile):
            tile_el = ET.SubElement(tsn, "tile", {"id": str(tid)})
            _fmt_props(per_tile[tid], tile_el, indent="      ")

    next_object_id = 1
    # (sheet, first-frame-local-id) -> (duration, [frame ids]) for TMX
    # <tileset><tile><animation> entries
    animations = {}

    for i, lyr in enumerate(layers):
        layer_el = ET.SubElement(root, "layer", {
            "id": str(2 * i + 1),
            "name": lyr["id"],
            "width": str(w),
            "height": str(h),
        })
        if not lyr["visible"]:
            layer_el.set("visible", "0")
        _fmt_props(lyr["props"], layer_el)

        gids = bytearray()
        objects = []
        for iy, row in enumerate(lyr["tiles"]):
            for ix, tile in enumerate(row):
                if tile is None:
                    gids += struct.pack("<I", 0)
                    continue
                if tile.get("animated"):
                    frames = tile["frames"]
                    sheets_used = {f["sheet"] for f in frames}
                    if len(sheets_used) != 1:
                        raise ValueError(
                            f"animation spans tilesheets {sheets_used} at {ix},{iy}")
                    sheet = frames[0]["sheet"]
                    frame_ids = [f["index"] for f in frames]
                    key = (sheet, frame_ids[0])
                    prev = animations.setdefault(key, (tile["interval"], frame_ids))
                    if prev != (tile["interval"], frame_ids):
                        raise ValueError(f"conflicting animation for {key}")
                    gids += struct.pack("<I", firstgid[sheet] + frame_ids[0])
                    props = tile["props"]
                    blend = frames[0]["blend"]
                else:
                    sheet = tile["sheet"]
                    if sheet not in firstgid:
                        raise ValueError(f"unknown tilesheet {sheet!r} at {ix},{iy}")
                    gids += struct.pack("<I", firstgid[sheet] + tile["index"])
                    props = tile["props"]
                    blend = tile["blend"]
                if props:
                    objects.append((ix, iy, props, blend))

        data_el = ET.SubElement(layer_el, "data", {
            "encoding": "base64",
            "compression": "zlib",
        })
        data_el.text = base64.b64encode(zlib.compress(bytes(gids), 9)).decode()

        # per-tile properties -> TileData objects (Clean Map convention)
        og = ET.SubElement(root, "objectgroup", {
            "id": str(2 * i + 2),
            "name": lyr["id"],
        })
        for ix, iy, props, blend in objects:
            if blend:
                props = list(props) + [("__BlendMode", 1, blend)]
            obj = ET.SubElement(og, "object", {
                "id": str(next_object_id),
                "name": "TileData",
                "x": str(ix * tw),
                "y": str(iy * th),
                "width": str(tw),
                "height": str(th),
            })
            next_object_id += 1
            _fmt_props(props, obj)

    # attach collected animations to their first-frame tileset tiles
    by_sheet = defaultdict(list)
    for (sheet, f0), (dur, frames) in animations.items():
        by_sheet[sheet].append((f0, dur, frames))
    for tsn in root.findall("tileset"):
        name = tsn.get("name")
        if name not in by_sheet:
            continue
        tile_els = {int(t.get("id")): t for t in tsn.findall("tile")}
        for f0, dur, frames in sorted(by_sheet[name]):
            tel = tile_els.get(f0)
            if tel is None:
                tel = ET.SubElement(tsn, "tile", {"id": str(f0)})
                tile_els[f0] = tel
            anim = ET.SubElement(tel, "animation")
            for fid in frames:
                ET.SubElement(anim, "frame",
                              {"tileid": str(fid), "duration": str(dur)})
        # keep <tile> children sorted by id (Tiled's usual output order)
        for tel in tsn.findall("tile"):
            tsn.remove(tel)
        for fid in sorted(tile_els):
            tsn.append(tile_els[fid])

    root.set("nextobjectid", str(next_object_id))
    _indent(root)
    return root


def convert(xnb_content: bytes) -> tuple[bytes, dict]:
    """xnb_content = full XNB logical content (reader table + tbin payload)."""
    tbin_at = xnb_content.find(b"tBIN")
    if tbin_at < 0:
        raise ValueError("tBIN payload not found")
    m = parse_tbin(xnb_content[tbin_at:])
    root = tbin_to_tmx(m)
    xml_bytes = ET.tostring(root, encoding="utf-8")
    xml_bytes = b'<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes
    return xml_bytes + b"\n", m


def stats(m: dict) -> dict:
    tiles = 0
    props_tiles = 0
    animated = 0
    blends = set()
    for lyr in m["layers"]:
        for row in lyr["tiles"]:
            for t in row:
                if t is None:
                    continue
                tiles += 1
                if t.get("animated"):
                    animated += 1
                    if t["props"]:
                        props_tiles += 1
                else:
                    blends.add(t["blend"])
                    if t["props"]:
                        props_tiles += 1
    return {
        "layers": [l["id"] for l in m["layers"]],
        "size": m["layers"][0]["size"],
        "sheets": [s["id"] for s in m["sheets"]],
        "map_props": len(m["props"]),
        "non_empty_tiles": tiles,
        "tiles_with_props": props_tiles,
        "animated_tiles": animated,
        "blend_modes": sorted(blends),
    }
