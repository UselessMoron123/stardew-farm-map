"""Pure-Python LZX decoder for XNB-compressed Stardew Valley assets.

Faithful port of MonoGame's LzxDecoder/LzxDecoderStream (itself a C# port of
libmspack's lzxd.c, dual-licensed MS-PL / LGPL 2.1).
"""
from __future__ import annotations

import struct


# ---------------------------------------------------------------- constants
MIN_MATCH = 2
MAX_MATCH = 257
NUM_CHARS = 256
BLOCKTYPE_INVALID = 0
BLOCKTYPE_VERBATIM = 1
BLOCKTYPE_ALIGNED = 2
BLOCKTYPE_UNCOMPRESSED = 3
PRETREE_NUM_ELEMENTS = 20
ALIGNED_NUM_ELEMENTS = 8
NUM_PRIMARY_LENGTHS = 7
NUM_SECONDARY_LENGTHS = 249
PRETREE_MAXSYMBOLS = PRETREE_NUM_ELEMENTS
PRETREE_TABLEBITS = 6
MAINTREE_MAXSYMBOLS = NUM_CHARS + 50 * 8
MAINTREE_TABLEBITS = 12
LENGTH_MAXSYMBOLS = NUM_SECONDARY_LENGTHS + 1
LENGTH_TABLEBITS = 12
ALIGNED_MAXSYMBOLS = ALIGNED_NUM_ELEMENTS
ALIGNED_TABLEBITS = 7
LENTABLE_SAFETY = 64


def _make_extra_bits():
    extra = [0] * 52
    j = 0
    for i in range(0, 51, 2):
        extra[i] = extra[i + 1] = j
        if i != 0 and j < 17:
            j += 1
    return extra


def _make_position_base(extra):
    pos = [0] * 51
    j = 0
    for i in range(51):
        pos[i] = j
        j += 1 << extra[i]
    return pos


EXTRA_BITS = _make_extra_bits()
POSITION_BASE = _make_position_base(EXTRA_BITS)


class BitBuffer:
    def __init__(self, stream: bytes, pos: int = 0):
        self.stream = stream
        self.pos = pos
        self.buffer = 0
        self.bitsleft = 0

    def init_bitstream(self):
        self.buffer = 0
        self.bitsleft = 0

    def ensure_bits(self, bits: int):
        while self.bitsleft < bits:
            if self.pos < len(self.stream):
                lo = self.stream[self.pos]
                self.pos += 1
            else:
                lo = 0xFF  # mirrors (byte)Stream.ReadByte() == -1
            if self.pos < len(self.stream):
                hi = self.stream[self.pos]
                self.pos += 1
            else:
                hi = 0xFF
            word = (hi << 8) | lo
            shift = 16 - self.bitsleft
            if shift >= 0:
                self.buffer |= (word << shift) & 0xFFFFFFFF
            else:
                self.buffer |= (word >> -shift) & 0xFFFFFFFF
            self.buffer &= 0xFFFFFFFF
            self.bitsleft += 16

    def peek_bits(self, bits: int) -> int:
        if bits == 0:
            return 0
        return (self.buffer >> (32 - bits)) & ((1 << bits) - 1)

    def remove_bits(self, bits: int):
        self.buffer = (self.buffer << bits) & 0xFFFFFFFF
        self.bitsleft -= bits

    def read_bits(self, bits: int) -> int:
        if bits > 0:
            self.ensure_bits(bits)
            ret = self.peek_bits(bits)
            self.remove_bits(bits)
            return ret
        return 0

    def get_buffer(self) -> int:
        return self.buffer

    def get_bits_left(self) -> int:
        return self.bitsleft


