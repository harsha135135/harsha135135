"""The banner's initial world, built region by region.

Everything here is an ordinary B3/S23 pattern placed on an unbounded plane.
The scene only *starts* designed; from generation 0 on, ``life.engine`` alone
moves it forward. Regions are placed so that each machine keeps working:

    SYSTEMS  rack with a Gosper glider gun ──gliders──► eater "data port" on the printer
    PRINTER  enclosure, gantry, pentadecathlon nozzle, bed, seed block
             ◄── slow-salvo "print job": 5 gliders that build a honey farm and
                 take it apart again, back into the exact seed block
    FLIGHT   X-frame quadcopter with four blinker propellers
    SKY      Orion with M42 as a pulsar, a telescope aimed at it, twinkling stars

Coordinates are world cells: x to the right, y downwards. The banner shows
the rectangle ``[0, COLS) × [0, ROWS)``.

Loop design (see docs/BANNER.md): every machine has a period dividing LOOP
(the gun is period 30), and the print job is an exact cycle. Its gliders are
placed one LOOP apart along their lanes, so the visible window at generation
START + LOOP equals the window at START, cell for cell. The GIF loops on a
genuine Conway step instead of cutting back to the beginning.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .engine import Cell, State, advance, next_generation
from .patterns import (
    BLINKER, BLOCK, EATER, GLIDER, GOSPER_GLIDER_GUN, PENTADECATHLON, POND, PULSAR, TUB,
    Pattern, union,
)

COLS, ROWS = 280, 96            # visible window, in cells
LOOP = 300                      # generations per GIF loop; multiple of 2, 3, 15 and 30
START = 600                     # first displayed generation (stream full, colours settled)
# Salvo copies: one print per loop. Copy -1 runs just before START so the seed block's
# age (and therefore its colour) is the same at START and at START + LOOP.
PRINT_COPIES = range(-1, 3)

# --- anchors ---------------------------------------------------------------------------

RACK = dict(x=1, y=1, nx=15, ny=31)           # block lattice: x 1…44, y 1…92
GUN_AT = (5, 5)
PRINTER = dict(x=92, y=24, nx=32, ny=23)      # block lattice: x 92…186, y 24…91
SEED_AT = (140, 67)                           # the build plate's origin block
DRONE_AT = (152, 10)                          # centre of the quadcopter

# --- parts and the scene ---------------------------------------------------------------


@dataclass
class Part:
    """A named piece of the scene; the list doubles as the pattern map."""
    name: str
    region: str
    pattern: str                 # canonical pattern name
    cells: State
    period: int                  # 1 still life, 2/3/15/30 oscillator or gun, 0 moving
    meaning: str = ""


@dataclass
class Scene:
    parts: list[Part] = field(default_factory=list)

    def add(self, name, region, pattern, cells, period, meaning=""):
        self.parts.append(Part(name, region, pattern, frozenset(cells), period, meaning))

    @property
    def cells(self) -> State:
        return union(*(p.cells for p in self.parts))

    def region(self, region: str) -> State:
        return union(*(p.cells for p in self.parts if p.region == region))


# --- geometry helpers -----------------------------------------------------------------


def long_barge(length: int) -> Pattern:
    """Diagonal still-life rod (tub → barge → long barge → …), two cells wide."""
    cells = {(k + 1, k) for k in range(length + 1)} | {(k, k + 1) for k in range(length + 1)}
    return Pattern("long barge", frozenset(cells))


def block_lattice(x0, y0, points) -> State:
    """Blocks on a 3-cell lattice: dotted rails, walls and marks.

    Straight runs are stable (a one-cell gap between two blocks sees 2 or 4
    neighbours) and so are diagonal steps (2). Three blocks in an L are not —
    the inside corner sees exactly 3 — so frames leave their corners open.
    """
    return union(*(BLOCK.at(x0 + 3 * i, y0 + 3 * j) for i, j in points))


def frame_points(nx, ny):
    """Lattice points of a rectangular frame. Corners are left open: three blocks
    meeting in an L would give a dead cell exactly three neighbours."""
    edge = [(i, j) for i in range(nx) for j in range(ny)
            if i in (0, nx - 1) or j in (0, ny - 1)]
    return [(i, j) for i, j in edge if (i in (0, nx - 1)) != (j in (0, ny - 1))]


def diag(c: Cell) -> int:
    """Lane coordinate of a south-east glider: constant along its path."""
    return c[0] - c[1]


def keep_clear(cells: State, lanes: tuple[int, int], rows: tuple[int, int]) -> State:
    """Drop cells that a glider travelling on ``lanes`` would touch between the
    rows where it appears and where it is absorbed or reacts.

    A still life is safe from a passing glider if every one of its cells is at
    Chebyshev distance ≥ 3 from the glider, i.e. |x - y - lane| ≥ 5.
    """
    lo, hi = lanes
    top, bottom = rows
    return frozenset(c for c in cells
                     if not (lo - 4 <= diag(c) <= hi + 4 and top - 3 <= c[1] < bottom))


def blocks_clear(blocks: State, lanes, rows: tuple[int, int]) -> State:
    """Like keep_clear but removes whole blocks (never leaves half a block)."""
    kept = keep_clear(blocks, lanes, rows)
    return frozenset(c for c in kept
                     if all(n in kept for n in _block_of(c, blocks)))


def _block_of(c, cells):
    x, y = c
    for bx in (x - 1, x):
        for by in (y - 1, y):
            quad = {(bx, by), (bx + 1, by), (bx, by + 1), (bx + 1, by + 1)}
            if quad <= cells:
                return quad
    return {c}


# --- the two glider flows --------------------------------------------------------------


def stream_lanes() -> tuple[int, int]:
    """x - y range of the gun's gliders: 12…15 relative to the gun (checked in tests)."""
    gx, gy = GUN_AT
    return gx - gy + 12, gx - gy + 15


