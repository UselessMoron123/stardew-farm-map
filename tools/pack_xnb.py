#!/usr/bin/env python3
"""Pack a tbin map into an uncompressed Stardew XNB (no external tools).

Layout of a Stardew map XNB (uncompressed, hi-def):
    'XNB' + platform('w') + version(5) + flags(0x01) + int32 fileSize
    payload:
        7bit readerCount (=1)
        7bit-len + 'xTile.Pipeline.TideReader, xTile'
        int32 readerVersion (0)
        7bit sharedResourceCount (0)
        7bit primaryTypeIndex (1)
        int32 tbinSize
        <tbin bytes>
The 54-byte prefix is reconstructed from scratch (verified against the
previously shipped output/Farm.xnb, whose embedded tbin starts at offset 54).
"""
import struct
import sys

READER = b'xTile.Pipeline.TideReader, xTile'


def prefix() -> bytes:
    out = bytearray()
    out += b'XNBw'                       # magic + platform
    out += bytes([5])                    # version
    out += bytes([0x01])                 # flags: hi-def, uncompressed
    out += b'\x00\x00\x00\x00'           # fileSize (patched below)
    out += bytes([0x01])                 # reader count = 1 (7bit)
    out += bytes([len(READER)]) + READER
    out += struct.pack('<i', 0)          # reader version
    out += bytes([0x00])                 # shared resources = 0 (7bit)
    out += bytes([0x01])                 # primary type index = 1 (7bit)
    return bytes(out)


def pack(tbin_path: str, xnb_path: str) -> int:
    tbin = open(tbin_path, 'rb').read()
    assert tbin[:6] == b'tBIN10', 'not a tbin file'
    pre = prefix() + struct.pack('<i', len(tbin))
    data = pre + tbin
    data = data[:6] + struct.pack('<i', len(data)) + data[10:]
    open(xnb_path, 'wb').write(data)
    return len(data)


if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    n = pack(src, dst)
    # sanity: re-read header
    d = open(dst, 'rb').read()
    assert d[:3] == b'XNB' and d[5] == 0x01
    (fs,) = struct.unpack_from('<i', d, 6)
    assert fs == len(d)
    (ts,) = struct.unpack_from('<i', d, len(d) - len(open(src, 'rb').read()) - 4)
    assert ts == len(open(src, 'rb').read())
    print(f'wrote {dst} ({n} bytes, uncompressed XNB)')
