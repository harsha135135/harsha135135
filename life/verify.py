"""Prove the banner is Conway's Game of Life:  python -m life.verify

Checks, each against something independent of the code that produced it:

1. rules      — a second, deliberately naive B3/S23 implementation (explicit
                neighbour loops over a dense grid) agrees with ``life.engine``
                on every displayed generation: frame N+1 = Conway(frame N).
2. gif        — the published GIF is decoded back into cells from its pixels.
                Every cell square must be one flat colour (live colour or the
                dead colour) and every gap pixel background, so the image is
                an exact binary picture of the state. Decoded frame N+1 must
                equal Conway(decoded frame N) on every cell whose neighbourhood
                is inside the picture — including last frame → first frame.
3. loop       — the window at START + LOOP equals the window at START, and its
                rendering is pixel-identical, so the GIF's wrap-around is a
                genuine Conway step.
4. print job  — the five-glider salvo, flown in from far away with nothing
                else around, turns the seed block into a honey farm and then
                back into the identical block.
5. manifest   — decoded frames match the per-generation hashes in
                assets/life-banner.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from . import composition as comp
from .engine import advance, window
from .patterns import BEEHIVE, BLOCK

ROOT = Path(__file__).resolve().parent.parent
GIF = ROOT / "assets" / "life-banner.gif"
MANIFEST = ROOT / "assets" / "life-banner.json"


# --- 1. an independent reference implementation ---------------------------------------


def reference_step(live: set) -> set:
    """B3/S23 written out the long way, independent of ``life.engine``.

    Every cell that could change is visited and its eight neighbours are looked
    up one by one; the four rules are then applied literally.
    """
    candidates = {(x + dx, y + dy) for x, y in live for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    out = set()
    for x, y in candidates:
        n = sum((x + dx, y + dy) in live
                for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0))
        alive = (x, y) in live
        if alive and n < 2:
            continue                  # 1. underpopulation
        if alive and n in (2, 3):
            out.add((x, y))           # 2. survival
        elif alive and n > 3:
            continue                  # 3. overpopulation
        elif not alive and n == 3:
            out.add((x, y))           # 4. reproduction
    return out


def grid_step(alive: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Conway on a finite picture (a third implementation: array shifts).

    Returns (next grid, mask of cells whose result is determined by the picture):
    only cells whose whole 3×3 neighbourhood lies inside it.
    """
    a = alive.astype(np.uint8)
    n = np.zeros_like(a)
    n[1:-1, 1:-1] = sum(a[1 + dy:a.shape[0] - 1 + dy, 1 + dx:a.shape[1] - 1 + dx]
                        for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dx, dy) != (0, 0))
    nxt = (n == 3) | ((a == 1) & (n == 2))
    known = np.zeros_like(alive, dtype=bool)
    known[1:-1, 1:-1] = True
    return nxt & known, known


# --- 2. reading the GIF back ----------------------------------------------------------


def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def decode_frames(path: Path, view) -> list[np.ndarray]:
    """Alive/dead grid of every frame, recovered from pixels.

    Raises unless each cell square is one flat colour — a live colour or the dead
    colour — and every grid-gap pixel is background: the picture must be an
    exact binary image of the state, nothing blended or blurred.
    """
    pal = view.palette
    live = np.array([_rgb(c) for c in (pal.newborn, pal.young, pal.active, pal.recent,
                                       pal.settled)])
    dead, background = np.array(_rgb(pal.dead)), np.array(_rgb(pal.background))
    p, s, rows, cols = view.pitch, view.cell, view.rows, view.cols
    frames = []
    with Image.open(path) as im:
        if im.size != view.size:
            raise AssertionError(f"GIF is {im.size}, expected {view.size}")
        for i in range(im.n_frames):
            im.seek(i)
            px = np.asarray(im.convert("RGB"))[:rows * p, :cols * p].astype(int)
            tiles = px.reshape(rows, p, cols, p, 3).transpose(0, 2, 1, 3, 4)
            squares = tiles[:, :, :s, :s]
            corner = squares[:, :, :1, :1]
            if not (squares == corner).all():
                raise AssertionError(f"frame {i}: a cell square is not flat")
            gaps = np.concatenate([tiles[:, :, s:, :].reshape(rows, cols, -1, 3),
                                   tiles[:, :, :, s:].reshape(rows, cols, -1, 3)], axis=2)
            if not (gaps == background).all():
                raise AssertionError(f"frame {i}: something is drawn in the grid gaps")
            colour = corner[:, :, 0, 0]
            is_live = (colour[:, :, None, :] == live[None, None]).all(-1).any(-1)
            is_dead = (colour == dead).all(-1)
            if not (is_live | is_dead).all():
                raise AssertionError(f"frame {i}: a cell has a colour outside the palette")
            frames.append(is_live)
    return frames


def cells_of(grid: np.ndarray, view) -> set:
    ys, xs = np.nonzero(grid)
    return {(int(x) + view.x0, int(y) + view.y0) for x, y in zip(xs, ys)}


