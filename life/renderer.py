"""Turns Life states into banner frames.

Rendering is a pure function of (state, ages, trails, generation). Colour is
visual metadata only, never simulation state:

* hue comes from the *region* a cell is in (rack, stream, printer, drone, sky…);
* brightness comes from how long a live cell has been alive;
* a *trail* is a dead cell that was alive one or two generations ago, drawn as a
  dim square of its region's hue.

A cell is drawn in a live colour if and only if it is alive, as one crisp
square. ``verify.decode_frames`` reads the finished GIFs back into alive/dead
cells (trails count as dead) to prove exactly that.
"""

from __future__ import annotations

import colorsys
from dataclasses import dataclass
from typing import Callable

from PIL import Image, ImageDraw

from .engine import Cell, State
from .pixelfont import draw_text, text_width

# Regions, in palette order. composition.zone_of() assigns one to every cell.
ZONES = ("systems", "stream", "making", "job", "flight", "sky", "meteor", "orbit")
LIVE_CLASSES = ("newborn", "young", "active", "recent", "settled")
TRAILS = 2
# Only things that travel leave trails: gliders, meteors and the satellite get comet
# tails, while oscillators (which would just smear in place) do not.
TRAIL_ZONES = ("stream", "job", "meteor", "orbit")
AGE_BOUNDS = (1, 3, 29, 199)        # upper ages of newborn, young, active, recent

BG, DEAD, CAPTION = 0, 1, 2
FIRST_ZONE = 3
PER_ZONE = len(LIVE_CLASSES) + TRAILS


def age_class(age: int) -> int:
    """0…4: newborn, young (2–3), active (4–29), recent (30–199), settled (200+)."""
    for i, bound in enumerate(AGE_BOUNDS):
        if age <= bound:
            return i
    return len(AGE_BOUNDS)


def live_index(zone: int, age: int) -> int:
    return FIRST_ZONE + zone * PER_ZONE + age_class(age)


def trail_index(zone: int, generations_dead: int) -> int:
    return FIRST_ZONE + zone * PER_ZONE + len(LIVE_CLASSES) + generations_dead - 1


