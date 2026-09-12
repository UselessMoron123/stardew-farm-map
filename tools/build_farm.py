#!/usr/bin/env python3
"""
Rebuild the standard Farm map — v2 (feedback round 2026-09-12, screens 295-302).

Changes vs v1:
  * FIELD (x3..76, y9..60 minus the house yard) is uniform yellow sandy soil
    (tile 472, Diggable/Type Dirt) instead of green grass, and carries
    NoSpawn All so weeds/stones/forage/trees no longer respawn on it.
  * HOUSE YARD (x50..77, y6..24) is preserved byte-for-byte from vanilla
    (fences, stone path, patio, flowers, the flower tuft behind the house)
    -> the green rectangle around house / shipping bin / spouse spot,
       with the vanilla fence lines intact and uncut.
    Only player-removable debris tokens are stripped there.
  * NORTH strip (y0..9): trees, bushes, flowers, rocks/stones, weeds,
    pebbles on the north path and sprout variants on the cliff are removed;
    cliff, cave door, shrine, statue ("totem"), sign and corridors kept.
    North path repainted to plain sand (588), cliff-base strip to 562.
  * WEST edge: the grass strip + tree rows are gone; a neat uniform 3-wide
    rock cliff band (x0..2, y8..60) replaces the vanilla mountain jut
    (one same level, no hills). EAST outer column (x78..79) likewise,
    keeping the vanilla BusStop gate and the east fence column at x77.
  * SOUTH edge (y61..64): restored to vanilla (cliff + fence line),
    the half-off-map pond at the SE corner is filled with the same cliff.
  * All ponds removed (no water left on the farm).
  * Debris tokens (weeds/stones/twigs/stumps/bushes/trees) stripped map-wide;
    cabin markers (Paths 29/30 + Order) and grass-init (22) preserved.
Functional things preserved: warps + approaches, cave door, greenhouse,
farm sign, multiplayer cabin markers, grass-init token, tilesheets.
"""
import sys
sys.path.insert(0, 'tools')
from tbin import parse, serialize, StaticTile, AnimatedTile, Properties

SRC = 'work/Farm.tbin'
DST = 'work/Farm_modified.tbin'

MAIN = 'untitled tile sheet'          # spring_outdoorsTileSheet
SAND = 472                            # yellow sandy soil, Diggable / Type Dirt
SAND_PATH = 588                       # plain sand (north path)
SAND_STRIP = 562                      # plain sand (cliff-base strip)
GRASS = 587
ROCK = 176                            # round-boulder cliff face
CLIFFTOP_PLAIN = 175                  # cliff-top without sprouts
BLOCK = 16                            # invisible blocker (Buildings)

# tiles that may NOT be touched on the Buildings layer of the north strip
CLIFF_B = {394, 419, 444, 469, 494, 519, 544, 416, 391, 441, 466, 491, 516,
           541, 446, 447, 448, 467, 468, 492, 493, 517, 518, 542, 543,
           321, 346, 371, 396, 296, 470, 495, 520, 545, 835}
STRUCT_B = {1633, 1634, 1635, 1658, 1660, 1683, 1685, 1708, 1710} | set(range(1906, 1959))
KEEP_B_NORTH = CLIFF_B | STRUCT_B | {BLOCK}
# coordinates whose Front tiles survive the north clean-up (statue + cave frame)
KEEP_FRONT_NORTH = {(48, 3), (48, 5), (33, 5), (35, 5)}

DEBRIS = set(range(9, 22)) | {23, 24, 25, 26, 31, 32}     # Paths tokens to strip
FLOWERS = {3, 4, 5, 28, 29, 30, 53, 54, 55, 78, 79, 80, 103, 104, 105, 101, 126}
# flower tufts sitting in/behind the house yard (deleted on request, screen 299)
TUFT = {(55, 6), (56, 6), (57, 6), (66, 6), (67, 6), (68, 6), (74, 6), (75, 6),
        (55, 7), (56, 7), (57, 7), (67, 7)}
CABIN = {29, 30}
GRASS_INIT = 22

PEBBLE = {512, 645, 618, 566, 565, 591, 838}              # pebbly/rocky sand
SPROUT = {177, 203, 206, 207}                             # cliff-top w/ sprouts

YARD = (50, 77, 6, 24)        # x0,x1,y0,y1  preserved vanilla house yard
FIELD = (3, 76, 9, 60)        # sandy farmable square