def stream_rows() -> tuple[int, int]:
    """Rows the stream crosses: from the gun's output (row 9 of the gun) to the eater."""
    return GUN_AT[1] + 9, eater_position()[1]


def salvo_rows() -> tuple[int, int]:
    """The print job comes in from far above the banner and ends at the seed."""
    return -10**6, SEED_AT[1]


# Slow-salvo recipe found by tools/salvo_search.py. Each step is one south-east glider:
# its bounding box's top-left corner runs along lane x - y = (seed's x - y) + LANE, and it
# is released in glider phase PHASE when the target is in the phase the search used
# (for a blinker, the lexicographically smaller of its two phases).
PRINT_RECIPE = [
    # (lane, glider phase, what the target becomes)
    (+4, 1, "a honey farm: four beehives"),
    (+1, 1, "two beehives"),
    (+3, 1, "a blinker"),
    (-1, 1, "a blinker, one cell over"),
    (-3, 1, "the original seed block"),
]
# Generation within each loop at which each glider passes its launch point, 6 diagonals
# short of its target. Chosen so that every reaction has settled before the next glider
# arrives and no glider in flight clips the honey farm; tests replay the whole salvo.
PRINT_SCHEDULE = [0, 170, 210, 238, 263]


def salvo_lanes() -> tuple[int, int]:
    """x - y range of every print-job glider."""
    lanes = [diag(c) for _, g in print_job_gliders() for c in g]
    return min(lanes), max(lanes)


# --- SYSTEMS ---------------------------------------------------------------------------