class LzxDecoder:
    def __init__(self, window: int):
        if window < 15 or window > 21:
            raise ValueError("unsupported window size")
        wndsize = 1 << window
        if window == 20:
            posn_slots = 42
        elif window == 21:
            posn_slots = 50
        else:
            posn_slots = window << 1

        self.R0 = self.R1 = self.R2 = 1
        self.main_elements = NUM_CHARS + (posn_slots << 3)
        self.header_read = 0
        self.frames_read = 0
        self.block_remaining = 0
        self.block_type = BLOCKTYPE_INVALID
        self.intel_curpos = 0
        self.intel_started = 0
        self.intel_filesize = 0

        self.PRETREE_table = [0] * ((1 << PRETREE_TABLEBITS) + (PRETREE_MAXSYMBOLS << 1))
        self.PRETREE_len = [0] * (PRETREE_MAXSYMBOLS + LENTABLE_SAFETY)
        self.MAINTREE_table = [0] * ((1 << MAINTREE_TABLEBITS) + (MAINTREE_MAXSYMBOLS << 1))
        self.MAINTREE_len = [0] * (MAINTREE_MAXSYMBOLS + LENTABLE_SAFETY)
        self.LENGTH_table = [0] * ((1 << LENGTH_TABLEBITS) + (LENGTH_MAXSYMBOLS << 1))
        self.LENGTH_len = [0] * (LENGTH_MAXSYMBOLS + LENTABLE_SAFETY)
        self.ALIGNED_table = [0] * ((1 << ALIGNED_TABLEBITS) + (ALIGNED_MAXSYMBOLS << 1))
        self.ALIGNED_len = [0] * (ALIGNED_MAXSYMBOLS + LENTABLE_SAFETY)

        self.window = bytearray([0xDC]) * wndsize
        self.window_size = wndsize
        self.window_posn = 0

    # ---------------------------------------------------------- decode tables
    def make_decode_table(self, nsyms, nbits, length, table) -> int:
        bit_num = 1
        fill = 0
        pos = 0
        table_mask = 1 << nbits
        bit_mask = table_mask >> 1
        next_symbol = bit_mask

        while bit_num <= nbits:
            for sym in range(nsyms):
                if length[sym] == bit_num:
                    leaf = pos
                    pos += bit_mask
                    if pos > table_mask:
                        return 1
                    fill = bit_mask
                    while fill > 0:
                        table[leaf] = sym
                        leaf += 1
                        fill -= 1
            bit_mask >>= 1
            bit_num += 1

        if pos != table_mask:
            for sym in range(pos, table_mask):
                table[sym] = 0
            pos <<= 16
            table_mask <<= 16
            bit_mask = 1 << 15
            while bit_num <= 16:
                for sym in range(nsyms):
                    if length[sym] == bit_num:
                        leaf = pos >> 16
                        fill = 0
                        while fill < bit_num - nbits:
                            if table[leaf] == 0:
                                table[next_symbol << 1] = 0
                                table[(next_symbol << 1) + 1] = 0
                                table[leaf] = next_symbol
                                next_symbol += 1
                            leaf = table[leaf] << 1
                            if (pos >> (15 - fill)) & 1:
                                leaf += 1
                            fill += 1
                        table[leaf] = sym
                        pos += bit_mask
                        if pos > table_mask:
                            return 1
                bit_mask >>= 1
                bit_num += 1

        if pos == table_mask:
            return 0
        for sym in range(nsyms):
            if length[sym] != 0:
                return 1
        return 0

    def read_lengths(self, lens, first, last, bitbuf):
        for x in range(20):
            self.PRETREE_len[x] = bitbuf.read_bits(4)
        self.make_decode_table(PRETREE_MAXSYMBOLS, PRETREE_TABLEBITS,
                               self.PRETREE_len, self.PRETREE_table)
        x = first
        while x < last:
            z = self.read_huff_sym(self.PRETREE_table, self.PRETREE_len,
                                   PRETREE_MAXSYMBOLS, PRETREE_TABLEBITS, bitbuf)
            if z == 17:
                y = bitbuf.read_bits(4) + 4
                while y != 0:
                    lens[x] = 0
                    x += 1
                    y -= 1
            elif z == 18:
                y = bitbuf.read_bits(5) + 20
                while y != 0:
                    lens[x] = 0
                    x += 1
                    y -= 1
            elif z == 19:
                y = bitbuf.read_bits(1) + 4
                z = self.read_huff_sym(self.PRETREE_table, self.PRETREE_len,
                                       PRETREE_MAXSYMBOLS, PRETREE_TABLEBITS, bitbuf)
                z = lens[x] - z
                if z < 0:
                    z += 17
                while y != 0:
                    lens[x] = z & 0xFF
                    x += 1
                    y -= 1
            else:
                z = lens[x] - z
                if z < 0:
                    z += 17
                lens[x] = z & 0xFF
                x += 1

    def read_huff_sym(self, table, lengths, nsyms, nbits, bitbuf) -> int:
        bitbuf.ensure_bits(16)
        i = table[bitbuf.peek_bits(nbits)]
        if i >= nsyms:
            j = 1 << (32 - nbits)
            while True:
                j >>= 1
                i <<= 1
                i |= 1 if (bitbuf.get_buffer() & j) else 0
                if j == 0:
                    return 0
                i = table[i]
                if i < nsyms:
                    break
        j = lengths[i]
        bitbuf.remove_bits(j)
        return i

    # ------------------------------------------------------------- main decode
    def decompress(self, in_data: bytes, in_len: int, out: bytearray, out_len: int) -> int:
        bitbuf = BitBuffer(in_data, 0)
        startpos = bitbuf.pos
        endpos = startpos + in_len

        window = self.window
        window_posn = self.window_posn
        window_size = self.window_size
        R0, R1, R2 = self.R0, self.R1, self.R2

        bitbuf.init_bitstream()

        if self.header_read == 0:
            intel = bitbuf.read_bits(1)
            if intel != 0:
                i = bitbuf.read_bits(16)
                j = bitbuf.read_bits(16)
                self.intel_filesize = (i << 16) | j
            self.header_read = 1

        togo = out_len
        while togo > 0:
            if self.block_remaining == 0:
                if self.block_type == BLOCKTYPE_UNCOMPRESSED:
                    if (self.block_length & 1) == 1:
                        bitbuf.pos += 1  # realign bitstream to word
                    bitbuf.init_bitstream()

                self.block_type = bitbuf.read_bits(3)
                i = bitbuf.read_bits(16)
                j = bitbuf.read_bits(8)
                self.block_remaining = self.block_length = (i << 8) | j

                if self.block_type == BLOCKTYPE_ALIGNED:
                    for i2 in range(8):
                        self.ALIGNED_len[i2] = bitbuf.read_bits(3)
                    self.make_decode_table(ALIGNED_MAXSYMBOLS, ALIGNED_TABLEBITS,
                                           self.ALIGNED_len, self.ALIGNED_table)
                    # fall through to verbatim header
                    self._read_verbatim_header(bitbuf)
                elif self.block_type == BLOCKTYPE_VERBATIM:
                    self._read_verbatim_header(bitbuf)
                elif self.block_type == BLOCKTYPE_UNCOMPRESSED:
                    self.intel_started = 1
                    bitbuf.ensure_bits(16)
                    if bitbuf.get_bits_left() > 16:
                        bitbuf.pos -= 2
                    R0 = self._read_u32_le(bitbuf)
                    R1 = self._read_u32_le(bitbuf)
                    R2 = self._read_u32_le(bitbuf)
                else:
                    return -1

            # buffer exhaustion check
            if bitbuf.pos > startpos + in_len:
                if bitbuf.pos > startpos + in_len + 2 or bitbuf.get_bits_left() < 16:
                    return -1

            this_run = self.block_remaining
            while this_run > 0 and togo > 0:
                if this_run > togo:
                    this_run = togo
                togo -= this_run
                self.block_remaining -= this_run

                window_posn &= window_size - 1
                if (window_posn + this_run) > window_size:
                    return -1

                if self.block_type in (BLOCKTYPE_VERBATIM, BLOCKTYPE_ALIGNED):
                    while this_run > 0:
                        main_element = self.read_huff_sym(
                            self.MAINTREE_table, self.MAINTREE_len,
                            MAINTREE_MAXSYMBOLS, MAINTREE_TABLEBITS, bitbuf)
                        if main_element < NUM_CHARS:
                            window[window_posn] = main_element
                            window_posn += 1
                            this_run -= 1
                        else:
                            main_element -= NUM_CHARS
                            match_length = main_element & NUM_PRIMARY_LENGTHS
                            if match_length == NUM_PRIMARY_LENGTHS:
                                length_footer = self.read_huff_sym(
                                    self.LENGTH_table, self.LENGTH_len,
                                    LENGTH_MAXSYMBOLS, LENGTH_TABLEBITS, bitbuf)
                                match_length += length_footer
                            match_length += MIN_MATCH
                            match_offset = main_element >> 3

                            if match_offset > 2:
                                if self.block_type == BLOCKTYPE_ALIGNED:
                                    extra = EXTRA_BITS[match_offset]
                                    match_offset = POSITION_BASE[match_offset] - 2
                                    if extra > 3:
                                        extra -= 3
                                        verbatim_bits = bitbuf.read_bits(extra)
                                        match_offset += verbatim_bits << 3
                                        aligned_bits = self.read_huff_sym(
                                            self.ALIGNED_table, self.ALIGNED_len,
                                            ALIGNED_MAXSYMBOLS, ALIGNED_TABLEBITS, bitbuf)
                                        match_offset += aligned_bits
                                    elif extra == 3:
                                        aligned_bits = self.read_huff_sym(
                                            self.ALIGNED_table, self.ALIGNED_len,
                                            ALIGNED_MAXSYMBOLS, ALIGNED_TABLEBITS, bitbuf)
                                        match_offset += aligned_bits
                                    elif extra > 0:
                                        verbatim_bits = bitbuf.read_bits(extra)
                                        match_offset += verbatim_bits
                                    else:
                                        match_offset = 1
                                else:
                                    if match_offset != 3:
                                        extra = EXTRA_BITS[match_offset]
                                        verbatim_bits = bitbuf.read_bits(extra)
                                        match_offset = POSITION_BASE[match_offset] - 2 + verbatim_bits
                                    else:
                                        match_offset = 1
                                R2, R1, R0 = R1, R0, match_offset
                            elif match_offset == 0:
                                match_offset = R0
                            elif match_offset == 1:
                                match_offset = R1
                                R1, R0 = R0, match_offset
                            else:  # match_offset == 2
                                match_offset = R2
                                R2, R0 = R0, match_offset

                            rundest = window_posn
                            this_run -= match_length

                            if window_posn >= match_offset:
                                runsrc = rundest - match_offset
                            else:
                                runsrc = rundest + (window_size - match_offset)
                                copy_length = match_offset - window_posn
                                if copy_length < match_length:
                                    match_length -= copy_length
                                    window_posn += copy_length
                                    while copy_length > 0:
                                        window[rundest] = window[runsrc]
                                        rundest += 1
                                        runsrc += 1
                                        copy_length -= 1
                                    runsrc = 0
                            window_posn += match_length
                            while match_length > 0:
                                window[rundest] = window[runsrc]
                                rundest += 1
                                runsrc += 1
                                match_length -= 1
                elif self.block_type == BLOCKTYPE_UNCOMPRESSED:
                    if bitbuf.pos + this_run > endpos:
                        return -1
                    chunk = in_data[bitbuf.pos:bitbuf.pos + this_run]
                    window[window_posn:window_posn + this_run] = chunk
                    bitbuf.pos += this_run
                    window_posn += this_run
                else:
                    return -1

        if togo != 0:
            return -1
        start_window_pos = window_posn
        if start_window_pos == 0:
            start_window_pos = window_size
        start_window_pos -= out_len
        out.extend(window[start_window_pos:start_window_pos + out_len])

        self.window_posn = window_posn
        self.R0, self.R1, self.R2 = R0, R1, R2

        # intel E8 translation (XNB data has intel_filesize == 0, so no-op;
        # kept faithful to the reference port)
        self.frames_read += 1
        if (self.frames_read - 1 < 32768) and self.intel_filesize != 0:
            if out_len <= 6 or self.intel_started == 0:
                self.intel_curpos += out_len
            else:
                dataend = out_len - 10
                curpos = self.intel_curpos
                self.intel_curpos = curpos + out_len
                # reference implementation is unfinished; not used for XNB
                _ = dataend
            return -1
        return 0

    def _read_verbatim_header(self, bitbuf: BitBuffer):
        self.read_lengths(self.MAINTREE_len, 0, 256, bitbuf)
        self.read_lengths(self.MAINTREE_len, 256, self.main_elements, bitbuf)
        self.make_decode_table(MAINTREE_MAXSYMBOLS, MAINTREE_TABLEBITS,
                               self.MAINTREE_len, self.MAINTREE_table)
        if self.MAINTREE_len[0xE8] != 0:
            self.intel_started = 1
        self.read_lengths(self.LENGTH_len, 0, NUM_SECONDARY_LENGTHS, bitbuf)
        self.make_decode_table(LENGTH_MAXSYMBOLS, LENGTH_TABLEBITS,
                               self.LENGTH_len, self.LENGTH_table)

    @staticmethod
    def _read_u32_le(bitbuf: BitBuffer) -> int:
        lo = bitbuf.stream[bitbuf.pos] if bitbuf.pos < len(bitbuf.stream) else 0xFF
        ml = bitbuf.stream[bitbuf.pos + 1] if bitbuf.pos + 1 < len(bitbuf.stream) else 0xFF
        mh = bitbuf.stream[bitbuf.pos + 2] if bitbuf.pos + 2 < len(bitbuf.stream) else 0xFF
        hi = bitbuf.stream[bitbuf.pos + 3] if bitbuf.pos + 3 < len(bitbuf.stream) else 0xFF
        bitbuf.pos += 4
        return lo | (ml << 8) | (mh << 16) | (hi << 24)


