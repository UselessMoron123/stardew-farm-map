#!/usr/bin/env python3
"""Dump tile indices of a region/layer from a tbin as a compact grid."""
import sys
sys.path.insert(0, 'tools')
from tbin import parse, StaticTile, AnimatedTile

def load(path):
    m = parse(open(path, 'rb').read())
    return m, {l.id: l for l in m.layers}

def cell(t):
    if t is None:
        return '  .  '
    if isinstance(t, AnimatedTile):
        return f'A{t.frames[0].index:>4}' if t.frames else 'A??? '
    return f'{t.index:>5}'

def dump(path, layer, x0, x1, y0, y1, sheet_filter=None):
    m, L = load(path)
    W, H = L['Back'].size
    print(f'--- {path} layer={layer} x[{x0}..{x1}] y[{y0}..{y1}]')
    hdr = '      ' + ''.join(f'{x%100:>5d}' for x in range(x0, x1 + 1))
    print(hdr)
    for y in range(y0, y1 + 1):
        row = f'{y:>5} '
        for x in range(x0, x1 + 1):
            t = L[layer].tiles[y * W + x]
            if sheet_filter and t is not None and isinstance(t, StaticTile) and t.sheet != sheet_filter:
                row += '    s'
            else:
                row += cell(t)
        print(row)

if __name__ == '__main__':
    path, layer = sys.argv[1], sys.argv[2]
    x0, x1, y0, y1 = (int(v) for v in sys.argv[3:7])
    dump(path, layer, x0, x1, y0, y1)
