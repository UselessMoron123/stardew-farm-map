#!/usr/bin/env python3
"""
Rebuild the standard Farm map — revision 3 (play-test report 288-294).

v3 = "keep textures simple and universal":
  * ONE ground tile everywhere below the north band: plain green lawn 351.
    No speckle variants (293: darker dots / lighter patches gone), no dirt
    patches, no paths, no flowers, no pond (289), no trees at all (292).
  * Every painted ground tile carries Diggable=T / Type=Dirt / CanPlantTrees=T
    (hoe, trees, buildings behave like the vanilla field) AND NoSpawn="All",
    so weeds / stones / twigs / grass can never spawn or spread on the farm
    (292: "prevent litter from spawning at all"). Objects already baked into
    an old save are not part of the map - they need a new save to disappear.
  * The north band y0-8 stays verbatim vanilla (hill, shrine, greenhouse and
    cave doors, fences, the cliff-base shadow row y8 that helps blending (288)).
  * The yard keeps only what has function: fences and border blockers
    (Buildings layer, x55-79 / y9-20 verbatim) and the instance properties of
    the vanilla yard tiles (spouse-patio "Buildable f" markers, patio stone
    props) - but their look becomes the same plain lawn (292: no stone
    textures, no path to the shipping bin, no pebbles/holes).
    The fence line is kept complete, so there is no walk-through gap (291).
  * Border: invisible blockers on lawn at x2 / x77 (y21-58), south row y59 and
    the whole bottom band y60-64 except the Forest warp corridor (x40-42).
  * No Front / AlwaysFront tile below y9 (nothing draws over the player).
  * Paths layer: only the 14 multiplayer cabin markers and ONE grass-init
    token (index 22), hidden under the farmhouse footprint so the mandatory
    start grass tuft is invisible (294: stray grass object in the corner).
"""
import sys, copy
sys.path.insert(0, 'tools')
from tbin import parse, serialize, StaticTile, AnimatedTile, Properties

SRC = 'work/Farm.tbin'
DST = 'work/Farm_modified.tbin'

MAIN = 'untitled tile sheet'          # spring_outdoorsTileSheet
BLOCK = 16                            # invisible blocker (vanilla Buildings layer)
LAWN = 351                            # the one and only ground tile

FX0, FX1, FY0, FY1 = 3, 76, 9, 58     # clean square field
NX0, NX1, NY0, NY1 = 55, 79, 9, 20    # yard block: fences/blockers/props kept
WALL_Y = 59
CX0, CX1 = 40, 42                     # forest warp corridor
HOUSE_HIDE = (66, 12)                 # grass-init token hidden under the farmhouse

WATER_IDS = {1186,1187,1188,1211,1212,1213,1227,1228,1229,1230,1231,
             1237,1238,1239,1240,1241,1242,1243,1244,1245,1246,1247,1248,1249,
             1252,1253,1254,1255,1256,1263,1264,1265,1266,1267,1268,1269,1270,
             1271,1272,1273,1274,1277,1278,1279,1280,1281,1297,1298,1299,
             1302,1303,1304,1305,1306,1322,1323,1324,209,234}
S2_WATER = {816,817,820,821,822}|set(range(832,839))|set(range(848,855))|set(range(864,871))|set(range(880,884))

# sheet-level properties of the patio stone tiles, re-stamped per tile so the
# patio behaves the same while looking like plain lawn
STONE_PROPS = {
    1964: {'NoFurniture': (3, 'T'), 'NoSpawn': (3, 'All'), 'Type': (3, 'Stone'), 'placeable': (3, 'F')},
    1965: {'NoFurniture': (3, 'T'), 'NoSpawn': (3, 'All'), 'Type': (3, 'Stone'), 'placeable': (3, 'f')},
    1966: {'NoFurniture': (3, 'T'), 'NoSpawn': (3, 'All')},
}


def is_water(t):
    if t is None or not isinstance(t, StaticTile):
        return False
    if t.sheet == MAIN and t.index in WATER_IDS:
        return True
    if t.sheet == 'v16_Outdoors2' and t.index in S2_WATER:
        return True
    return False


