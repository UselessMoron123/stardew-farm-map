#!/usr/bin/env python3
"""
Rebuild the standard Farm map:
  * perfectly square, fully-clean farmable interior (uniform plain grass)
  * straight border walls with functional gates (BusStop E/W, Forest S, cave, greenhouse)
  * all ponds removed; a new small pond outside the square (south-west) behind a
    gap in the wall, so water stays reachable for fishing/crab pots
  * tidy staggered tree rows "behind the fence" (outside the west & east walls)
  * debris tokens (weeds/rocks/twigs/stumps/logs/boulders/bushes) stripped
Functional things preserved: warps + approaches, cave door, greenhouse approach,
farm sign, multiplayer cabin markers (+Order props), grass-spawn init token.
"""
import sys, copy
sys.path.insert(0, 'tools')
from tbin import parse, serialize, StaticTile, AnimatedTile, Properties

SRC = 'work/Farm.tbin'
DST = 'work/Farm_modified.tbin'

MAIN = 'untitled tile sheet'   # spring_outdoorsTileSheet
GRASS = 587                    # plain farm ground tile
HEDGE = 176                    # mossy stone-hedge block (vanilla south border look)
BLOCK = 16                     # invisible blocker used by vanilla on Buildings layer

W = H = None

def main_map():
    return parse(open(SRC, 'rb').read())

