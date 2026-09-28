"""Canonical Conway patterns and the geometry to place them.

Patterns are written as plaintext pictures (``#`` alive, ``.`` dead) so the
source reads like the thing it draws. A :class:`Pattern` is immutable; the
transforms return new patterns, and :meth:`Pattern.at` places the pattern's
top-left corner at a world coordinate.

x grows to the right, y grows downwards (screen convention). Under that
convention the glider below travels towards +x, +y ("south-east").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .engine import Cell, State


@dataclass(frozen=True)
class Pattern:
    name: str
    cells: State

    # --- construction -----------------------------------------------------

    @classmethod
    def from_picture(cls, name: str, picture: str) -> "Pattern":
        rows = [r.strip() for r in picture.strip().splitlines()]
        cells = frozenset(
            (x, y) for y, row in enumerate(rows) for x, ch in enumerate(row) if ch in "#O*"
        )
        return cls(name, cells).normalised()

    @classmethod
    def from_rle(cls, name: str, rle: str) -> "Pattern":
        """Minimal RLE reader (B3/S23 two-state patterns only)."""
        body = "".join(
            line.strip() for line in rle.strip().splitlines()
            if line.strip() and not line.startswith(("#", "x"))
        )
        cells, x, y, run = set(), 0, 0, ""
        for ch in body:
            if ch.isdigit():
                run += ch
                continue
            n = int(run) if run else 1
            run = ""
            if ch == "b":
                x += n
            elif ch == "o":
                cells.update((x + i, y) for i in range(n))
                x += n
            elif ch == "$":
                y, x = y + n, 0
            elif ch == "!":
                break
        return cls(name, frozenset(cells)).normalised()

    # --- geometry ---------------------------------------------------------

    @property
    def width(self) -> int:
        return max(x for x, _ in self.cells) + 1 if self.cells else 0

    @property
    def height(self) -> int:
        return max(y for _, y in self.cells) + 1 if self.cells else 0

    def normalised(self) -> "Pattern":
        if not self.cells:
            return self
        mx = min(x for x, _ in self.cells)
        my = min(y for _, y in self.cells)
        return Pattern(self.name, frozenset((x - mx, y - my) for x, y in self.cells))

    def rotate(self, quarter_turns: int = 1) -> "Pattern":
        """Rotate clockwise (on screen) by 90° per quarter turn."""
        cells = self.cells
        for _ in range(quarter_turns % 4):
            cells = frozenset((-y, x) for x, y in cells)
        return Pattern(self.name, cells).normalised()

    def flip_x(self) -> "Pattern":
        """Mirror left↔right."""
        return Pattern(self.name, frozenset((-x, y) for x, y in self.cells)).normalised()

    def flip_y(self) -> "Pattern":
        """Mirror top↔bottom."""
        return Pattern(self.name, frozenset((x, -y) for x, y in self.cells)).normalised()

    def transpose(self) -> "Pattern":
        """Mirror across the main diagonal."""
        return Pattern(self.name, frozenset((y, x) for x, y in self.cells)).normalised()

    def at(self, x: int, y: int) -> State:
        """World cells with the pattern's top-left corner at (x, y)."""
        return frozenset((cx + x, cy + y) for cx, cy in self.cells)

    def __len__(self) -> int:
        return len(self.cells)


def union(*parts: Iterable[Cell]) -> State:
    out: set[Cell] = set()
    for p in parts:
        out.update(p)
    return frozenset(out)


# --- still lifes (period 1) ---------------------------------------------------

BLOCK = Pattern.from_picture("block", """
##
##
""")

BEEHIVE = Pattern.from_picture("beehive", """
.##.
#..#
.##.
""")

LOAF = Pattern.from_picture("loaf", """
.##.
#..#
.#.#
..#.
""")

BOAT = Pattern.from_picture("boat", """
##.
#.#
.#.
""")

TUB = Pattern.from_picture("tub", """
.#.
#.#
.#.
""")

POND = Pattern.from_picture("pond", """
.##.
#..#
#..#
.##.
""")

