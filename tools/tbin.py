#!/usr/bin/env python3
"""TBin (tIDE binary map) parser/writer — matches xTile FormatTide / Tiled tbin plugin."""
import struct

MAGIC = b"tBIN10"

# PropertyValue types (from TbinFormat / PropertyValue.hpp)
T_BOOL, T_INT, T_FLOAT, T_STRING = 0, 1, 2, 3


class Reader:
    def __init__(self, data: bytes):
        self.d = data
        self.o = 0

    def i8(self):
        v = self.d[self.o]
        self.o += 1
        return v

    def i32(self):
        v = struct.unpack_from("<i", self.d, self.o)[0]
        self.o += 4
        return v

    def f32(self):
        v = struct.unpack_from("<f", self.d, self.o)[0]
        self.o += 4
        return v

    def s(self):
        n = self.i32()
        v = self.d[self.o:self.o + n]
        self.o += n
        return v.decode("utf-8")


class Writer:
    def __init__(self):
        self.buf = bytearray()

    def i8(self, v):
        self.buf += struct.pack("<B", v & 0xFF)

    def i32(self, v):
        self.buf += struct.pack("<i", v)

    def f32(self, v):
        self.buf += struct.pack("<f", v)

    def s(self, v):
        b = v.encode("utf-8")
        self.i32(len(b))
        self.buf += b


class Properties(dict):
    """key -> (type, value)"""
    def __getitem__(self, k):
        return super().__getitem__(k)


def read_props(r: Reader):
    props = Properties()
    for _ in range(r.i32()):
        key = r.s()
        ptype = r.i8()
        if ptype == T_BOOL:
            val = r.i8() > 0
        elif ptype == T_INT:
            val = r.i32()
        elif ptype == T_FLOAT:
            val = r.f32()
        elif ptype == T_STRING:
            val = r.s()
        else:
            raise ValueError(f"bad property type {ptype} for {key!r}")
        props[key] = (ptype, val)
    return props


def write_props(w: Writer, props):
    w.i32(len(props))
    for key, (ptype, val) in props.items():
        w.s(key)
        w.i8(ptype)
        if ptype == T_BOOL:
            w.i8(1 if val else 0)
        elif ptype == T_INT:
            w.i32(val)
        elif ptype == T_FLOAT:
            w.f32(val)
        elif ptype == T_STRING:
            w.s(val)
        else:
            raise ValueError(f"bad property type {ptype}")


class StaticTile:
    __slots__ = ("sheet", "index", "blend", "props")

    def __init__(self, sheet="", index=-1, blend=0, props=None):
        self.sheet, self.index, self.blend = sheet, index, blend
        self.props = props if props is not None else Properties()


class AnimatedTile:
    __slots__ = ("sheet", "interval", "frames", "props")

    def __init__(self, sheet="", interval=0, frames=None, props=None):
        self.sheet = sheet  # outer current-tilesheet state (for the 'T' marker)
        self.interval = interval
        self.frames = frames if frames is not None else []
        self.props = props if props is not None else Properties()


class Layer:
    __slots__ = ("id", "visible", "desc", "size", "tile_size", "props", "tiles")

    def __init__(self):
        self.id = ""
        self.visible = True
        self.desc = ""
        self.size = (0, 0)
        self.tile_size = (16, 16)
        self.props = Properties()
        self.tiles = []  # list len w*h; entries: None | StaticTile | AnimatedTile


class TileSheet:
    __slots__ = ("id", "desc", "image", "sheet_size", "tile_size", "margin", "spacing", "props")

    def __init__(self):
        self.id = ""
        self.desc = ""
        self.image = ""
        self.sheet_size = (0, 0)
        self.tile_size = (16, 16)
        self.margin = (0, 0)
        self.spacing = (0, 0)
        self.props = Properties()


class Map:
    def __init__(self):
        self.id = ""
        self.desc = ""
        self.props = Properties()
        self.tilesheets = []
        self.layers = []


def read_tile(r: Reader, cur_sheet):
    static_index = r.i32()
    blend = r.i8()
    props = read_props(r)
    return StaticTile(cur_sheet, static_index, blend, props)


def write_tile(w: Writer, tile: StaticTile):
    w.i32(tile.index)
    w.i8(tile.blend)
    write_props(w, tile.props)


def read_animated_tile(r: Reader):
    interval = r.i32()
    frame_count = r.i32()
    cur = ""
    frames = []
    i = 0
    while i < frame_count:
        c = chr(r.i8())
        if c == "T":
            cur = r.s()
        elif c == "S":
            frames.append(read_tile(r, cur))
            i += 1
        else:
            raise ValueError(f"bad animated tile marker {c!r}")
    props = read_props(r)
    return AnimatedTile("", interval, frames, props)