def build_systems_region(scene: Scene) -> None:
    gx, gy = GUN_AT
    scene.add("glider gun", "systems", "Gosper glider gun", GOSPER_GLIDER_GUN.at(gx, gy), 30,
              "the running system: emits one glider every 30 generations")

    # Rack cabinet around the gun, with a floor under the gun bay. The stream leaves
    # through a port in the right wall, so blocks in its path are left out.
    x0, y0, nx, ny = RACK["x"], RACK["y"], RACK["nx"], RACK["ny"]
    pts = frame_points(nx, ny) + [(i, 6) for i in range(2, nx - 2)]
    rack = blocks_clear(block_lattice(x0, y0, pts), stream_lanes(), stream_rows())
    scene.add("rack", "systems", "block", rack, 1, "the cabinet: infrastructure")

    # Server units: a status LED (blinker) and a front panel rail each.
    for k, uy in enumerate(range(y0 + 26, y0 + 88, 9)):
        led = BLINKER.at(x0 + 5, uy + 1)
        panel = block_lattice(x0 + 11, uy, [(i, 0) for i in range(8)])
        panel = blocks_clear(panel, stream_lanes(), stream_rows())
        scene.add(f"server {k + 1} LED", "systems", "blinker", led, 2, "status LED")
        scene.add(f"server {k + 1}", "systems", "block", panel, 1, "server unit")


# --- PRINTER ---------------------------------------------------------------------------


def build_printer_region(scene: Scene) -> None:
    x0, y0, nx, ny = PRINTER["x"], PRINTER["y"], PRINTER["nx"], PRINTER["ny"]
    sx, sy = SEED_AT
    lanes = salvo_lanes()

    # Enclosure. Its top-left corner stays open: print jobs come in through it.
    enclosure = blocks_clear(block_lattice(x0, y0, frame_points(nx, ny)), lanes, salvo_rows())
    ex, ey = eater_position()
    enclosure = frozenset(c for c in enclosure
                          if not (ex - 3 <= c[0] <= ex + 6 and ey - 3 <= c[1] <= ey + 6))
    enclosure = frozenset(c for c in enclosure if len(_block_of(c, enclosure)) == 4)
    scene.add("enclosure", "printer", "block", enclosure, 1, "the enclosure frame")
    scene.add("data port", "printer", "eater 1", EATER.at(ex, ey), 1,
              "Eater 1 swallows every glider from the rack and repairs itself")

    # Gantry and hot end, directly above the seed. The pentadecathlon's sparks
    # reach 3 cells beyond its 3×10 body, so it hangs 6 rows below the gantry
    # and ends 4 rows above the tallest point of the honey-farm reaction.
    gantry = blocks_clear(block_lattice(x0, y0 + 9, [(i, 0) for i in range(2, nx - 2)]),
                          lanes, salvo_rows())
    scene.add("gantry", "printer", "block", gantry, 1, "the X gantry")
    scene.add("hot end", "printer", "pentadecathlon", PENTADECATHLON.at(sx - 1, y0 + 16), 15,
              "the toolhead: a period-15 oscillator")

    # Build plate and its Z supports.
    bed_y = sy + 9
    bed = block_lattice(sx - 25, bed_y, [(i, 0) for i in range(18)])
    scene.add("bed", "printer", "block", bed, 1, "the build plate")
    scene.add("z supports", "printer", "block", union(
        block_lattice(sx - 10, bed_y + 4, [(0, 0), (0, 1)]),
        block_lattice(sx + 20, bed_y + 4, [(0, 0), (0, 1)])), 1, "Z axis")
    scene.add("seed", "printer", "block", BLOCK.at(sx, sy), 1,
              "the origin block the print job builds from — and returns to")


def eater_position() -> tuple[int, int]:
    """Eater 1 on the gun's lane, set into the printer's left wall.

    The offset (53 + k, 39 + k) from the gun comes from a search over positions
    near the lane: keep those where gun + eater is exactly period 30 and nothing
    escapes. Any k works; this one puts the eater in the wall.
    """
    gx, gy = GUN_AT
    k = PRINTER["x"] - 2 - gx - 53
    return gx + 53 + k, gy + 39 + k


# --- FLIGHT ----------------------------------------------------------------------------