def _hls(h: float, l: float, s: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hls_to_rgb(h / 360, l, s)
    return round(r * 255), round(g * 255), round(b * 255)


def _hex(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


# Hue in degrees and a saturation multiplier, per region.
HUES = {
    "systems": (172, 1.0),   # teal: the rack and its gun
    "stream": (194, 1.0),    # cyan: information in flight
    "making": (34, 1.0),     # amber: the printer and what it makes
    "job": (18, 1.0),        # orange: print-job gliders, like filament
    "flight": (92, 0.9),     # lime: the drone
    "sky": (248, 0.9),       # indigo-violet: stars, Orion, M42, the galaxy
    "meteor": (46, 1.0),     # gold
    "orbit": (215, 0.18),    # silver: the satellite
}


@dataclass(frozen=True)
class Theme:
    name: str
    background: str
    dead: str
    caption: str
    live: tuple[tuple[float, float], ...]      # (lightness, saturation) per age class
    trail: tuple[tuple[float, float], ...]     # (lightness, saturation) per trail step

    def colours(self) -> list[tuple[int, int, int]]:
        out = [_hex(self.background), _hex(self.dead), _hex(self.caption)]
        for zone in ZONES:
            h, sat = HUES[zone]
            out += [_hls(h, l, s * sat) for l, s in self.live]
            out += [_hls(h, l, s * sat) for l, s in self.trail]
        return out

    def palette_bytes(self) -> list[int]:
        flat = [v for rgb in self.colours() for v in rgb]
        return flat + [0] * (768 - len(flat))

    def live_colours(self) -> set:
        c = self.colours()
        return {c[FIRST_ZONE + z * PER_ZONE + i] for z in range(len(ZONES))
                for i in range(len(LIVE_CLASSES))}

    def dead_colours(self) -> set:
        c = self.colours()
        return {c[DEAD]} | {c[FIRST_ZONE + z * PER_ZONE + len(LIVE_CLASSES) + i]
                            for z in range(len(ZONES)) for i in range(TRAILS)}


DARK = Theme(
    "dark", background="#0a0d12", dead="#10141b", caption="#4a5568",
    live=((0.70, 0.95), (0.88, 0.80), (0.64, 0.55), (0.60, 0.90), (0.36, 0.30)),
    trail=((0.24, 0.55), (0.17, 0.45)),
)
LIGHT = Theme(
    "light", background="#ffffff", dead="#f2f4f7", caption="#8a94a3",
    live=((0.46, 0.95), (0.27, 0.80), (0.40, 0.60), (0.45, 0.90), (0.66, 0.28)),
    trail=((0.82, 0.60), (0.89, 0.50)),
)
THEMES = (DARK, LIGHT)


@dataclass(frozen=True)
class View:
    """Which world cells are drawn and how big they are."""
    x0: int = 0
    y0: int = 0
    cols: int = 280
    rows: int = 104
    pitch: int = 5                 # pixels per cell, including the gap
    cell: int = 4                  # drawn square size; pitch - cell = grid gap
    footer: int = 20               # caption strip under the grid (no cells there)

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


class ZoneMap:
    """Region index of every cell in the view, computed once from a geometry function."""

    def __init__(self, view: View, zone_of: Callable[[Cell], str]):
        self.index = {(x, y): ZONES.index(zone_of((x, y)))
                      for x in range(view.x0, view.x0 + view.cols)
                      for y in range(view.y0, view.y0 + view.rows)}

    def __getitem__(self, c: Cell) -> int:
        return self.index[c]


@dataclass(frozen=True)
class Label:
    """A run of caption text: ((text, zone name or None for the plain caption colour), …)."""
    parts: tuple[tuple[str, str | None], ...]
    x: int                        # anchor in pixels
    align: str = "left"           # left, centre or right of the anchor


def base_image(view: View, theme: Theme) -> Image.Image:
    img = Image.new("P", view.size, BG)
    img.putpalette(theme.palette_bytes())
    d = ImageDraw.Draw(img)
    for r in range(view.rows):
        for c in range(view.cols):
            x, y = c * view.pitch, r * view.pitch
            d.rectangle((x, y, x + view.cell - 1, y + view.cell - 1), fill=DEAD)
    return img


def render(view: View, zones: ZoneMap, state: State, ages: dict[Cell, int],
           trails: dict[Cell, int], base: Image.Image,
           labels: tuple[Label, ...] = ()) -> Image.Image:
    img = base.copy()
    d = ImageDraw.Draw(img)
    s = view.cell - 1
    trail_zones = {ZONES.index(z) for z in TRAIL_ZONES}
    for c, k in trails.items():
        if view.contains(c) and zones[c] in trail_zones:
            x, y = view.cell_origin(c)
            d.rectangle((x, y, x + s, y + s), fill=trail_index(zones[c], k))
    for c in state:
        if view.contains(c):
            x, y = view.cell_origin(c)
            d.rectangle((x, y, x + s, y + s), fill=live_index(zones[c], ages.get(c, 1)))
    for label in labels:
        _draw_label(d, view, label)
    return img


def _label_colour(zone: str | None) -> int:
    if zone is None:
        return CAPTION
    return FIRST_ZONE + ZONES.index(zone) * PER_ZONE + LIVE_CLASSES.index("recent")


def _draw_label(d: ImageDraw.ImageDraw, view: View, label: Label, scale: int = 2) -> None:
    width = text_width("".join(t for t, _ in label.parts), scale)
    x = {"left": label.x, "centre": label.x - width // 2, "right": label.x - width}[label.align]
    y = view.grid_size[1] + (view.footer - 5 * scale) // 2
    for text, zone in label.parts:
        draw_text(d, x, y, text, _label_colour(zone), scale=scale)
        x += text_width(text, scale) + scale      # one tracking gap between runs
