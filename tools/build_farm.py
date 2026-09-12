#!/usr/bin/env python3
"""
Rebuild the standard Farm map — revision 2 (fixes the play-test report 277-287).

Design (see README-MOD.md):
  * The farmable land is one clean rectangle (x3-76, y9-58) of GREEN lawn — the same
    grass family the vanilla map uses around the farmhouse / north hill (tile 351 and
    its natural neighbours 300/304/305/329), NOT the tan diggable dirt (587) used in v1.
  * Everything the game draws at runtime keeps its vanilla ground underneath:
      - whole north band y0-8 (hill, shrine, greenhouse, cave, fences, Backwoods corridor)
      - the north-east yard block x57-79 / y8-20  -> farmhouse lawn, shipping bin &
        mailbox ground, the spouse "patio" (Buildable 'f' + stone tiles), the BusStop gate
      - the Forest exit corridor x40-42 / y59-64
    Those regions are copied byte-for-byte from the vanilla map, so nothing functional
    or decorative disappears (bug 278: "husband zone / box / mailbox" were flattened).
  * One pond, copied verbatim (Back water + Buildings sparkle animation) from the
    vanilla east pond, placed INSIDE the square at the south-west so it is always
    reachable and fully on-screen (bugs 281/283/286).
  * Border = invisible blockers on plain lawn, every one of them carrying
    NoSpawn="All" so grass/weeds can never grow on the un-interactable lines (bug 284).
    The whole bottom band y60-64 is blocked except the Forest corridor, so the player
    can never step off the map (bug 281).
  * No Front / AlwaysFront tile anywhere below y9: the vanilla south "grass fringe"
    used to draw over the player and over tree crowns (bugs 282, 285, 286).
  * Trees: every vanilla scatter token is gone; two tidy rows sit BEHIND the border at
    x=1 and x=78 (crowns stay inside the map, bug 285) and stay clear of the BusStop
    gate (bug 277).
"""
import sys, copy, random
sys.path.insert(0, 'tools')
from tbin import parse, serialize, StaticTile, AnimatedTile, Properties

SRC = 'work/Farm.tbin'
DST = 'work/Farm_modified.tbin'

MAIN = 'untitled tile sheet'          # spring_outdoorsTileSheet
BLOCK = 16                            # invisible blocker (vanilla Buildings layer)

# green lawn family (vanilla look around the farmhouse / north hill)
LAWN_BASE = 351
LAWN_SPECKLE = (300, 304, 305, 329)   # proven vanilla neighbours of 351
LAWN_RARE = (352, 354, 355)

# rectangle of the clean square field
FX0, FX1, FY0, FY1 = 3, 76, 9, 58
# north-east yard block kept verbatim from vanilla (house lawn, bin, mailbox, patio, gate)
NX0, NX1, NY0, NY1 = 57, 79, 8, 20
# south wall row and the blocked bottom band
WALL_Y = 59
# forest corridor kept verbatim
CX0, CX1 = 40, 42
# pond: source window in the vanilla map (east pond, incl. one tile of shore)
POND_SRC = (69, 27, 77, 34)
POND_DST = (7, 49)

WATER_IDS = {1186,1187,1188,1211,1212,1213,1227,1228,1229,1230,1231,
             1237,1238,1239,1240,1241,1242,1243,1244,1245,1246,1247,1248,1249,
             1252,1253,1254,1255,1256,1263,1264,1265,1266,1267,1268,1269,1270,
             1271,1272,1273,1274,1277,1278,1279,1280,1281,1297,1298,1299,
             1302,1303,1304,1305,1306,1322,1323,1324,209,234}
