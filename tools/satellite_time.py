"""Choose SATELLITE_TIME: when, within each loop, the satellite enters the orbit lane.

    python -m tools.satellite_time

Print-job gliders cross the orbit lane on-screen and meteors cross its line just
past the right edge. Every glider and every satellite copy moves in a straight
line at a known speed, so for each candidate entry time we compute, generation
by generation, the Chebyshev distance between the satellite's centre and each
glider's centre while that glider is near the lane, and keep the time with the
largest worst-case gap. The chosen time is then confirmed by full simulation in
the tests (the satellite leaves the window intact every loop).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from life import composition as comp  # noqa: E402

HORIZON = comp.START + 2 * comp.LOOP


def moving_gliders():
    """(x0, y0, vx, vy) centre and velocity at generation 0 of every glider in the scene."""
    scene = comp.Scene()
    comp.build_print_job(scene)
    comp.build_meteor_shower(scene)
    out = []
    for p in scene.parts:
        xs = [x for x, _ in p.cells]
        ys = [y for _, y in p.cells]
        v = (0.25, 0.25) if p.region == "print job" else (-0.25, 0.25)
        out.append(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, *v))
    return np.array(out)


def worst_gap(time: int, gliders: np.ndarray) -> float:
    t = np.arange(HORIZON + 1)[:, None]                        # generations × 1
    gx = gliders[:, 0] + gliders[:, 2] * t
    gy = gliders[:, 1] + gliders[:, 3] * t
    entry = comp.satellite_entry()
    ex = (min(x for x, _ in entry) + max(x for x, _ in entry)) / 2
    ey = (min(y for _, y in entry) + max(y for _, y in entry)) / 2
    worst = np.inf
    for k in comp.SATELLITE_COPIES:
        sx = ex + 0.5 * (t - (comp.START + k * comp.LOOP + time))
        near_lane = np.abs(gy - ey) < 12
        d = np.maximum(np.abs(gx - sx), np.abs(gy - ey))
        d = np.where(near_lane, d, np.inf)
        worst = min(worst, float(d.min()))
    return worst


def main() -> None:
    gliders = moving_gliders()
    best = max(range(comp.LOOP), key=lambda t: (worst_gap(t, gliders), -t))
    print(f"SATELLITE_TIME = {best}   (closest approach {worst_gap(best, gliders):.1f} cells)")


if __name__ == "__main__":
    main()
