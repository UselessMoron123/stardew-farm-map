#!/usr/bin/env python3
"""Schematic renderer for Farm tbins (before/after comparison)."""
import sys
sys.path.insert(0, 'tools')
from tbin import parse, StaticTile, AnimatedTile
from PIL import Image, ImageDraw

MAIN = 'untitled tile sheet'
WATER = {1186,1187,1188,1211,1212,1213,1227,1228,1229,1230,1231,1237,1238,1239,
         1240,1241,1242,1243,1244,1245,1246,1247,1248,1249,1252,1253,1254,1255,1256,
         1263,1264,1265,1266,1267,1268,1269,1270,1271,1272,1273,1274,1277,1278,1279,
         1280,1281,1297,1298,1299,1302,1303,1304,1305,1306,1322,1323,1324,209,234}
S2_WATER = {816,817,820,821,822}|set(range(832,839))|set(range(848,855))|set(range(864,871))|set(range(880,884))
LAWN = {351, 300, 304, 305, 329, 352, 354, 355}
T = 10  # px per tile


def classify(path):
    m = parse(open(path, 'rb').read())
    L = {l.id: l for l in m.layers}
    W, H = L['Back'].size
    sheet = {t.id: t for t in m.tilesheets}
    grass_idx = set()
    for k, v in sheet[MAIN].props.items():
        if k.startswith('@TileIndex@') and k.endswith('@Type') and v[1] == 'Grass':
            grass_idx.add(int(k.split('@')[2]))
    grid = []
    for y in range(H):
        row = []
        for x in range(W):
            b = L['Back'].tiles[y * W + x]
            bld = L['Buildings'].tiles[y * W + x]
            p = L['Paths'].tiles[y * W + x]
            c = 'void'
            if b is not None:
                c = 'floor'
                if isinstance(b, StaticTile):
                    if b.sheet == MAIN and b.index in WATER:
                        c = 'water'
                    elif b.sheet == 'v16_Outdoors2' and b.index in S2_WATER:
                        c = 'water'
                    elif b.sheet == MAIN and (b.index in LAWN or b.index in grass_idx):
                        c = 'grass'
                    elif b.sheet == MAIN and b.index == 587:
                        c = 'dirt'
                    elif b.sheet == MAIN and b.index == 176:
                        c = 'cliff'
            if bld is not None and isinstance(bld, StaticTile):
                if bld.sheet == MAIN and bld.index == 16:
                    c = 'block'
                elif bld.sheet == MAIN and bld.index == 1957:
                    c = 'sign'
                elif bld.sheet == MAIN and bld.index in (259, 898):
                    pass                      # pond decor (lily/rock) over water
                else:
                    c = 'solid'
            if p is not None and isinstance(p, StaticTile) and p.sheet == 'Paths':
                if p.index in (9, 10, 11, 12, 23, 31, 32):
                    c = 'tree'
                elif p.index in (29, 30):
                    c = 'cabin'
                elif p.index in (22, 36):
                    c = 'ginit'
                elif p.index in (13, 14, 15, 16, 17, 18, 19, 20, 21):
                    c = 'debris'
                elif p.index in (24, 25, 26):
                    c = 'bush'
            row.append(c)
        grid.append(row)
    return grid


COLORS = {
    'void':   (26, 26, 36),
    'water':  (63, 127, 191),
    'grass':  (143, 191, 111),
    'dirt':   (214, 176, 92),
    'floor':  (203, 178, 106),
    'cliff':  (120, 100, 70),
    'block':  (90, 90, 100),
    'solid':  (74, 59, 42),
    'tree':   (34, 120, 62),
    'cabin':  (204, 102, 204),
    'ginit':  (200, 235, 160),
    'debris': (150, 130, 110),
    'bush':   (90, 160, 80),
    'sign':   (220, 60, 60),
}


def render(path, out, label):
    grid = classify(path)
    H, W = len(grid), len(grid[0])
    img = Image.new('RGB', (W * T, H * T))
    d = ImageDraw.Draw(img)
    for y in range(H):
        for x in range(W):
            c = COLORS[grid[y][x]]
            d.rectangle([x * T, y * T, x * T + T - 1, y * T + T - 1], fill=c)
    for gx in range(0, W, 10):
        d.line([(gx * T, 0), (gx * T, H * T)], fill=(255, 255, 255, 30), width=1)
    for gy in range(0, H, 10):
        d.line([(0, gy * T), (W * T, gy * T)], fill=(255, 255, 255, 30), width=1)
    img.save(out)
    print(f"{label}: {out}  ({W}x{H} tiles)")
    return img


if __name__ == '__main__':
    render(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else '')
