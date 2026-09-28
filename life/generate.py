"""Regenerate the banner:  python -m life.generate

Writes
    assets/life-banner.gif          dark theme (GitHub dark mode)
    assets/life-banner-light.gif    light theme (GitHub light mode)
    assets/life-banner-preview.png  a still frame with the printed part on the bed
    assets/life-banner.json         manifest: generations, populations, state hashes

One frame per Life generation. The output is deterministic: same composition +
same settings → same states, same manifest and (with the same Pillow version)
the same bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from . import composition as comp
from .engine import State, next_generation, update_ages, window
from .renderer import DARK, THEMES, Label, Theme, View, ZoneMap, base_image, render

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
GIF_NAMES = {"dark": "life-banner.gif", "light": "life-banner-light.gif"}

FRAME_MS = 30                         # one generation per frame (~33 gen/s)
PREVIEW_GEN = comp.START + 110        # honey farm sitting on the bed
TRANSPARENT = 255                     # palette slot used for "unchanged since last frame"


def view() -> View:
    return View(cols=comp.COLS, rows=comp.ROWS)


def zone_map(v: View) -> ZoneMap:
    return ZoneMap(v, comp.zone_function())


@dataclass
class Frame:
    generation: int
    state: State                      # full world state (unbounded plane)
    ages: dict                        # live cell -> generations alive (colour only)
    trails: dict                      # dead cell -> 1 or 2 generations since it died


def simulate(start: int = comp.START, count: int = comp.LOOP + 1) -> list[Frame]:
    """Run the composition from generation 0 and keep generations start … start+count-1."""
    state = comp.build_scene().cells
    ages = update_ages({}, state)
    prev1 = prev2 = frozenset()
    frames = []
    for gen in range(start + count):
        if gen:
            prev2, prev1 = prev1, state
            state = next_generation(state)
            ages = update_ages(ages, state)
        if gen >= start:
            trails = {c: 2 for c in prev2 - prev1 - state}
            trails.update({c: 1 for c in prev1 - state})
            frames.append(Frame(gen, state, ages, trails))
    return frames


def state_hash(cells) -> str:
    return hashlib.sha256(repr(sorted(cells)).encode()).hexdigest()[:16]


def frame_labels(v: View, generation: int) -> tuple[Label, ...]:
    gen = Label(((f"B3/S23 · GEN {generation:04d}", None),), x=v.size[0] - 10, align="right")
    return comp.labels(v.pitch) + (gen,)


def render_frame(v: View, zones: ZoneMap, f: Frame, base: Image.Image) -> Image.Image:
    return render(v, zones, f.state, f.ages, f.trails, base, frame_labels(v, f.generation))


def delta_frames(images):
    """Frame 0 as is; later frames keep only pixels that changed (others transparent).

    With disposal 1 ("leave in place") a GIF viewer composites each frame over the
    previous one, so the picture is identical but long transparent runs compress
    far better than repeating the static scene.
    """
    prev = None
    for im in images:
        cur = im.tobytes()
        if prev is None:
            out = im
        else:
            data = bytes(c if c != p else TRANSPARENT for c, p in zip(cur, prev))
            out = Image.frombytes("P", im.size, data)
            out.putpalette(im.getpalette())
            out.info["transparency"] = TRANSPARENT
        prev = cur
        yield out


def write_gif(images: list[Image.Image], path: Path) -> None:
    frames = list(delta_frames(images))
    frames[0].save(
        path, save_all=True, append_images=frames[1:], duration=FRAME_MS, loop=0,
        disposal=1, transparency=TRANSPARENT, optimize=False,
    )


def render_theme(v: View, zones: ZoneMap, frames: list[Frame], theme: Theme) -> list[Image.Image]:
    base = base_image(v, theme)
    return [render_frame(v, zones, f, base) for f in frames]


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ASSETS)
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    v = view()
    zones = zone_map(v)
    frames = simulate()
    shown, closing = frames[:-1], frames[-1]
    x0, y0 = v.x0, v.y0
    if window(shown[0].state, x0, y0, v.cols, v.rows) != window(closing.state, x0, y0, v.cols, v.rows):
        raise SystemExit("loop is not exact: window(START + LOOP) != window(START)")

    for theme in THEMES:
        gif = args.out / GIF_NAMES[theme.name]
        write_gif(render_theme(v, zones, shown, theme), gif)
        print(f"{gif}: {len(shown)} frames, {v.size[0]}×{v.size[1]}, "
              f"{gif.stat().st_size / 1e6:.2f} MB")
    preview = next(f for f in shown if f.generation == PREVIEW_GEN)
    render_frame(v, zones, preview, base_image(v, DARK)).convert("RGB").save(
        args.out / "life-banner-preview.png", optimize=True)

    manifest = {
        "rule": "B3/S23",
        "view": {"x0": x0, "y0": y0, "cols": v.cols, "rows": v.rows, "pitch": v.pitch,
                 "cell": v.cell, "size": list(v.size)},
        "first_generation": shown[0].generation,
        "generations": len(shown),
        "frame_ms": FRAME_MS,
        "gifs": GIF_NAMES,
        "loop_closes_on_conway_step": True,
        "frames": [{"generation": f.generation,
                    "population_visible": len(window(f.state, x0, y0, v.cols, v.rows)),
                    "window_sha": state_hash(window(f.state, x0, y0, v.cols, v.rows))}
                   for f in shown],
    }
    (args.out / "life-banner.json").write_text(json.dumps(manifest, indent=1) + "\n")


if __name__ == "__main__":
    main()