def build():
    m = parse(open(SRC, 'rb').read())
    L = {l.id: l for l in m.layers}
    W, H = L['Back'].size
    assert (W, H) == (80, 65)
    van = {ln: list(L[ln].tiles) for ln in L}

    def put(ln, x, y, tile):
        L[ln].tiles[y * W + x] = tile

    def clear(ln, x, y):
        L[ln].tiles[y * W + x] = None

    def lawn(x, y, props=None):
        t = StaticTile(MAIN, LAWN, 0)
        t.props['Diggable'] = (3, 'T')
        t.props['Type'] = (3, 'Dirt')
        t.props['CanPlantTrees'] = (3, 'T')
        t.props['NoSpawn'] = (3, 'All')        # no weed/stone/grass spawn, ever
        if props:
            for k, v in props.items():
                t.props[k] = v
        put('Back', x, y, t)

    def blocker(x, y):
        t = StaticTile(MAIN, BLOCK, 0)
        t.props['NoSpawn'] = (3, 'All')
        put('Buildings', x, y, t)

    # ------------------------------------------------------------------ #
    # 1) paths: keep cabin markers only
    # ------------------------------------------------------------------ #
    cabins = {}
    for y in range(H):
        for x in range(W):
            t = L['Paths'].tiles[y * W + x]
            if t is not None and isinstance(t, StaticTile) and t.sheet == 'Paths' \
               and t.index in (29, 30):
                cabins[(x, y)] = t
    for y in range(H):
        for x in range(W):
            clear('Paths', x, y)
    for (x, y), t in cabins.items():
        put('Paths', x, y, t)
    put('Paths', HOUSE_HIDE[0], HOUSE_HIDE[1], StaticTile('Paths', 22, 0))

    # ------------------------------------------------------------------ #
    # 2) one plain lawn everywhere below the north band
    # ------------------------------------------------------------------ #
    for y in range(9, H):
        for x in range(W):
            lawn(x, y)
            for ln in ('Buildings', 'Front', 'AlwaysFront', 'AlwaysFront2'):
                clear(ln, x, y)

    # forest corridor: same lawn, but keep the vanilla tile properties
    for y in range(WALL_Y, H):
        for x in range(CX0, CX1 + 1):
            vt = van['Back'][y * W + x]
            props = dict(vt.props) if isinstance(vt, StaticTile) else None
            lawn(x, y, props)

    # yard: keep the instance properties of the vanilla tiles (patio markers,
    # stone-tile behaviour) on top of the plain lawn
    for y in range(NY0, NY1 + 1):
        for x in range(NX0, NX1 + 1):
            vt = van['Back'][y * W + x]
            props = Properties()
            if isinstance(vt, StaticTile):
                for k, v in vt.props.items():
                    props[k] = v
                for k, v in STONE_PROPS.get(vt.index, {}).items():
                    props[k] = v
            lawn(x, y, props or None)

    # ------------------------------------------------------------------ #
    # 3) verbatim vanilla: north band y0-8 (all layers) and the yard's
    #    Buildings layer (fences, border blockers) - no walk-through gap
    # ------------------------------------------------------------------ #
    for ln in ('Back', 'Buildings', 'Front', 'AlwaysFront', 'AlwaysFront2'):
        for y in range(0, 9):
            for x in range(W):
                L[ln].tiles[y * W + x] = copy.deepcopy(van[ln][y * W + x])
    for y in range(NY0, NY1 + 1):
        for x in range(NX0, NX1 + 1):
            L['Buildings'].tiles[y * W + x] = copy.deepcopy(van['Buildings'][y * W + x])
    # corridor side walls (vanilla cliff faces) back in
    for y in range(WALL_Y + 1, H):
        for x in (CX0 - 1, CX1 + 1):
            if van['Buildings'][y * W + x] is not None:
                put('Buildings', x, y, copy.deepcopy(van['Buildings'][y * W + x]))

    # ------------------------------------------------------------------ #
    # 4) border walls + sealed bottom band
    # ------------------------------------------------------------------ #
    for y in range(FY0, FY1 + 1):
        blocker(2, y)
        if not (15 <= y <= 18):            # BusStop gate stays open
            blocker(77, y)
    for x in range(FX0, CX0):
        blocker(x, WALL_Y)
    for x in range(CX1 + 1, FX1 + 1):
        blocker(x, WALL_Y)
    for x in (0, 1, 78, 79):
        blocker(x, WALL_Y)
    for y in range(WALL_Y + 1, H):
        for x in range(W):
            if CX0 <= x <= CX1:
                continue
            if van['Buildings'][y * W + x] is not None and x in (CX0 - 1, CX1 + 1):
                continue
            blocker(x, y)

    return m, L