def build_drone(scene: Scene) -> None:
    cx, cy = DRONE_AT
    scene.add("drone body", "flight", "pond", POND.at(cx - 1, cy - 1), 1, "flight controller")
    arm = long_barge(3)
    se, ne = arm, arm.flip_x()
    scene.add("drone arms", "flight", "long barge", union(
        se.at(cx - 7, cy - 7), ne.at(cx + 4, cy - 7),
        ne.at(cx - 7, cy + 4), se.at(cx + 4, cy + 4)), 1, "carbon-fibre arms")
    props = union(BLINKER.at(cx - 11, cy - 9), BLINKER.at(cx + 10, cy - 9),
                  BLINKER.at(cx - 11, cy + 10), BLINKER.at(cx + 10, cy + 10))
    scene.add("propellers", "flight", "blinker", props, 2,
              "propellers: a blinker turns a quarter turn every generation")


# --- SKY -------------------------------------------------------------------------------


def build_space_region(scene: Scene) -> None:
    """Orion, the telescope aimed at M42, and a few stars elsewhere in the sky.

    Orion's Nebula (M42, under the belt) is the classic first astrophotography
    target; here it is a pulsar, the brightest period-3 oscillator.
    """
    # Orion, roughly as it stands in the evening sky (x right, y down).
    orion = [
        (BLINKER, 202, 9, "Betelgeuse"), (BLOCK, 234, 12, "Bellatrix"),
        (TUB, 211, 31, "Alnitak"), (TUB, 218, 28, "Alnilam"), (TUB, 225, 25, "Mintaka"),
        (BLOCK, 206, 69, "Saiph"), (BLINKER, 230, 61, "Rigel"),
    ]
    for pat, x, y, star in orion:
        scene.add(star, "sky", pat.name, pat.at(x, y), 2 if pat is BLINKER else 1,
                  f"{star} (Orion)")
    scene.add("M42", "sky", "pulsar", PULSAR.at(210, 41), 3, "Orion Nebula (M42)")

    # Telescope on a tripod, aimed up-left at M42.
    # The tube lies on the diagonal through M42's centre, so it really points at it.
    tube = long_barge(11)                                 # NW–SE rod
    scene.add("telescope", "sky", "long barge", tube.at(236, 67), 1, "the telescope tube")
    scene.add("mount", "sky", "block", BLOCK.at(251, 81), 1, "the mount")
    leg = long_barge(7)
    scene.add("tripod", "sky", "long barge", union(
        leg.flip_x().at(241, 85), leg.at(255, 85)), 1, "tripod legs")

    stars = [
        (TUB, 59, 12), (BLOCK, 100, 12), (BLINKER, 70, 26), (TUB, 52, 56),
        (BLOCK, 60, 62), (TUB, 116, 6), (BLINKER, 181, 3), (TUB, 268, 10),
        (BLINKER, 262, 30), (TUB, 273, 48), (BLOCK, 193, 88), (TUB, 222, 84), (TUB, 262, 64),
    ]
    for pat, x, y in stars:
        per = 2 if pat is BLINKER else 1
        scene.add(f"star at {x},{y}", "sky", pat.name, pat.at(x, y), per,
                  "a twinkling star" if per == 2 else "a star")


# --- OneCreations -----------------------------------------------------------------------

# The mark is drawn in the same dotted-block language as the machine it sits on.
O_MARK = [(1, 0), (2, 0), (0, 1), (3, 1), (1, 2), (2, 2)]     # six blocks in a ring
C_MARK = [(1, 0), (2, 0), (0, 1), (1, 2), (2, 2)]             # the same ring, opened


def build_onecreations_signature(scene: Scene) -> None:
    """OneCreations' maker's mark on the printer base: an O and a C built from blocks.

    Diagonal neighbours on the 3-cell lattice give a dead cell only two live
    neighbours, so both rings are still lifes.
    """
    x = PRINTER["x"] + 5
    y = SEED_AT[1] + 13
    scene.add("mark O", "printer", "block", block_lattice(x, y, O_MARK), 1, "O")
    scene.add("mark C", "printer", "block", block_lattice(x + 13, y, C_MARK), 1, "C")


# --- the print job ------------------------------------------------------------------------


