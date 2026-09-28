"""Bit-parallel Life stepper used only by the offline search in tools/.

The banner itself is always simulated by ``life.engine``; anything found here is
re-checked there (and by the tests) before it is used.

A board is one Python int: cell (x, y) is bit ``y * stride + x`` with
``stride = width + 1``. The extra column per row is a permanently dead guard, so
horizontal shifts never wrap live cells into the neighbouring row.
"""

from __future__ import annotations


class Board:
    def __init__(self, width: int, height: int):
        self.w, self.h, self.s = width, height, width + 1
        row = (1 << width) - 1
        self.mask = sum(row << (y * self.s) for y in range(height))
        self.edge = self._edge_mask()

    def _edge_mask(self) -> int:
        m = 0
        for y in range(self.h):
            for x in range(self.w):
                if x < 2 or y < 2 or x >= self.w - 2 or y >= self.h - 2:
                    m |= 1 << (y * self.s + x)
        return m

    def encode(self, cells) -> int:
        b = 0
        for x, y in cells:
            if not (0 <= x < self.w and 0 <= y < self.h):
                raise ValueError(f"cell {(x, y)} outside board")
            b |= 1 << (y * self.s + x)
        return b

    def decode(self, b: int) -> frozenset:
        out, s = [], self.s
        while b:
            low = b & -b
            i = low.bit_length() - 1
            out.append((i % s, i // s))
            b ^= low
        return frozenset(out)

    def step(self, b: int) -> int:
        s = self.s
        s0 = s1 = s2 = 0
        for n in (b << 1, b >> 1, b << s, b >> s,
                  b << (s + 1), b >> (s + 1), b << (s - 1), b >> (s - 1)):
            c0 = s0 & n
            s0 ^= n
            c1 = s1 & c0
            s1 ^= c0
            s2 |= c1
        return s1 & ~s2 & (s0 | b) & self.mask