S2_WATER = {816,817,820,821,822}|set(range(832,839))|set(range(848,855))|set(range(864,871))|set(range(880,884))


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
    van = {ln: list(L[ln].tiles) for ln in L}      # pristine vanilla copy

    def put(ln, x, y, tile):
        L[ln].tiles[y * W + x] = tile

    def clear(ln, x, y):
        L[ln].tiles[y * W + x] = None

    rng = random.Random(1234)

    def lawn(x, y, tillable=True):
        r = rng.random()
        idx = LAWN_BASE
        if r < 0.06:
            idx = rng.choice(LAWN_SPECKLE)
        elif r < 0.085:
            idx = rng.choice(LAWN_RARE)
        t = StaticTile(MAIN, idx, 0)
        if tillable:
            # the green lawn tiles are not diggable at sheet level (only the tan
            # dirt family is), so stamp the field properties per tile: the hoe,
            # trees and buildings all behave exactly like on the vanilla field
            t.props['Diggable'] = (3, 'T')
            t.props['Type'] = (3, 'Dirt')
            t.props['CanPlantTrees'] = (3, 'T')
        put('Back', x, y, t)

    def blocker(x, y, back='lawn'):
        """invisible wall tile that also forbids grass/weed spawns"""
        if back == 'lawn':
            lawn(x, y)
        t = StaticTile(MAIN, BLOCK, 0)
        t.props['NoSpawn'] = (3, 'All')
        put('Buildings', x, y, t)

    # ------------------------------------------------------------------ #
    # 1) wipe every spawn token everywhere (trees, weeds, stones, bushes)
    #    but remember the 14 multiplayer cabin markers
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

    # ------------------------------------------------------------------ #
    # 2) the clean square field: green lawn, empty Buildings/Front/AlwaysFront
    # ------------------------------------------------------------------ #
    for y in range(FY0, FY1 + 1):
        for x in range(FX0, FX1 + 1):
            if NX0 <= x <= NX1 and NY0 <= y <= NY1:
                continue                      # yard block stays vanilla
            lawn(x, y)
            for ln in ('Buildings', 'Front', 'AlwaysFront', 'AlwaysFront2'):
                clear(ln, x, y)

    # west / east behind-the-border strips + border columns
    for y in range(FY0, FY1 + 1):
        for x in (0, 1, 2, 77, 78, 79):
            if NX0 <= x <= NX1 and NY0 <= y <= NY1:
                continue
            lawn(x, y)
            for ln in ('Buildings', 'Front', 'AlwaysFront', 'AlwaysFront2'):
                clear(ln, x, y)

    # ------------------------------------------------------------------ #
    # 3) restore the verbatim vanilla regions (they were wiped above only
    #    where the field reaches; make sure they are exactly vanilla)
    # ------------------------------------------------------------------ #
    for ln in ('Back', 'Buildings', 'Front', 'AlwaysFront', 'AlwaysFront2'):
        for y in range(0, 9):                              # north band incl. y8 row
            for x in range(W):
                L[ln].tiles[y * W + x] = copy.deepcopy(van[ln][y * W + x])
        for y in range(NY0, NY1 + 1):                      # NE yard block
            for x in range(NX0, NX1 + 1):
                L[ln].tiles[y * W + x] = copy.deepcopy(van[ln][y * W + x])
        for y in range(WALL_Y, H):                         # forest corridor
            for x in range(CX0 - 1, CX1 + 2):
                L[ln].tiles[y * W + x] = copy.deepcopy(van[ln][y * W + x])
    # ...but the corridor must not keep the front-layer fringe either
    for y in range(WALL_Y, H):
        for x in range(CX0 - 1, CX1 + 2):
            clear('Front', x, y)
            clear('AlwaysFront', x, y)
            clear('AlwaysFront2', x, y)
    # no Paths debris inside the kept blocks either (tokens already wiped);
    # cabin markers that fall inside them go back
    for (x, y), t in cabins.items():
        put('Paths', x, y, t)

    # ------------------------------------------------------------------ #
    # 4) no Front / AlwaysFront graphics anywhere below the north band:
    #    they drew over the player and chopped tree crowns (282/285/286)
    # ------------------------------------------------------------------ #
    for y in range(9, H):
        for x in range(W):
            clear('Front', x, y)
            clear('AlwaysFront', x, y)
            clear('AlwaysFront2', x, y)
    for y in range(NY0, NY1 + 1):                          # yard fence stays, but
        for x in range(NX0, NX1 + 1):                      # nothing in front of it
            if y >= 9:
                clear('Front', x, y)
                clear('AlwaysFront', x, y)

    # ------------------------------------------------------------------ #
    # 5) border walls: invisible, on lawn, no grass ever grows on them
    # ------------------------------------------------------------------ #
    for y in range(FY0, FY1 + 1):
        blocker(2, y)
        if not (15 <= y <= 18):            # keep the BusStop gate open
            blocker(77, y)
    for x in range(FX0, CX0):
        blocker(x, WALL_Y)
    for x in range(CX1 + 1, FX1 + 1):
        blocker(x, WALL_Y)
    for x in (0, 1, 2, 77, 78, 79):
        blocker(x, WALL_Y)
    # corridor mouth stays open, on lawn
    for x in range(CX0, CX1 + 1):
        lawn(x, WALL_Y)
        clear('Buildings', x, WALL_Y)
    # bottom band: sealed (except the forest corridor) so nobody walks off the map
    for y in range(WALL_Y + 1, H):
        for x in range(W):
            for ln in ('Front', 'AlwaysFront', 'AlwaysFront2'):
                clear(ln, x, y)
            if CX0 <= x <= CX1:
                # keep the vanilla corridor floor (+ its NoSpawn/NPCBarrier props)
                clear('Buildings', x, y)
                continue
            if x in (CX0 - 1, CX1 + 1) and van['Buildings'][y * W + x] is not None:
                # keep the vanilla cliff faces that flank the corridor (they block too)
                lawn(x, y, tillable=False)
                continue
            lawn(x, y, tillable=False)
            blocker(x, y, back='keep')

    # ------------------------------------------------------------------ #
    # 6) the pond: verbatim vanilla water + sparkle animation, inside the square
    # ------------------------------------------------------------------ #
    sx0, sy0, sx1, sy1 = POND_SRC
    dx, dy = POND_DST
    for yy in range(sy0, sy1 + 1):
        for xx in range(sx0, sx1 + 1):
            src = van['Back'][yy * W + xx]
            dst_x, dst_y = dx + (xx - sx0), dy + (yy - sy0)
            if is_water(src):
                put('Back', dst_x, dst_y, copy.deepcopy(src))
            else:
                lawn(dst_x, dst_y)          # shore blends into the field
            b = van['Buildings'][yy * W + xx]
            if b is not None and is_water(src):
                # only the water sparkle / lily decor that sits ON the water
                put('Buildings', dst_x, dst_y, copy.deepcopy(b))

    # ------------------------------------------------------------------ #
    # 7) tidy tree rows behind the border (crowns fully inside the map)
    # ------------------------------------------------------------------ #
    cycle = [9, 10, 11]                     # oak / maple / pine
    n = 0
    for y in range(FY0, FY1 + 1):
        put('Paths', 1, y, StaticTile('Paths', cycle[n % 3], 0)); n += 1
    for y in range(NY1 + 1, FY1 + 1):      # east row starts below the yard block
        put('Paths', 78, y, StaticTile('Paths', cycle[n % 3], 0)); n += 1
    # grass-init token the game requires (>=1 Paths index 22 on farm maps)
    put('Paths', 1, H - 1, StaticTile('Paths', 22, 0))

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

    # warp corridors
    need_open("N corridor", [(40, y) for y in range(0, 9)] + [(41, y) for y in range(0, 9)])
    need_open("E gate", [(x, y) for y in range(15, 19) for x in (77, 78, 79)])
    need_open("S corridor", [(x, y) for y in range(58, 65) for x in (40, 41, 42)])
    # cave door + frame + sign untouched (north band is verbatim vanilla)
    bt = L['Back'].tiles[5 * W + 34]
    if not (bt and isinstance(bt, StaticTile) and bt.index == 217 and
            bt.props.get('NoSpawn') == (3, 'All') and bt.props.get('NoFurniture') == (3, 'total')):
        errors.append("cave door tile (34,5) was altered")
    need_blocked("cave door frame", [(33, 5), (35, 5), (33, 6), (35, 6), (33, 7), (35, 7)])
    st = L['Buildings'].tiles[7 * W + 8]
    if not (st and isinstance(st, StaticTile) and st.index == 1957 and
            st.props.get('Action') == (3, 'Message "Farm.1"')):
        errors.append("farm sign (8,7) was altered")
    # spouse patio / yard block verbatim
    for (x, y) in [(69, 10), (70, 10), (71, 10), (72, 10), (69, 11), (70, 11), (72, 11),
                   (69, 12), (70, 12), (71, 12), (72, 12), (69, 13), (70, 13), (71, 13), (72, 13)]:
        t = L['Back'].tiles[y * W + x]
        if not (t and isinstance(t, StaticTile) and t.props.get('Buildable') == (3, 'f')):
            errors.append(f"spouse patio tile ({x},{y}) lost its Buildable property")
    # walls
    need_blocked("W wall", [(2, y) for y in range(FY0, FY1 + 1)])
    need_blocked("E wall", [(77, y) for y in range(FY0, FY1 + 1) if not (15 <= y <= 18)])
    need_blocked("S wall", [(x, WALL_Y) for x in list(range(FX0, CX0 - 1)) + list(range(CX1 + 1, FX1 + 1))])
    need_blocked("bottom band", [(x, y) for y in range(WALL_Y + 1, H)
                                 for x in range(W) if not (CX0 - 1 <= x <= CX1 + 1)])
    # field clean + green
    lawn_ok = {LAWN_BASE} | set(LAWN_SPECKLE) | set(LAWN_RARE)
    for y in range(FY0, FY1 + 1):
        for x in range(FX0, FX1 + 1):
            if NX0 <= x <= NX1 and NY0 <= y <= NY1:
                continue
            b = L['Back'].tiles[y * W + x]
            if is_water(b):
                continue                       # pond
            if not (b and isinstance(b, StaticTile) and b.sheet == MAIN and b.index in lawn_ok):
                errors.append(f"field Back ({x},{y}) is not lawn ({b.index if b else None})")
            elif b.props.get('Diggable') != (3, 'T'):
                errors.append(f"field Back ({x},{y}) is not tillable")
            for ln in ('Buildings', 'Front', 'AlwaysFront', 'AlwaysFront2'):
                if L[ln].tiles[y * W + x] is not None and not (ln == 'Buildings' and (x, y) in
                        {(dx, dy) for dx in range(POND_DST[0], POND_DST[0] + 9)
                         for dy in range(POND_DST[1], POND_DST[1] + 8)}):
                    errors.append(f"field {ln} ({x},{y}) not empty")
    # no front graphics below the north band at all
    for y in range(9, H):
        for x in range(W):
            for ln in ('Front', 'AlwaysFront', 'AlwaysFront2'):
                if L[ln].tiles[y * W + x] is not None:
                    errors.append(f"{ln} tile at ({x},{y}) below north band")
    # pond: water present and reachable from the field on every side
    dx, dy = POND_DST
    water_cells = [(x, y) for y in range(dy, dy + 8) for x in range(dx, dx + 9)
                   if is_water(L['Back'].tiles[y * W + x])]
    if len(water_cells) < 20:
        errors.append(f"pond too small: {len(water_cells)} water tiles")
    for x, y in water_cells:
        for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + ddx, y + ddy
            if (nx, ny) in water_cells:
                continue
            if blocked(nx, ny):
                errors.append(f"pond shore ({nx},{ny}) not reachable")
    # tokens
    tokens = [(x, y, t.index) for y in range(H) for x in range(W)
              for t in [L['Paths'].tiles[y * W + x]]
              if t is not None and isinstance(t, StaticTile) and t.sheet == 'Paths']
    if not any(i == 22 for _, _, i in tokens):
        errors.append("no Paths idx-22 grass-init token")
    n_cabins = sum(1 for _, _, i in tokens if i in (29, 30))
    if n_cabins != 14:
        errors.append(f"cabin markers: {n_cabins} != 14")
    trees = [(x, y) for x, y, i in tokens if i in (9, 10, 11)]
    bad_tree = [(x, y) for x, y in trees if x not in (1, 78) or not (FY0 <= y <= FY1)]
    if bad_tree:
        errors.append(f"tree tokens outside the two rows: {bad_tree[:6]}")
    # trees must never sit in a gate/corridor
    for x, y in trees:
        if 15 <= y <= 18 and x >= 77:
            errors.append(f"tree blocks the BusStop gate at ({x},{y})")
    # warps untouched
    if m.props['Warp'] != (3, ('80 15 BusStop 11 23 80 18 BusStop 11 24 80 16 BusStop 11 23 '
                               '80 17 BusStop 11 23 40 65 Forest 68 0 41 65 Forest 68 0 '
                               '42 65 Forest 68 0 40 -1 Backwoods 14 39 41 -1 Backwoods 14 39 '
                               '34 5 FarmCave 8 11')):
        errors.append("Warp property changed")
    return errors, len(trees)


if __name__ == '__main__':
    m, _ = build()
    print("validating...")
    errs, n_trees = validate(m)
    if errs:
        print(f"{len(errs)} PROBLEMS:")
        for e in errs[:60]:
            print("  -", e)
        sys.exit(1)
    print(f"  all checks passed ({n_trees} trees in the two rows)")
    data = serialize(m)
    open(DST, 'wb').write(data)
    m2 = parse(open(DST, 'rb').read())
    assert len(serialize(m2)) == len(data)
    print(f"wrote {DST} ({len(data)} bytes)")