# ---------------------------------------------------------------------- #
def validate(m):
    L = {l.id: l for l in m.layers}
    W, H = L['Back'].size
    errors = []

    def blocked(x, y):
        if not (0 <= x < W and 0 <= y < H):
            return True
        if L['Buildings'].tiles[y * W + x] is not None:
            return True
        return is_water(L['Back'].tiles[y * W + x])

    def need_open(name, pts):
        for x, y in pts:
            if blocked(x, y):
                errors.append(f"{name}: ({x},{y}) is blocked")

    def need_blocked(name, pts):
        for x, y in pts:
            if not blocked(x, y):
                errors.append(f"{name}: ({x},{y}) is OPEN (should block)")

    need_open("N corridor", [(40, y) for y in range(0, 9)] + [(41, y) for y in range(0, 9)])
    need_open("E gate", [(x, y) for y in range(15, 19) for x in (77, 78, 79)])
    need_open("S corridor", [(x, y) for y in range(58, 65) for x in (40, 41, 42)])
    bt = L['Back'].tiles[5 * W + 34]
    if not (bt and isinstance(bt, StaticTile) and bt.index == 217 and
            bt.props.get('NoSpawn') == (3, 'All') and bt.props.get('NoFurniture') == (3, 'total')):
        errors.append("cave door tile (34,5) was altered")
    need_blocked("cave door frame", [(33, 5), (35, 5), (33, 6), (35, 6), (33, 7), (35, 7)])
    st = L['Buildings'].tiles[7 * W + 8]
    if not (st and isinstance(st, StaticTile) and st.index == 1957 and
            st.props.get('Action') == (3, 'Message "Farm.1"')):
        errors.append("farm sign (8,7) was altered")
    # spouse patio markers survived the repaint
    for (x, y) in [(69, 10), (70, 10), (71, 10), (72, 10), (70, 11), (72, 11),
                   (69, 12), (70, 12), (71, 12), (72, 12), (69, 13), (70, 13), (71, 13), (72, 13)]:
        t = L['Back'].tiles[y * W + x]
        if not (t and isinstance(t, StaticTile) and t.props.get('Buildable') == (3, 'f')):
            errors.append(f"spouse patio tile ({x},{y}) lost its Buildable property")
    # fence line complete (no walk-through gap)
    for x in range(55, 69):
        if L['Buildings'].tiles[9 * W + x] is None:
            errors.append(f"fence gap at ({x},9)")
    # walls / sealed band
    need_blocked("W wall", [(2, y) for y in range(FY0, FY1 + 1)])
    need_blocked("E wall", [(77, y) for y in range(FY0, FY1 + 1) if not (15 <= y <= 18)])
    need_blocked("S wall", [(x, WALL_Y) for x in list(range(FX0, CX0)) + list(range(CX1 + 1, FX1 + 1))])
    need_blocked("bottom band", [(x, y) for y in range(WALL_Y + 1, H)
                                 for x in range(W) if not (CX0 <= x <= CX1)])
    # uniform lawn, tillable, no-spawn, no water, nothing in front
    for y in range(9, H):
        for x in range(W):
            b = L['Back'].tiles[y * W + x]
            if not (b and isinstance(b, StaticTile) and b.sheet == MAIN and b.index == LAWN):
                errors.append(f"Back ({x},{y}) is not plain lawn")
            else:
                if b.props.get('Diggable') != (3, 'T'):
                    errors.append(f"Back ({x},{y}) not tillable")
                if b.props.get('NoSpawn') != (3, 'All'):
                    errors.append(f"Back ({x},{y}) missing NoSpawn")
            if is_water(b):
                errors.append(f"water tile at ({x},{y})")
            for ln in ('Front', 'AlwaysFront', 'AlwaysFront2'):
                if L[ln].tiles[y * W + x] is not None:
                    errors.append(f"{ln} tile at ({x},{y})")
    # tokens: cabins + one hidden grass-init, nothing else
    tokens = [(x, y, t.index) for y in range(H) for x in range(W)
              for t in [L['Paths'].tiles[y * W + x]]
              if t is not None and isinstance(t, StaticTile) and t.sheet == 'Paths']
    n_cabins = sum(1 for _, _, i in tokens if i in (29, 30))
    if n_cabins != 14:
        errors.append(f"cabin markers: {n_cabins} != 14")
    inits = [(x, y) for x, y, i in tokens if i == 22]
    if inits != [HOUSE_HIDE]:
        errors.append(f"grass-init tokens: {inits}")
    stray = [(x, y, i) for x, y, i in tokens if i not in (22, 29, 30)]
    if stray:
        errors.append(f"stray path tokens: {stray[:8]}")
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
        for e in errs[:60]:
            print("  -", e)
        sys.exit(1)
    print("  all checks passed")
    data = serialize(m)
    open(DST, 'wb').write(data)
    m2 = parse(open(DST, 'rb').read())
    assert len(serialize(m2)) == len(data)
    print(f"wrote {DST} ({len(data)} bytes)")