# Eater 1 (the "fishhook"), 1971. Absorbs gliders arriving from the upper left
# of its hook and repairs itself within four generations.
EATER = Pattern.from_picture("eater 1", """
##..
#.#.
..#.
..##
""")

# --- oscillators ----------------------------------------------------------------

BLINKER = Pattern.from_picture("blinker", "###")                      # p2

TOAD = Pattern.from_picture("toad", """
.###
###.
""")                                                                   # p2

BEACON = Pattern.from_picture("beacon", """
##..
##..
..##
..##
""")                                                                   # p2

CLOCK = Pattern.from_picture("clock", """
..#.
#.#.
.#.#
.#..
""")                                                                   # p2

PULSAR = Pattern.from_picture("pulsar", """
..###...###..
.............
#....#.#....#
#....#.#....#
#....#.#....#
..###...###..
.............
..###...###..
#....#.#....#
#....#.#....#
#....#.#....#
.............
..###...###..
""")                                                                   # p3

# Shown as a vertical 10-cell column; it breathes with period 15.
PENTADECATHLON = Pattern.from_picture("pentadecathlon", """
..#....#..
##.####.##
..#....#..
""").rotate(1)                                                         # p15

# Jan Kok, 1971: sixteen cells that wind and unwind like a spiral galaxy. Period 8;
# its arms reach two cells beyond the 9×9 box while it turns.
KOKS_GALAXY = Pattern.from_picture("Kok's galaxy", """
##.######
##.######
##.......
##.....##
##.....##
##.....##
.......##
######.##
######.##
""")                                                                   # p8

MOLD = Pattern.from_picture("mold", """
...##.
..#..#
#..#.#
....#.
#.##..
.#....
""")                                                                   # p4

OCTAGON_2 = Pattern.from_picture("octagon 2", """
...##...
..#..#..
.#....#.
#......#
#......#
.#....#.
..#..#..
...##...
""")                                                                   # p5

# --- spaceships -----------------------------------------------------------------

GLIDER = Pattern.from_picture("glider", """
.#.
..#
###
""")                                                                   # c/4, moves (+1, +1)

def glider_heading(direction: str) -> Pattern:
    """The glider reflected to travel "se", "sw", "ne" or "nw"."""
    return {"se": GLIDER, "sw": GLIDER.flip_x(), "ne": GLIDER.flip_y(),
            "nw": GLIDER.flip_x().flip_y()}[direction]


LWSS = Pattern.from_picture("lightweight spaceship", """
.#..#
#....
#...#
####.
""")                                                                   # c/2, moves (-1, 0)

# --- guns -------------------------------------------------------------------------

# Bill Gosper, 1970: the first known finite pattern with unbounded growth.
# Period 30; in this orientation it fires one south-east glider every 30 generations.
GOSPER_GLIDER_GUN = Pattern.from_rle("Gosper glider gun", """
x = 36, y = 9, rule = B3/S23
24bo$22bobo$12b2o6b2o12b2o$11bo3bo4b2o12b2o$2o8bo5bo3b2o$2o8bo3bob2o4bo
bo$10bo5bo7bo$11bo3bo$12b2o!
""")

CATALOGUE: dict[str, tuple[Pattern, int]] = {
    # name: (pattern, period) — period 1 means still life
    "block": (BLOCK, 1),
    "beehive": (BEEHIVE, 1),
    "loaf": (LOAF, 1),
    "boat": (BOAT, 1),
    "tub": (TUB, 1),
    "pond": (POND, 1),
    "eater 1": (EATER, 1),
    "blinker": (BLINKER, 2),
    "toad": (TOAD, 2),
    "beacon": (BEACON, 2),
    "clock": (CLOCK, 2),
    "pulsar": (PULSAR, 3),
    "pentadecathlon": (PENTADECATHLON, 15),
    "mold": (MOLD, 4),
    "octagon 2": (OCTAGON_2, 5),
    "Kok's galaxy": (KOKS_GALAXY, 8),
}