def write_animated_tile(w: Writer, tile: AnimatedTile):
    w.i32(tile.interval)
    w.i32(len(tile.frames))
    cur = ""
    for f in tile.frames:
        if f.sheet != cur:
            w.i8(ord("T"))
            w.s(f.sheet)
            cur = f.sheet
        w.i8(ord("S"))
        write_tile(w, f)
    write_props(w, tile.props)


def read_layer(r: Reader) -> Layer:
    layer = Layer()
    layer.id = r.s()
    layer.visible = r.i8() > 0
    layer.desc = r.s()
    layer.size = (r.i32(), r.i32())
    layer.tile_size = (r.i32(), r.i32())
    layer.props = read_props(r)
    w, h = layer.size
    layer.tiles = [None] * (w * h)
    cur_sheet = ""
    for iy in range(h):
        ix = 0
        while ix < w:
            c = chr(r.i8())
            if c == "N":
                ix += r.i32()
            elif c == "S":
                layer.tiles[ix + iy * w] = read_tile(r, cur_sheet)
                ix += 1
            elif c == "A":
                anim = read_animated_tile(r)
                anim.sheet = cur_sheet
                layer.tiles[ix + iy * w] = anim
                ix += 1
            elif c == "T":
                cur_sheet = r.s()
            else:
                raise ValueError(f"bad tile marker {c!r} in layer {layer.id}")
    return layer


def write_layer(w: Writer, layer: Layer):
    w.s(layer.id)
    w.i8(1 if layer.visible else 0)
    w.s(layer.desc)
    w.i32(layer.size[0])
    w.i32(layer.size[1])
    w.i32(layer.tile_size[0])
    w.i32(layer.tile_size[1])
    write_props(w, layer.props)
    W, H = layer.size
    cur_sheet = ""
    for iy in range(H):
        nulls = 0
        for ix in range(W):
            tile = layer.tiles[ix + iy * W]
            if tile is None:
                nulls += 1
                continue
            if nulls > 0:
                w.i8(ord("N"))
                w.i32(nulls)
                nulls = 0
            sheet = tile.sheet
            if sheet != cur_sheet:
                w.i8(ord("T"))
                w.s(sheet)
                cur_sheet = sheet
            if isinstance(tile, StaticTile):
                w.i8(ord("S"))
                write_tile(w, tile)
            else:
                w.i8(ord("A"))
                write_animated_tile(w, tile)
        if nulls > 0:
            w.i8(ord("N"))
            w.i32(nulls)


def parse(data: bytes) -> Map:
    r = Reader(data)
    if data[:6] != MAGIC:
        raise ValueError("not a tbin file")
    r.o = 6
    m = Map()
    m.id = r.s()
    m.desc = r.s()
    m.props = read_props(r)
    for _ in range(r.i32()):
        ts = TileSheet()
        ts.id = r.s()
        ts.desc = r.s()
        ts.image = r.s()
        ts.sheet_size = (r.i32(), r.i32())
        ts.tile_size = (r.i32(), r.i32())
        ts.margin = (r.i32(), r.i32())
        ts.spacing = (r.i32(), r.i32())
        ts.props = read_props(r)
        m.tilesheets.append(ts)
    for _ in range(r.i32()):
        m.layers.append(read_layer(r))
    if r.o != len(data):
        raise ValueError(f"trailing bytes: at {r.o}/{len(data)}")
    return m


def serialize(m: Map) -> bytes:
    w = Writer()
    w.buf += MAGIC
    w.s(m.id)
    w.s(m.desc)
    write_props(w, m.props)
    w.i32(len(m.tilesheets))
    for ts in m.tilesheets:
        w.s(ts.id)
        w.s(ts.desc)
        w.s(ts.image)
        w.i32(ts.sheet_size[0]); w.i32(ts.sheet_size[1])
        w.i32(ts.tile_size[0]); w.i32(ts.tile_size[1])
        w.i32(ts.margin[0]); w.i32(ts.margin[1])
        w.i32(ts.spacing[0]); w.i32(ts.spacing[1])
        write_props(w, ts.props)
    w.i32(len(m.layers))
    for layer in m.layers:
        write_layer(w, layer)
    return bytes(w.buf)


if __name__ == "__main__":
    import sys
    data = open(sys.argv[1], "rb").read()
    m = parse(data)
    out = serialize(m)
    print(f"parsed OK: {len(m.tilesheets)} tilesheets, {len(m.layers)} layers, "
          f"{len(m.props)} map props")
    print(f"round-trip: {'IDENTICAL' if out == data else 'DIFFERS!'} "
          f"({len(out)} vs {len(data)} bytes)")