def build():
    m = main_map()
    L = {l.id: l for l in m.layers}
    W, H = L['Back'].size
    assert (W, H) == (80, 65)

    water_ids = {1186,1187,1188,1211,1212,1213,1227,1228,1229,1230,1231,
                 1237,1238,1239,1240,1241,1242,1243,1244,1245,1246,1247,1248,1249,
                 1252,1253,1254,1255,1256,1263,1264,1265,1266,1267,1268,1269,1270,
                 1271,1272,1273,1274,1277,1278,1279,1280,1281,1297,1298,1299,
                 1302,1303,1304,1305,1306,1322,1323,1324,209,234}
    s2_water = {816,817,820,821,822}|set(range(832,839))|set(range(848,855))|set(range(864,871))|set(range(880,884))
    def is_water(t):
        if t is None or not isinstance(t, StaticTile): return False
        if t.sheet == MAIN and t.index in water_ids: return True
        if t.sheet == 'v16_Outdoors2' and t.index in s2_water: return True
        return False

    # -- basic setters ------------------------------------------------------
    def put(layer, x, y, tile):
        L[layer].tiles[y*W+x] = tile
    def clear(layer, x, y):
        L[layer].tiles[y*W+x] = None
    def grass_at(x, y):
        put('Back', x, y, StaticTile(MAIN, GRASS, 0))
    def wall_at(x, y):
        grass_at(x, y)
        if not (x == 8 and y == 7):          # keep the farm sign tile!
            put('Buildings', x, y, StaticTile(MAIN, BLOCK, 0))

    IX0, IX1, IY0, IY1 = 3, 76, 8, 60       # interior rectangle (inclusive)

    # -- 1) clean interior: uniform grass, wipe every layer -----------------
    cabin_markers = {}                       # preserved Paths tokens
    for y in range(H):
        for x in range(W):
            t = L['Paths'].tiles[y*W+x]
            if t is not None and isinstance(t, StaticTile) and t.sheet == 'Paths' \
               and t.index in (29, 30):
                cabin_markers[(x, y)] = t    # multiplayer cabin markers + Order props
    for y in range(IY0, IY1+1):
        for x in range(IX0, IX1+1):
            grass_at(x, y)
            clear('Buildings', x, y)
            clear('Front', x, y)
            clear('AlwaysFront', x, y)
            clear('AlwaysFront2', x, y)
            clear('Paths', x, y)
    for (x, y), t in cabin_markers.items():
        L['Paths'].tiles[y*W+x] = t

    # -- 2) flatten west bite (mountain) + outside strips -------------------
    for x, y in [(0, y) for y in range(22, 35)] + [(1, y) for y in range(22, 35)]:
        grass_at(x, y); clear('Buildings', x, y); clear('Front', x, y); clear('AlwaysFront', x, y)
    for y in range(8, 62):                   # west strip behind wall
        for x in (0, 1):
            grass_at(x, y); clear('Buildings', x, y); clear('Front', x, y); clear('AlwaysFront', x, y)
    for y in range(8, 62):                   # east strip behind wall
        for x in (78, 79):
            grass_at(x, y); clear('Buildings', x, y); clear('Front', x, y); clear('AlwaysFront', x, y)

    # -- 3) border walls (with gates) ---------------------------------------
    # North y=7: KEEP vanilla x3..41 (hill + greenhouse + cave door + corridors —
    #            doors are clicked, frame must stay). New hedge wall only x42..76.
    # South y=61: grass + invisible blocker; gates x5..8 (pond yard), x40..42 (Forest).
    # West x=2 / East x=77: hedge + blocker; east gate y15..18 (BusStop).
    def open_gate(xs, y):
        """Remove only invisible blockers (idx 16) — never visible structures."""
        for x in xs:
            t = L['Buildings'].tiles[y*W+x]
            if t is not None and isinstance(t, StaticTile) and t.index == BLOCK:
                clear('Buildings', x, y)
            if L['Back'].tiles[y*W+x] is None:
                grass_at(x, y)
    def hedge_at(x, y):
        put('Back', x, y, StaticTile(MAIN, HEDGE, 0))
        if not (x == 8 and y == 7):
            put('Buildings', x, y, StaticTile(MAIN, BLOCK, 0))
        clear('Front', x, y); clear('AlwaysFront', x, y)

    for x in range(42, 77):                  # new north hedge wall (was jagged cliff)
        hedge_at(x, 7)
    hedge_at(77, 7)                          # NE corner
    south_wall = list(range(3, 5)) + list(range(9, 40)) + list(range(43, 77))
    for x in south_wall:
        wall_at(x, 61)
    for x in range(5, 9):                    # pond-yard gate (fresh grass floor)
        grass_at(x, 61); clear('Buildings', x, 61); clear('Front', x, 61); clear('AlwaysFront', x, 61)
    open_gate((40, 41, 42), 61)              # Forest corridor
    for x in (40, 41, 42):
        clear('Front', x, 61); clear('AlwaysFront', x, 61)
    for y in range(8, 62): hedge_at(2, y)    # west wall
    for y in list(range(8, 15)) + list(range(19, 62)): hedge_at(77, y)   # east wall
    for y in range(15, 19):                  # east gate (BusStop)
        clear('Buildings', 77, y); clear('Front', 77, y); clear('AlwaysFront', 77, y)
        if L['Back'].tiles[y*W+77] is None: grass_at(77, y)

    # -- 4) pond yard outside the south wall --------------------------------
    # yard x4..22, y62..64; pond water x8..16, y62..64; wall gate x5..8 above
    # Forest corridor continues south at x40..42 (warp tiles at y65)
    POND = 'untitled tile sheet'
    top, mid, bot = [1227]+[1253]*7+[1230], [1266]+[1246]*7+[1271], [1280]+[1298]*7+[1281]
    for row, yy in ((top, 62), (mid, 63), (bot, 64)):
        for i, xx in enumerate(range(8, 17)):
            put('Back', xx, yy, StaticTile(POND, row[i], 0))
    for y in range(62, 65):
        for x in range(4, 23):               # yard
            clear('Buildings', x, y); clear('Front', x, y); clear('AlwaysFront', x, y)
            if not (8 <= x <= 16): grass_at(x, y)
        for x in (40, 41, 42):               # forest corridor extension
            clear('Buildings', x, y); clear('Front', x, y); clear('AlwaysFront', x, y)
            if L['Back'].tiles[y*W+x] is None: grass_at(x, y)
    # guards: keep the player out of the void / off the outside strips
    for y in range(62, 65):
        for x in list(range(0, 4)) + list(range(23, 40)) + list(range(43, 80)):
            t = L['Buildings'].tiles[y*W+x]
            if t is None:
                put('Buildings', x, y, StaticTile(MAIN, BLOCK, 0))
    for y in range(0, 7):                    # guard right of the north corridor
        for x in range(42, 46):
            t = L['Buildings'].tiles[y*W+x]
            if t is None:
                put('Buildings', x, y, StaticTile(MAIN, BLOCK, 0))
    # remove the little vanilla pond bottom-right (cosmetic, outside square)
    for y in (63, 64):
        for x in range(73, 79):
            if is_water(L['Back'].tiles[y*W+x]): grass_at(x, y)

    # -- 5) tidy tree rows behind the fence (outside west/east walls) -------
    cycle = [9, 10, 11]                      # oak, maple, pine
    n = 0
    for y in range(8, 62):
        for x in ((0, 1) if y % 2 == 0 else (1, 0)):
            t = StaticTile('Paths', cycle[n % 3], 0)
            L['Paths'].tiles[y*W+x] = t
            n += 1
        t = StaticTile('Paths', cycle[n % 3], 0)
        L['Paths'].tiles[y*W + (79 if y % 2 == 0 else 78)] = t
        n += 1
    # grass-init token (game requires >=1 index-22 on Paths of farm maps)
    L['Paths'].tiles[60*W+1] = StaticTile('Paths', 22, 0)

    return m, L