def in_rect(x, y, r):
    return r[0] <= x <= r[1] and r[2] <= y <= r[3]


def build():
    m = parse(open(SRC, 'rb').read())
    L = {l.id: l for l in m.layers}
    W, H = L['Back'].size
    assert (W, H) == (80, 65)

    def put(layer, x, y, tile):
        L[layer].tiles[y * W + x] = tile

    def clear(layer, x, y):
        L[layer].tiles[y * W + x] = None

    def get(layer, x, y):
        return L[layer].tiles[y * W + x]

    def idx(t):
        if t is None:
            return None
        return t.frames[0].index if isinstance(t, AnimatedTile) else t.index

    # remember cabin markers before any Paths wipe
    cabins = {}
    for y in range(H):
        for x in range(W):
            t = get('Paths', x, y)
            if t is not None and isinstance(t, StaticTile) and t.sheet == 'Paths' \
               and t.index in CABIN:
                cabins[(x, y)] = t

    # -- 1) sandy farm field ------------------------------------------------
    for y in range(FIELD[2], FIELD[3] + 1):
        for x in range(FIELD[0], FIELD[1] + 1):
            if in_rect(x, y, YARD):
                continue
            t = StaticTile(MAIN, SAND, 0, Properties({'NoSpawn': (3, 'All')}))
            put('Back', x, y, t)
            for ln in ('Buildings', 'Front', 'AlwaysFront', 'AlwaysFront2', 'Paths'):
                clear(ln, x, y)

    # -- 2) house yard: vanilla, minus debris, plus NoSpawn -----------------
    for y in range(YARD[2], YARD[3] + 1):
        for x in range(YARD[0], YARD[1] + 1):
            p = get('Paths', x, y)
            if p is not None and isinstance(p, StaticTile) and p.index in DEBRIS:
                clear('Paths', x, y)
            f = get('Front', x, y)
            if f is not None and (x, y) in TUFT:
                clear('Front', x, y)
            b = get('Back', x, y)
            if b is not None and isinstance(b, StaticTile) and 'NoSpawn' not in b.props:
                b.props['NoSpawn'] = (3, 'All')

    # -- 3) north strip clean-up (y0..9) ------------------------------------
    for y in range(0, 10):
        for x in range(0, 80):
            if in_rect(x, y, YARD):
                continue
            b = get('Back', x, y)
            if b is not None and isinstance(b, StaticTile):
                if b.index in PEBBLE:
                    put('Back', x, y, StaticTile(MAIN, SAND_STRIP, 0))
                elif b.index in SPROUT:
                    put('Back', x, y, StaticTile(MAIN, CLIFFTOP_PLAIN, 0))
            edge = x >= 78                     # NE cliff corner: keep structure
            bl = get('Buildings', x, y)
            if bl is not None and isinstance(bl, StaticTile) \
               and bl.index not in KEEP_B_NORTH and not (edge and y > 3):
                # cliff top stays impassable where decorations were removed
                if y <= 3 and not (x in (40, 41) or x == 34):
                    put('Buildings', x, y, StaticTile(MAIN, BLOCK, 0))
                else:
                    clear('Buildings', x, y)
            f = get('Front', x, y)
            if f is not None and (x, y) not in KEEP_FRONT_NORTH and not (edge and y > 3):
                clear('Front', x, y)
            elif f is not None and edge and 4 <= y <= 9 and isinstance(f, StaticTile) \
                    and f.index in FLOWERS:
                clear('Front', x, y)      # NE corner flowers
            af = get('AlwaysFront', x, y)
            if af is not None and not (33 <= x <= 35 and y <= 5):
                clear('AlwaysFront', x, y)
            p = get('Paths', x, y)
            if p is not None and isinstance(p, StaticTile) and p.index in DEBRIS:
                clear('Paths', x, y)
    # north path + cliff-base strip: plain sand, no pebbles
    for y in range(0, 9):
        for x in (40, 41):
            put('Back', x, y, StaticTile(MAIN, SAND_PATH, 0))
    for x in range(3, 50):
        put('Back', x, 8, StaticTile(MAIN, SAND_STRIP, 0))

    # -- 4) neat uniform cliff bands west / east ----------------------------
    for y in range(8, 61):                     # west: x0..2 rock band
        for x in (0, 1, 2):
            put('Back', x, y, StaticTile(MAIN, ROCK, 0))
            put('Buildings', x, y, StaticTile(MAIN, BLOCK, 0))
            for ln in ('Front', 'AlwaysFront', 'AlwaysFront2', 'Paths'):
                clear(ln, x, y)
    for y in range(10, 61):                    # east outer: x78..79 rock band
        if 15 <= y <= 18:                      # BusStop gate stays open
            continue
        for x in (78, 79):
            put('Back', x, y, StaticTile(MAIN, ROCK, 0))
            put('Buildings', x, y, StaticTile(MAIN, BLOCK, 0))
            for ln in ('Front', 'AlwaysFront', 'AlwaysFront2', 'Paths'):
                clear(ln, x, y)

    # -- 5) south edge: vanilla cliff + fences, pond filled with cliff ------
    for y in range(61, 65):
        for x in range(73, 80):                # SE pond -> continue the cliff
            for ln in ('Back', 'Buildings', 'Front', 'AlwaysFront', 'Paths'):
                src = get(ln, x - 29, y)
                if src is not None and isinstance(src, StaticTile):
                    put(ln, x, y, StaticTile(src.sheet, src.index, src.blend,
                                             Properties(dict(src.props))))
                else:
                    clear(ln, x, y)
            put('Buildings', x, 61, StaticTile(MAIN, BLOCK, 0))   # keep SE shore shut
    for y in range(58, 65):                    # debris strip on south band
        for x in range(0, 80):
            p = get('Paths', x, y)
            if p is not None and isinstance(p, StaticTile) and p.index in DEBRIS:
                clear('Paths', x, y)

    # -- 6) leftover debris anywhere else -----------------------------------
    for y in range(H):
        for x in range(W):
            p = get('Paths', x, y)
            if p is not None and isinstance(p, StaticTile) and p.sheet == 'Paths' \
               and p.index in DEBRIS:
                clear('Paths', x, y)

    # -- 7) re-add cabin markers + grass-init token -------------------------
    for (x, y), t in cabins.items():
        L['Paths'].tiles[y * W + x] = t
    if not any(isinstance(t, StaticTile) and t.sheet == 'Paths' and t.index == GRASS_INIT
               for t in L['Paths'].tiles):
        put('Paths', 5, 59, StaticTile('Paths', GRASS_INIT, 0))
    return m, L