def launch_cells(lane: int, phase: int, target: State) -> State:
    """Glider cells the salvo search used: lane/phase, 6 diagonals short of ``target``."""
    g = advance(GLIDER.cells, phase)
    gx, gy = min(x for x, _ in g), min(y for _, y in g)
    g = [(x - gx, y - gy) for x, y in g]
    tmin = min(x + y for x, y in target)
    t = (tmin - 6 - lane - max(u + v for u, v in g)) // 2
    return frozenset((lane + t + u, t + v) for u, v in g)


def print_job_gliders() -> list[tuple[int, State]]:
    """(release generation, glider cells at that generation) for one loop's salvo.

    Replays the recipe on the isolated seed with ``life.engine`` to know each
    target's exact cells (and phase) at its release generation.
    """
    seed_lane = diag(SEED_AT)
    state: State = BLOCK.at(*SEED_AT)
    t = 0
    out = []
    for (lane, phase, _), release in zip(PRINT_RECIPE, PRINT_SCHEDULE):
        state = advance(state, release - t)
        t = release
        if next_generation(state) != state:
            # period-2 target: the search used its lexicographically smaller phase
            if tuple(sorted(state)) > tuple(sorted(next_generation(state))):
                raise ValueError(f"release at gen {release} meets the other blinker phase")
        g = launch_cells(seed_lane + lane, phase, state)
        out.append((release, g))
        state = frozenset(state | g)
    return out


def build_print_job(scene: Scene) -> None:
    """Place every salvo glider far up its lane, so it reaches its launch point on time.

    Copy k of the salvo is released k·LOOP generations later than copy 0; since a
    glider moves one diagonal per 4 generations, copies sit LOOP/4 diagonals apart.
    """
    for k in PRINT_COPIES:
        for i, (release, g) in enumerate(print_job_gliders()):
            when = START + k * LOOP + release
            scene.add(f"print job {k}.{i}", "print job", "glider", rewind_glider(g, when), 0,
                      f"turns the part into {PRINT_RECIPE[i][2]}")


def rewind_glider(cells: State, generations: int) -> State:
    """The south-east glider that becomes ``cells`` after ``generations`` steps.

    A glider repeats its shape every 4 generations, one cell further (+1, +1), so
    going back 4q + r generations is: step back one period, run it forward 4 - r
    generations (if r > 0), then slide it back q diagonals.
    """
    q, r = divmod(generations, 4)
    earlier = advance(frozenset((x - 1, y - 1) for x, y in cells), 4 - r) if r else frozenset(cells)
    out = frozenset((x - q, y - q) for x, y in earlier)
    assert advance(out, generations) == frozenset(cells)
    return out


def build_scene() -> Scene:
    scene = Scene()
    build_systems_region(scene)
    build_printer_region(scene)
    build_drone(scene)
    build_space_region(scene)
    build_onecreations_signature(scene)
    build_print_job(scene)
    return scene


def pattern_map(scene: Scene | None = None) -> str:
    """Markdown table of every placed pattern: python -m life.composition"""
    scene = scene or build_scene()
    rows = ["| region | part | pattern | period | where (x, y) | meaning |",
            "|---|---|---|---|---|---|"]
    for p in scene.parts:
        if p.region == "print job":
            continue
        x0 = min(x for x, _ in p.cells)
        y0 = min(y for _, y in p.cells)
        per = {0: "moves", 1: "still"}.get(p.period, f"p{p.period}")
        rows.append(f"| {p.region} | {p.name} | {p.pattern} | {per} | {x0}, {y0} | {p.meaning} |")
    jobs = [p for p in scene.parts if p.region == "print job"]
    rows.append(f"| print job | {len(jobs)} gliders ({len(jobs) // len(PRINT_RECIPE)} copies of "
                f"the {len(PRINT_RECIPE)}-glider salvo) | glider | moves | far up-left, off-screen "
                f"| slow-salvo construction |")
    return "\n".join(rows)


if __name__ == "__main__":
    print(pattern_map())
