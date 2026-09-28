"""Prove the banner is Conway's Game of Life:  python -m life.verify

Checks, each against something independent of the code that produced it:

1. rules      — a second, deliberately naive B3/S23 implementation (explicit
                neighbour loops over a dense grid) agrees with ``life.engine``
                on every displayed generation: frame N+1 = Conway(frame N).
2. gif        — both published GIFs (dark and light) are decoded back into
                cells from their pixels. Every cell square must be one flat
                colour — a live colour, or the dead colour / a trail colour —
                and every gap pixel background, so each image is an exact
                binary picture of the state. Decoded frame N+1 must equal
                Conway(decoded frame N) on every cell whose neighbourhood is
                inside the picture — including last frame → first frame.
3. loop       — the window at START + LOOP equals the window at START, and it
                renders pixel-identically in both themes (colours and trails
                included), so the GIF's wrap-around is a genuine Conway step.
4. print job  — the salvo, flown in from far away with nothing else around,
                turns the seed block into a honey farm and back, twice a loop.
5. satellite  — every copy of the satellite leaves the window intact.
6. manifest   — decoded frames match the per-generation hashes in
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
ASSETS = ROOT / "assets"
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


def decode_frames(path: Path, view, theme) -> list[np.ndarray]:
    """Alive/dead grid of every frame, recovered from pixels.

    Raises unless each cell square is one flat colour — one of the theme's live
    colours, or its dead colour or a trail colour (trails are dead cells) — and
    every grid-gap pixel is background: the picture must be an exact binary
    image of the state, nothing blended or blurred.
    """
    live_set, dead_set = theme.live_colours(), theme.dead_colours()
    if live_set & dead_set:
        raise AssertionError(f"{theme.name} theme uses a colour for both live and dead cells")
    live, dead = np.array(sorted(live_set)), np.array(sorted(dead_set))
    background = np.array(theme.colours()[0])
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
            is_dead = (colour[:, :, None, :] == dead[None, None]).all(-1).any(-1)
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


def check_gif(path: Path, view, frames, theme) -> tuple[str, list[set]]:
    grids = decode_frames(path, view, theme)
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
    return (f"{path.name}: {len(decoded)} frames decoded from pixels; {checked:,} cell updates "
            "checked against B3/S23, including the wrap-around from the last frame to the first",
            decoded)


def check_loop(view, zones, frames, render_frame, themes) -> str:
    from .renderer import base_image
    first, closing = frames[0], frames[-1]
    wa = window(first.state, view.x0, view.y0, view.cols, view.rows)
    wb = window(closing.state, view.x0, view.y0, view.cols, view.rows)
    if wa != wb:
        raise AssertionError("window(START + LOOP) != window(START)")
    grid = (0, 0, *view.grid_size)       # the caption shows the generation number
    for theme in themes:
        base = base_image(view, theme)
        ia = render_frame(view, zones, first, base)
        ib = render_frame(view, zones, closing, base)
        if ia.crop(grid).tobytes() != ib.crop(grid).tobytes():
            raise AssertionError(f"{theme.name}: loop closes on the right cells but renders differently")
    return (f"gen {closing.generation} window == gen {first.generation} window "
            f"({len(wa)} live cells) and renders pixel-identically in "
            f"{' and '.join(t.name for t in themes)}")


def check_print_job() -> str:
    """Fly one loop's print jobs in from far away, with nothing else around."""
    seed = BLOCK.at(*comp.SEED_AT)
    sx, sy = comp.SEED_AT
    lead = 400                                   # every glider starts ≥100 diagonals away
    jobs = comp.LOOP // comp.PRINT_PERIOD
    state = set(seed)
    for k in range(jobs):
        for release, g in comp.print_job_gliders():
            state |= comp.rewind_glider(g, lead + k * comp.PRINT_PERIOD + release)
    state = frozenset(state)
    t = 0
    for k in range(jobs):
        farm_at = lead + k * comp.PRINT_PERIOD + comp.PRINT_SCHEDULE[1] - 30
        state, t = advance(state, farm_at - t), farm_at
        farm = window(state, sx - 12, sy - 14, 26, 20)   # the build volume only
        beehives = sum(1 for dx in range(-8, 9) for dy in range(-12, 6)
                       for hive in (BEEHIVE, BEEHIVE.rotate(1)) if hive.at(sx + dx, sy + dy) <= farm)
        if len(farm) != 24 or beehives != 4:
            raise AssertionError(f"job {k + 1}: expected a honey farm (4 beehives) at gen {farm_at}")
    end = advance(state, lead + comp.LOOP - t)
    if end != seed:
        raise AssertionError("print jobs do not return to the seed block")
    return (f"{jobs} jobs per loop, 5 gliders each: block → honey farm (4 beehives) → … → "
            "the identical block")


def check_satellite() -> str:
    """Each satellite copy, 340 cells after entering, is still exactly an LWSS."""
    scene = comp.build_scene()
    entry = comp.satellite_entry()
    due = {comp.START + k * comp.LOOP + comp.SATELLITE_TIME + 4 * 170: k
           for k in comp.SATELLITE_COPIES if k <= 1}
    state = scene.cells
    t = 0
    for gen in sorted(due):
        state, t = advance(state, gen - t), gen
        expected = frozenset((x + 340, y) for x, y in entry)
        x0 = min(x for x, _ in expected) - 6
        if window(state, x0, -4, 20, 14) != expected:
            raise AssertionError(f"satellite copy {due[gen]} did not survive its pass")
    return f"{len(due)} satellite passes cross the sky and leave intact"


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
    from .generate import GIF_NAMES, render_frame, simulate, view, zone_map
    from .renderer import THEMES

    v = view()
    zones = zone_map(v)
    print("simulating …", flush=True)
    frames = simulate()
    results = [("rules", lambda: check_rules(frames))]
    decoded: list[set] = []

    def gif(theme):
        def run():
            text, d = check_gif(ASSETS / GIF_NAMES[theme.name], v, frames, theme)
            if not decoded:
                decoded.extend(d)
            return text
        return run

    results += [(f"gif {t.name}", gif(t)) for t in THEMES]
    results += [
        ("loop", lambda: check_loop(v, zones, frames, render_frame, THEMES)),
        ("print job", check_print_job),
        ("satellite", check_satellite),
        ("manifest", lambda: check_manifest(decoded)),
    ]
    ok = True
    for name, fn in results:
        try:
            print(f"  ✓ {name:<10} {fn()}", flush=True)
        except AssertionError as e:
            ok = False
            print(f"  ✗ {name:<10} {e}", flush=True)
    print("verified: every displayed frame is an exact Conway generation" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