# --- the checks ------------------------------------------------------------------------


def check_rules(frames) -> str:
    for a, b in zip(frames, frames[1:]):
        if reference_step(set(a.state)) != set(b.state):
            raise AssertionError(f"generation {b.generation} is not Conway(generation {a.generation})")
    return (f"{len(frames) - 1} transitions (gens {frames[0].generation}–{frames[-1].generation})"
            " match an independent B3/S23 implementation")


def check_gif(path: Path, view, frames) -> tuple[str, list[set]]:
    grids = decode_frames(path, view)
    shown = frames[:-1]
    if len(grids) != len(shown):
        raise AssertionError(f"GIF has {len(grids)} frames, expected {len(shown)}")
    decoded = [cells_of(g, view) for g in grids]
    for d, f in zip(decoded, shown):
        if d != set(window(f.state, view.x0, view.y0, view.cols, view.rows)):
            raise AssertionError(f"GIF frame for gen {f.generation} differs from the simulation")
    checked = 0
    for i in range(len(grids)):
        j = (i + 1) % len(grids)                                    # includes last → first
        want, known = grid_step(grids[i])
        if ((grids[j] & known) != want).any():
            ys, xs = np.nonzero((grids[j] & known) != want)
            raise AssertionError(f"GIF frame {j} is not Conway(frame {i}) at x={xs[:5]}, y={ys[:5]}")
        checked += int(known.sum())
    return (f"{len(decoded)} GIF frames decoded from pixels; {checked:,} cell updates checked "
            "against B3/S23, including the wrap-around from the last frame to the first",
            decoded)


def check_loop(view, frames, render_frame, base) -> str:
    first, closing = frames[0], frames[-1]
    wa = window(first.state, view.x0, view.y0, view.cols, view.rows)
    wb = window(closing.state, view.x0, view.y0, view.cols, view.rows)
    if wa != wb:
        raise AssertionError("window(START + LOOP) != window(START)")
    ia, ib = render_frame(view, first, base), render_frame(view, closing, base)
    # the caption shows the generation number, so compare the grid only
    grid = (0, 0, *view.grid_size)
    if ia.crop(grid).tobytes() != ib.crop(grid).tobytes():
        raise AssertionError("loop closes on the right cells but with different colours")
    return (f"gen {closing.generation} window == gen {first.generation} window "
            f"({len(wa)} live cells) and renders pixel-identically")


def check_print_job() -> str:
    seed = BLOCK.at(*comp.SEED_AT)
    lead = 400                                   # fly every glider in from 100 diagonals away
    state = set(seed)
    for release, g in comp.print_job_gliders():
        state |= comp.rewind_glider(g, release + lead)
    state = frozenset(state)
    farm_at = lead + comp.PRINT_SCHEDULE[1] - 30  # before the second glider comes near
    world = advance(state, farm_at)
    sx, sy = comp.SEED_AT
    farm = window(world, sx - 12, sy - 14, 26, 20)       # the build volume only
    beehives = sum(1 for dx in range(-8, 9) for dy in range(-12, 6)
                   for hive in (BEEHIVE, BEEHIVE.rotate(1)) if hive.at(sx + dx, sy + dy) <= farm)
    if len(farm) != 24 or beehives != 4:
        raise AssertionError(f"expected a honey farm (4 beehives, 24 cells) at gen {farm_at}")
    end = advance(world, lead + comp.LOOP - farm_at)
    if end != seed:
        raise AssertionError("print job does not return to the seed block")
    return "5-glider salvo: block → honey farm (4 beehives) → … → the identical block"


def check_manifest(decoded: list[set]) -> str:
    from .generate import state_hash
    data = json.loads(MANIFEST.read_text())
    if not decoded or len(decoded) != len(data["frames"]):
        raise AssertionError("manifest and GIF frame counts differ (or the GIF check failed)")
    for d, entry in zip(decoded, data["frames"]):
        if state_hash(d) != entry["window_sha"]:
            raise AssertionError(f"manifest hash mismatch at gen {entry['generation']}")
    return f"{len(data['frames'])} frame hashes match assets/life-banner.json"


def main() -> int:
    from .generate import render_frame, simulate, view
    from .renderer import base_image

    v = view()
    print("simulating …", flush=True)
    frames = simulate()
    results = [("rules", lambda: check_rules(frames))]
    decoded: list[set] = []

    def gif():
        text, d = check_gif(GIF, v, frames)
        decoded.extend(d)
        return text

    results += [
        ("gif", gif),
        ("loop", lambda: check_loop(v, frames, render_frame, base_image(v))),
        ("print job", check_print_job),
        ("manifest", lambda: check_manifest(decoded)),
    ]
    ok = True
    for name, fn in results:
        try:
            print(f"  ✓ {name:<9} {fn()}", flush=True)
        except AssertionError as e:
            ok = False
            print(f"  ✗ {name:<9} {e}", flush=True)
    print("verified: every displayed frame is an exact Conway generation" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