# -- validation -------------------------------------------------------------
def validate(m):
    L = {l.id: l for l in m.layers}
    W, H = L['Back'].size
    V = {l.id: l for l in parse(open(SRC, 'rb').read()).layers}
    errors = []

    def idx(layer, x, y):
        t = L[layer].tiles[y * W + x]
        if t is None:
            return None
        return t.frames[0].index if isinstance(t, AnimatedTile) else t.index

    def vidx(layer, x, y):
        t = V[layer].tiles[y * W + x]
        if t is None:
            return None
        return t.frames[0].index if isinstance(t, AnimatedTile) else t.index

    def blocked(x, y):
        if not (0 <= x < W and 0 <= y < H):
            return True
        return L['Buildings'].tiles[y * W + x] is not None

    def need_open(name, pts):
        for x, y in pts:
            if blocked(x, y):
                errors.append(f"{name}: ({x},{y}) is blocked")

    def need_blocked(name, pts):
        for x, y in pts:
            if not blocked(x, y):
                errors.append(f"{name}: ({x},{y}) is OPEN (should block)")

    need_open("N corridor", [(x, y) for y in range(0, 10) for x in (40, 41)])
    need_open("E gate", [(x, y) for y in range(15, 19) for x in (77, 78, 79)])
    need_open("S corridor", [(x, y) for y in range(58, 62) for x in (40, 41, 42)] +
              [(x, y) for y in range(62, 65) for x in (40, 41)])
    need_open("cave approach", [(34, y) for y in (5, 6, 7, 8)] +
              [(33, 8), (35, 8)] + [(x, 8) for x in range(36, 40)])
    need_open("greenhouse approach", [(x, 8) for x in range(19, 24)])
    need_blocked("W cliff band", [(x, y) for y in range(8, 61) for x in (0, 1, 2)])
    need_blocked("E cliff band", [(x, y) for y in list(range(10, 15)) +
                                  list(range(19, 61)) for x in (78, 79)])
    need_blocked("N cliff face", [(x, 7) for x in list(range(3, 33)) + list(range(36, 40))])
    need_blocked("yard fences", [(x, 6) for x in range(50, 55)] +
                 [(x, 7) for x in range(69, 73)] +
                 [(x, 9) for x in list(range(55, 69)) + list(range(73, 78))])
    need_blocked("S cliff", [(x, 63) for x in list(range(3, 12)) + list(range(13, 39)) +
                             list(range(43, 73))])
    # cave door + sign intact
    bt = L['Back'].tiles[5 * W + 34]
    if not (bt and isinstance(bt, StaticTile) and bt.index == 217 and
            bt.props.get('NoSpawn') == (3, 'All') and bt.props.get('NoFurniture') == (3, 'total')):
        errors.append("cave door tile (34,5) was altered")
    st = L['Buildings'].tiles[7 * W + 8]
    if not (st and isinstance(st, StaticTile) and st.index == 1957 and
            st.props.get('Action') == (3, 'Message "Farm.1"')):
        errors.append("farm sign (8,7) was altered")
    # field uniform sandy + NoSpawn
    for y in range(FIELD[2], FIELD[3] + 1):
        for x in range(FIELD[0], FIELD[1] + 1):
            if in_rect(x, y, YARD):
                continue
            t = L['Back'].tiles[y * W + x]
            if not (t and isinstance(t, StaticTile) and t.index == SAND and
                    t.props.get('NoSpawn') == (3, 'All')):
                errors.append(f"field ({x},{y}) not sandy/NoSpawn")
            for ln in ('Buildings', 'Front', 'AlwaysFront', 'AlwaysFront2'):
                if L[ln].tiles[y * W + x] is not None:
                    errors.append(f"field {ln} ({x},{y}) not empty")
    # yard preserved (Back/Buildings/Front indices identical to vanilla)
    for y in range(YARD[2], YARD[3] + 1):
        for x in range(YARD[0], YARD[1] + 1):
            for ln in ('Back', 'Buildings'):
                if idx(ln, x, y) != vidx(ln, x, y):
                    errors.append(f"yard {ln} ({x},{y}) changed: {vidx(ln, x, y)} -> {idx(ln, x, y)}")
            if (x, y) not in TUFT and idx('Front', x, y) != vidx('Front', x, y):
                errors.append(f"yard Front ({x},{y}) changed: {vidx('Front', x, y)} -> {idx('Front', x, y)}")
    # no debris / trees / bushes left anywhere; cabins + grass-init kept
    tokens = [(x, y, t.index) for y in range(H) for x in range(W)
              for t in [L['Paths'].tiles[y * W + x]]
              if t is not None and isinstance(t, StaticTile) and t.sheet == 'Paths']
    bad = [t for t in tokens if t[2] in DEBRIS]
    if bad:
        errors.append(f"debris tokens left: {bad[:10]}")
    n_cabins = sum(1 for _, _, i in tokens if i in CABIN)
    if n_cabins != 14:
        errors.append(f"cabin markers: {n_cabins} != 14")
    if not any(i == GRASS_INIT for _, _, i in tokens):
        errors.append("no Paths idx-22 grass-init token")
    # no water anywhere on the farm
    water_ids = {1186, 1187, 1188, 1211, 1212, 1213, 1227, 1228, 1229, 1230, 1231,
                 1237, 1238, 1239, 1240, 1241, 1242, 1243, 1244, 1245, 1246, 1247,
                 1248, 1249, 1252, 1253, 1254, 1255, 1256, 1263, 1264, 1265, 1266,
                 1267, 1268, 1269, 1270, 1271, 1272, 1273, 1274, 1277, 1278, 1279,
                 1280, 1281, 1297, 1298, 1299, 1302, 1303, 1304, 1305, 1306,
                 1322, 1323, 1324, 209, 234}
    s2_water = {816, 817, 820, 821, 822} | set(range(832, 839)) | set(range(848, 855)) \
        | set(range(864, 871)) | set(range(880, 884))
    for y in range(H):
        for x in range(W):
            t = L['Back'].tiles[y * W + x]
            if t is not None and isinstance(t, StaticTile) and (
                    (t.sheet == MAIN and t.index in water_ids) or
                    (t.sheet == 'v16_Outdoors2' and t.index in s2_water)):
                errors.append(f"water left at ({x},{y})")
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
        for e in errs[:40]:
            print("  -", e)
        sys.exit(1)
    print("  all checks passed")
    data = serialize(m)
    open(DST, 'wb').write(data)
    m2 = parse(open(DST, 'rb').read())
    assert len(serialize(m2)) == len(data)
    print(f"wrote {DST} ({len(data)} bytes)")
