"""Turns Life states into banner frames.

Rendering is a pure function of (state, ages, generation). Colour encodes only
visual metadata — how long a cell has been alive — never simulation state: a
cell is drawn if and only if it is alive, and every live cell is drawn as the
same crisp square. ``verify.decode_frames`` reads the finished GIF back into
alive/dead cells to prove exactly that.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PIL import Image, ImageDraw

from .engine import Cell, State
from .pixelfont import draw_text, text_width


def _rgb(hex_colour: str) -> tuple[int, int, int]:
    h = hex_colour.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


@dataclass(frozen=True)
class Palette:
    background: str = "#0a0d12"
    dead: str = "#10141b"          # faint dead-cell squares: the grid is always visible
    newborn: str = "#a996ff"       # age 1 — OneCreations violet
    young: str = "#f2f4f8"         # age 2–3
    active: str = "#b9c3d1"        # age 4–29
    recent: str = "#8d80d9"        # age 30–199: new, stable things (the printed part)
    settled: str = "#4b576b"       # age ≥ 200: infrastructure that has always been there
    caption: str = "#465164"

    def ordered(self) -> list[str]:
        # index order is part of the GIF's palette; keep it stable
        return [self.background, self.dead, self.newborn, self.young,
                self.active, self.recent, self.settled, self.caption]


BG, DEAD, NEWBORN, YOUNG, ACTIVE, RECENT, SETTLED, CAPTION = range(8)
AGE_BOUNDS = (1, 3, 29, 199)       # upper ages of NEWBORN, YOUNG, ACTIVE, RECENT


def age_class(age: int) -> int:
    """Palette index for a live cell that has been alive ``age`` generations."""
    for bound, index in zip(AGE_BOUNDS, (NEWBORN, YOUNG, ACTIVE, RECENT)):
        if age <= bound:
            return index
    return SETTLED


@dataclass(frozen=True)
class View:
    """Which world cells are drawn and how big they are."""
    x0: int = 0
    y0: int = 0
    cols: int = 280
    rows: int = 96
    pitch: int = 5                 # pixels per cell, including the gap
    cell: int = 4                  # drawn square size; pitch - cell = grid gap
    footer: int = 20               # caption strip under the grid (no cells there)
    palette: Palette = field(default_factory=Palette)

    @property
    def grid_size(self) -> tuple[int, int]:
        return self.cols * self.pitch, self.rows * self.pitch

    @property
    def size(self) -> tuple[int, int]:
        return self.cols * self.pitch, self.rows * self.pitch + self.footer

    def contains(self, c: Cell) -> bool:
        return self.x0 <= c[0] < self.x0 + self.cols and self.y0 <= c[1] < self.y0 + self.rows

    def cell_origin(self, c: Cell) -> tuple[int, int]:
        """Top-left pixel of the square for world cell ``c``."""
        return (c[0] - self.x0) * self.pitch, (c[1] - self.y0) * self.pitch


@dataclass(frozen=True)
class Caption:
    """One line of pixel text in the footer strip, below the grid."""
    left: str
    right: str
    scale: int = 2
    margin: int = 10


def palette_bytes(p: Palette) -> list[int]:
    flat: list[int] = []
    for colour in p.ordered():
        flat.extend(_rgb(colour))
    return flat + [0] * (768 - len(flat))


def base_image(view: View) -> Image.Image:
    img = Image.new("P", view.size, BG)
    img.putpalette(palette_bytes(view.palette))
    d = ImageDraw.Draw(img)
    for r in range(view.rows):
        for c in range(view.cols):
            x, y = c * view.pitch, r * view.pitch
            d.rectangle((x, y, x + view.cell - 1, y + view.cell - 1), fill=DEAD)
    return img


def render(view: View, state: State, ages: dict[Cell, int], base: Image.Image | None = None,
           caption: Caption | None = None, generation_text: str = "") -> Image.Image:
    img = (base or base_image(view)).copy()
    d = ImageDraw.Draw(img)
    s = view.cell - 1
    for c in state:
        if not view.contains(c):
            continue
        x, y = view.cell_origin(c)
        d.rectangle((x, y, x + s, y + s), fill=age_class(ages.get(c, 1)))
    if caption:
        _draw_caption(d, view, caption, generation_text)
    return img


def _draw_caption(d: ImageDraw.ImageDraw, view: View, caption: Caption,
                  generation_text: str) -> None:
    w, _ = view.size
    sc, m = caption.scale, caption.margin
    y = view.grid_size[1] + (view.footer - 5 * sc) // 2
    draw_text(d, m, y, caption.left + generation_text, CAPTION, scale=sc)
    draw_text(d, w - m - text_width(caption.right, sc), y, caption.right, CAPTION, scale=sc)