def decompress_xnb_lzx(data: bytes, expected_size: int) -> bytes:
    """Decompress the payload of an LZX-compressed XNB file.

    `data` starts at the int32 decompressedSize field (offset 10 of the file).
    """
    # layout per MonoGame: header(6) + xnbLength(4) + decompressedSize(4) + blocks
    decompressed_size = struct.unpack_from("<i", data, 0)[0]
    if decompressed_size != expected_size:
        raise ValueError(f"unexpected decompressed size {decompressed_size}")
    stream = data[4:]
    # MonoGame: compressedSize = xnbLength - 14; with data starting at offset
    # 10 of the file, len(stream) equals exactly that.
    compressed_size = len(stream)

    dec = LzxDecoder(16)
    out = bytearray()
    start = 0
    pos = 0
    while pos - start < compressed_size:
        if pos + 2 > len(stream):
            break
        hi = stream[pos]
        lo = stream[pos + 1]
        block_size = (hi << 8) | lo
        frame_size = 0x8000
        if hi == 0xFF:
            hi = lo
            lo = stream[pos + 2] if pos + 2 < len(stream) else 0
            frame_size = (hi << 8) | lo
            hi = stream[pos + 3] if pos + 3 < len(stream) else 0xFF
            lo = stream[pos + 4] if pos + 4 < len(stream) else 0xFF
            block_size = (hi << 8) | lo
            pos += 5
        else:
            pos += 2
        if block_size == 0 or frame_size == 0:
            break
        before = len(out)
        rc = dec.decompress(stream[pos:pos + block_size], block_size, out, frame_size)
        if rc != 0:
            # reference decoder returns -1 after finishing an intel-transform
            # frame; only fail if no progress was made
            if len(out) == before:
                raise ValueError(f"LZX block failed (rc={rc})")
        pos += block_size
    if len(out) != decompressed_size:
        raise ValueError(f"decompressed {len(out)} bytes, expected {decompressed_size}")
    return bytes(out)
