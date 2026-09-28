"""Regenerate the banner:  python -m life.generate

Writes
    assets/life-banner.gif          the animation (one frame per Life generation)
    assets/life-banner-preview.png  a still frame with the printed part on the bed
    assets/life-banner.json         manifest: generations, populations, state hashes

The output is deterministic: same composition + same settings → same states,
same manifest and (with the same Pillow version) the same bytes.
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
from .renderer import Caption, View, base_image, render

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

FRAME_MS = 60                         # one generation per frame (~16.7 gen/s)
PREVIEW_GEN = comp.START + 110        # honey farm sitting on the bed
TRANSPARENT = 255                     # palette slot used for "unchanged since last frame"

CAPTION = Caption(left="B3/S23 · GEN ", right="SIMPLE RULES → COMPLEX SYSTEMS → UNEXPECTED CREATIONS")


def view() -> View:
    return View(cols=comp.COLS, rows=comp.ROWS)


@dataclass
class Frame:
    generation: int
    state: State                      # full world state (unbounded plane)
    ages: dict


def simulate(start: int = comp.START, count: int = comp.LOOP + 1) -> list[Frame]:
    """Run the composition from generation 0 and keep generations start … start+count-1."""
    state = comp.build_scene().cells
    ages = update_ages({}, state)
    frames = []
    for gen in range(start + count):
        if gen:
            state = next_generation(state)
            ages = update_ages(ages, state)
        if gen >= start:
            frames.append(Frame(gen, state, ages))
    return frames


def state_hash(cells) -> str:
    return hashlib.sha256(repr(sorted(cells)).encode()).hexdigest()[:16]


def render_frame(v: View, f: Frame, base: Image.Image) -> Image.Image:
    return render(v, f.state, f.ages, base, CAPTION, generation_text=f"{f.generation:04d}")


def delta_frames(images: list[Image.Image]) -> list[Image.Image]:
    """Frame 0 as is; later frames keep only pixels that changed (others transparent).

    With disposal 1 ("leave in place") a GIF viewer composites each frame over the
    previous one, so the picture is identical but long transparent runs compress
    far better than repeating the static scene.
    """
    out = [images[0]]
    prev = images[0].tobytes()
    for im in images[1:]:
        cur = im.tobytes()
        data = bytes(c if c != p else TRANSPARENT for c, p in zip(cur, prev))
        d = Image.frombytes("P", im.size, data)
        d.putpalette(im.getpalette())
        d.info["transparency"] = TRANSPARENT
        out.append(d)
        prev = cur
    return out


def write_gif(images: list[Image.Image], path: Path) -> None:
    frames = delta_frames(images)
    frames[0].save(
        path, save_all=True, append_images=frames[1:], duration=FRAME_MS, loop=0,
        disposal=1, transparency=TRANSPARENT, optimize=False,
    )


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ASSETS)
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    v = view()
    frames = simulate()
    shown, closing = frames[:-1], frames[-1]
    x0, y0 = v.x0, v.y0
    first_window = window(shown[0].state, x0, y0, v.cols, v.rows)
    last_window = window(closing.state, x0, y0, v.cols, v.rows)
    if first_window != last_window:
        raise SystemExit("loop is not exact: window(START + LOOP) != window(START)")

    base = base_image(v)
    images = [render_frame(v, f, base) for f in shown]
    gif = args.out / "life-banner.gif"
    write_gif(images, gif)
    preview = next(f for f in shown if f.generation == PREVIEW_GEN)
    render_frame(v, preview, base).convert("RGB").save(args.out / "life-banner-preview.png",
                                                        optimize=True)

    manifest = {
        "rule": "B3/S23",
        "view": {"x0": x0, "y0": y0, "cols": v.cols, "rows": v.rows, "pitch": v.pitch,
                 "cell": v.cell, "size": list(v.size)},
        "first_generation": shown[0].generation,
        "generations": len(shown),
        "frame_ms": FRAME_MS,
        "loop_closes_on_conway_step": True,
        "frames": [{"generation": f.generation,
                    "population_visible": len(window(f.state, x0, y0, v.cols, v.rows)),
                    "window_sha": state_hash(window(f.state, x0, y0, v.cols, v.rows))}
                   for f in shown],
    }
    (args.out / "life-banner.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"{gif}: {len(images)} frames, {v.size[0]}×{v.size[1]}, "
          f"{gif.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