# -- validation -------------------------------------------------------------
def validate(m):
    L = {l.id: l for l in m.layers}
    W, H = L['Back'].size
    errors = []
    water_ids = {1186,1187,1188,1211,1212,1213,1227,1228,1229,1230,1231,
                 1237,1238,1239,1240,1241,1242,1243,1244,1245,1246,1247,1248,1249,
                 1252,1253,1254,1255,1256,1263,1264,1265,1266,1267,1268,1269,1270,
                 1271,1272,1273,1274,1277,1278,1279,1280,1281,1297,1298,1299,
                 1302,1303,1304,1305,1306,1322,1323,1324,209,234}
    s2_water = {816,817,820,821,822}|set(range(832,839))|set(range(848,855))|set(range(864,871))|set(range(880,884))
    def is_water(t):
        if t is None or not isinstance(t, StaticTile): return False
        if t.sheet == 'untitled tile sheet' and t.index in water_ids: return True
        if t.sheet == 'v16_Outdoors2' and t.index in s2_water: return True
        return False
    def blocked(x, y):
        if not (0 <= x < W and 0 <= y < H): return True
        if L['Buildings'].tiles[y*W+x] is not None: return True
        return is_water(L['Back'].tiles[y*W+x])
    def need_open(name, pts):
        for x, y in pts:
            if blocked(x, y): errors.append(f"{name}: ({x},{y}) is blocked")
    def need_blocked(name, pts):
        for x, y in pts:
            if not blocked(x, y): errors.append(f"{name}: ({x},{y}) is OPEN (should block)")

    # warp corridors
    need_open("N corridor", [(40, y) for y in range(0, 9)] + [(41, y) for y in range(0, 9)])
    need_open("E gate",    [(x, y) for y in range(15, 19) for x in (77, 78, 79)])
    need_open("S corridor", [(x, y) for y in range(58, 65) for x in (40, 41, 42)])
    # cave door approach: single open column x34 (door frame posts at x33/x35 stay)
    # row y7 x36-39 is the vanilla cliff face (not walkable); the path runs along y8
    need_open("cave approach", [(34, y) for y in (5, 6, 7, 8)] + [(40,7),(41,7),
                                                                 (33,8),(34,8),(35,8)] +
              [(x, 8) for x in range(36, 40)])
    bt = L['Back'].tiles[5*W+34]
    if not (bt and isinstance(bt, StaticTile) and bt.index == 217 and
            bt.props.get('NoSpawn') == (3, 'All') and bt.props.get('NoFurniture') == (3, 'total')):
        errors.append("cave door tile (34,5) was altered")
    door_frame = [(33,5),(35,5),(33,6),(35,6),(33,7),(35,7)]
    need_blocked("cave door frame", door_frame)
    # greenhouse approach row stays walkable; cliff/door tiles untouched
    need_open("greenhouse approach", [(x, 8) for x in range(19, 24)])
    # pond route
    need_open("pond gate", [(x, 61) for x in range(5, 9)])
    need_open("pond shore", [(x, y) for y in (62, 63, 64) for x in list(range(4, 8)) + list(range(17, 23))])
    for x, y in [(x, y) for y in (62, 63, 64) for x in range(8, 17)]:
        t = L['Back'].tiles[y*W+x]
        if not is_water(t): errors.append(f"pond: ({x},{y}) is not water")
    # farm sign intact
    st = L['Buildings'].tiles[7*W+8]
    if not (st and isinstance(st, StaticTile) and st.index == 1957 and
            st.props.get('Action') == (3, 'Message "Farm.1"')):
        errors.append("farm sign (8,7) was altered")
    # walls continuous
    north_wall = list(range(42, 77))
    south_wall = list(range(3, 5)) + list(range(9, 40)) + list(range(43, 77))
    need_blocked("N wall", [(x, 7) for x in north_wall])
    need_blocked("S wall", [(x, 61) for x in south_wall])
    need_blocked("W wall", [(2, y) for y in range(8, 62)])
    need_blocked("E wall", [(77, y) for y in list(range(8, 15)) + list(range(19, 62))])
    # guards around the outside strips
    need_blocked("yard/corridor guards", [(x, y) for y in (62, 63, 64)
                                          for x in list(range(0, 4)) + list(range(23, 40)) + list(range(43, 80))])
    # interior perfectly clean
    for y in range(8, 61):
        for x in range(3, 77):
            b = L['Back'].tiles[y*W+x]
            if not (b and isinstance(b, StaticTile) and b.sheet == 'untitled tile sheet' and b.index == 587):
                errors.append(f"interior Back ({x},{y}) is not plain grass")
            for ln in ('Buildings', 'Front', 'AlwaysFront', 'AlwaysFront2'):
                if L[ln].tiles[y*W+x] is not None:
                    errors.append(f"interior {ln} ({x},{y}) not empty")
            p = L['Paths'].tiles[y*W+x]
            if p is not None and not (isinstance(p, StaticTile) and p.sheet == 'Paths' and p.index in (29, 30)):
                errors.append(f"interior Paths ({x},{y}) unexpected token")
    # grass-init + cabin markers
    tokens = [(x, y, t.index) for y in range(H) for x in range(W)
              for t in [L['Paths'].tiles[y*W+x]]
              if t is not None and isinstance(t, StaticTile) and t.sheet == 'Paths']
    if not any(i == 22 for _, _, i in tokens): errors.append("no Paths idx-22 grass-init token")
    n_cabins = sum(1 for _, _, i in tokens if i in (29, 30))
    if n_cabins != 14: errors.append(f"cabin markers: {n_cabins} != 14")
    n_trees = sum(1 for _, _, i in tokens if i in (9, 10, 11))
    print(f"  tokens: {n_cabins} cabin markers, {n_trees} trees")
    # warps untouched
    if m.props['Warp'] != (3, ('80 15 BusStop 11 23 80 18 BusStop 11 24 80 16 BusStop 11 23 '
                               '80 17 BusStop 11 23 40 65 Forest 68 0 41 65 Forest 68 0 '
                               '42 65 Forest 68 0 40 -1 Backwoods 14 39 41 -1 Backwoods 14 39 '
                               '34 5 FarmCave 8 11')):
        errors.append("Warp property changed")
    return errors


if __name__ == '__main__':
    m, _ = build()
    print("validating...")
    errs = validate(m)
    if errs:
        print(f"{len(errs)} PROBLEMS:")
        for e in errs[:40]: print("  -", e)
        sys.exit(1)
    print("  all checks passed")
    data = serialize(m)
    open(DST, 'wb').write(data)
    # parse the written file again as a sanity check
    m2 = parse(open(DST, 'rb').read())
    assert len(serialize(m2)) == len(data)
    print(f"wrote {DST} ({len(data)} bytes)")
