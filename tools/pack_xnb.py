#!/usr/bin/env python3
"""Wrap work/Farm_modified.tbin into an uncompressed XNB (same reader block as
the previous output/Farm.xnb) -> output/Farm.xnb.

XNB layout used here (uncompressed, hi-def):
    'XNB' 'w' 0x05 flags(0x01) int32 totalSize | readers block | int32 tbinSize | tbin bytes
The readers block (xTile.Pipeline.TideReader) is copied verbatim from the
existing output/Farm.xnb so the payload stays byte-compatible with the game.
"""
import struct, sys

SRC_XNB = 'output/Farm.xnb'
DST_XNB = 'output/Farm.xnb'
TBIN = 'work/Farm_modified.tbin'

old = open(SRC_XNB, 'rb').read()
assert old[:4] == b'XNBw' and old[5] == 0x01, "unexpected XNB header"
i = old.find(b'tBIN10')
assert i > 10
prefix = old[:i - 4]                      # header + reader block
tbin = open(TBIN, 'rb').read()
payload = prefix + struct.pack('<i', len(tbin)) + tbin
out = bytearray(payload)
struct.pack_into('<i', out, 6, len(out))  # total file size
open(DST_XNB, 'wb').write(bytes(out))

# verify: unpack again and compare
chk = open(DST_XNB, 'rb').read()
j = chk.find(b'tBIN10')
assert struct.unpack_from('<i', chk, 6)[0] == len(chk), "size field wrong"
assert struct.unpack_from('<i', chk, j - 4)[0] == len(tbin), "tbin size field wrong"
assert chk[j:j + len(tbin)] == tbin and j + len(tbin) == len(chk), "payload mismatch"
sys.path.insert(0, 'tools')
from tbin import parse, serialize
m = parse(chk[j:])
assert len(serialize(m)) == len(tbin)
print(f"ok: {DST_XNB} ({len(chk)} bytes, uncompressed XNB, tbin round-trips)")
