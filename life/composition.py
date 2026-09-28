"""The banner's initial world, built region by region.

Everything here is an ordinary B3/S23 pattern placed on an unbounded plane.
The scene only *starts* designed; from generation 0 on, ``life.engine`` alone
moves it forward. Regions are placed so that each machine keeps working:

    SYSTEMS  rack with a Gosper glider gun ──gliders──► eater "data port" on the printer
    PRINTER  enclosure, gantry, pentadecathlon nozzle, bed, seed block
             ◄── slow-salvo "print job": 5 gliders that build a honey farm and
                 take it apart again, back into the exact seed block
    FLIGHT   X-frame quadcopter with four blinker propellers
    SKY      Orion with M42 as a pulsar, a telescope aimed at it, Kok's galaxy turning,
             twinkling stars, a meteor shower of gliders, and a satellite (LWSS)
             crossing the empty orbit lane along the top

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
    BLINKER, BLOCK, EATER, GLIDER, GOSPER_GLIDER_GUN, KOKS_GALAXY, LWSS, MOLD, OCTAGON_2,
    PENTADECATHLON, POND, PULSAR, TUB, Pattern, glider_heading, union,
)

COLS, ROWS = 280, 104           # visible window, in cells
ORBIT_ROWS = 8                  # rows 0-7: an empty lane for the satellite
TOP, BASELINE = 9, 100          # the rack and sky start on TOP; rack, printer, tripod end on BASELINE
LOOP = 600                      # generations per GIF loop; multiple of 2, 3, 4, 5, 8, 15, 30
START = 600                     # first displayed generation (stream full, colours settled)
# The printer runs a job every PRINT_PERIOD generations: twice per loop. Copies of the
# salvo run from generation 0 on, so the seed block's age (and therefore its colour) is
# the same at START and at START + LOOP, and continue past START + 2·LOOP.
PRINT_PERIOD = LOOP // 2
PRINT_COPIES = range(-START // PRINT_PERIOD, 2 * LOOP // PRINT_PERIOD + 1)

# --- anchors ---------------------------------------------------------------------------

RACK = dict(x=1, y=TOP, nx=15, ny=31)         # block lattice: x 1…44, y 9…100
GUN_AT = (5, TOP + 4)
PRINTER = dict(x=92, y=33, nx=32, ny=23)      # block lattice: x 92…186, y 33…100
SEED_AT = (140, 76)                           # the build plate's origin block
DRONE_AT = (152, 19)                          # centre of the quadcopter, above the printer
SKY = (0, TOP)                                # offset applied to every sky coordinate below
GALAXY_AT = (250, 3)                          # Kok's galaxy, top-right sky (sky coordinates)
METEOR = glider_heading("sw")
SATELLITE = LWSS.flip_x()                     # lightweight spaceship heading right

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


def antidiag(c: Cell) -> int:
    """Lane coordinate of a south-west glider (a meteor): constant along its path."""
    return c[0] + c[1]


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


def sky(pattern: Pattern, x: int, y: int) -> State:
    """Place a pattern in sky coordinates (shifted by SKY so the sky clears the orbit)."""
    return pattern.at(x + SKY[0], y + SKY[1])


def build_space_region(scene: Scene) -> None:
    """Orion, the telescope aimed at M42, Kok's galaxy, and a few deliberate stars.

    Orion's Nebula (M42, under the belt) is the classic first astrophotography
    target; here it is a pulsar, the brightest period-3 oscillator. Betelgeuse, a
    pulsating variable star, is a mold (period 4).
    """
    # Orion, roughly as it stands in the evening sky (x right, y down).
    orion = [
        (MOLD, 199, 6, "Betelgeuse", 4), (BLOCK, 234, 12, "Bellatrix", 1),
        (TUB, 211, 31, "Alnitak", 1), (TUB, 218, 28, "Alnilam", 1), (TUB, 225, 25, "Mintaka", 1),
        (BLOCK, 206, 69, "Saiph", 1), (BLINKER, 228, 57, "Rigel", 2),
    ]
    for pat, x, y, star, per in orion:
        scene.add(star, "sky", pat.name, sky(pat, x, y), per, f"{star} (Orion)")
    scene.add("M42", "sky", "pulsar", sky(PULSAR, 210, 41), 3, "Orion Nebula (M42)")
    scene.add("galaxy", "sky", "Kok's galaxy", sky(KOKS_GALAXY, *GALAXY_AT), 8,
              "a spiral galaxy: winds and unwinds every 8 generations")

    # Telescope on a tripod, aimed up-left at M42; its feet stand on the baseline.
    # The tube lies on the diagonal through M42's centre, so it really points at it.
    tube = long_barge(11)                                 # NW–SE rod
    scene.add("telescope", "sky", "long barge", sky(tube, 236, 67), 1, "the telescope tube")
    scene.add("mount", "sky", "block", sky(BLOCK, 251, 81), 1, "the mount")
    leg = long_barge(5)
    scene.add("tripod", "sky", "long barge", union(
        sky(leg.flip_x(), 243, 85), sky(leg, 255, 85)), 1, "tripod legs")

    # A few stars, placed on purpose: a loose diagonal between the rack and the
    # printer (parallel to the glider stream) and a scatter around Orion.
    stars = [
        (TUB, 54, 4, 1), (OCTAGON_2, 64, 20, 5), (TUB, 58, 46, 1), (BLOCK, 66, 58, 1),
        (TUB, 74, 70, 1), (BLINKER, 105, 3, 2), (TUB, 178, 4, 1),
        (TUB, 273, 48, 1), (MOLD, 271, 34, 4), (TUB, 222, 84, 1), (TUB, 262, 64, 1),
        (BLINKER, 272, 74, 2), (BLOCK, 193, 88, 1),
    ]
    for pat, x, y, per in stars:
        kind = {1: "a star", 2: "a twinkling star", 4: "a pulsing star", 5: "a pulsing star"}
        scene.add(f"star at {x},{y}", "sky", pat.name, sky(pat, x, y), per, kind[per])


# Meteor shower: south-west gliders entering past the right edge. Each lane lists the
# generations within a loop at which a meteor crosses the entry point; copies one LOOP
# apart (LOOP/4 diagonals up-lane) keep the visible window exactly periodic.
METEOR_LANES = [
    # (entry point just outside the window, crossing times within each loop)
    ((282, 9 + TOP), (40, 110, 190, 250, 330, 430, 480, 540)),
]
METEOR_COPIES = range(-1, 3)


def meteor_lanes() -> tuple[int, int]:
    """x + y range of every meteor glider."""
    lanes = [antidiag(c) for (x, y), _ in METEOR_LANES for c in METEOR.at(x, y)]
    return min(lanes), max(lanes)


def build_meteor_shower(scene: Scene) -> None:
    for (x, y), times in METEOR_LANES:
        entry = METEOR.at(x, y)
        for k in METEOR_COPIES:
            for t in times:
                when = START + k * LOOP + t
                scene.add(f"meteor {k}.{t}", "meteors", "glider",
                          rewind_glider(entry, when, step=(-1, 1)), 0,
                          "a meteor: a glider falling through the sky")


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

    Copy k of the salvo is released k·PRINT_PERIOD generations later than copy 0; a
    glider moves one diagonal per 4 generations, so copies sit PRINT_PERIOD/4
    diagonals apart along their lanes.
    """
    for k in PRINT_COPIES:
        for i, (release, g) in enumerate(print_job_gliders()):
            when = START + k * PRINT_PERIOD + release
            scene.add(f"print job {k}.{i}", "print job", "glider", rewind_glider(g, when), 0,
                      f"turns the part into {PRINT_RECIPE[i][2]}")


def rewind_glider(cells: State, generations: int, step: Cell = (1, 1)) -> State:
    """The spaceship that becomes ``cells`` after ``generations`` steps.

    Gliders and lightweight spaceships repeat their shape every 4 generations,
    displaced by ``step`` ((1, 1) south-east glider, (-1, 1) south-west glider,
    (2, 0) right-moving LWSS). Going back 4q + r generations is: step back one
    period, run it forward 4 - r generations (if r > 0), then slide back q steps.
    """
    dx, dy = step
    q, r = divmod(generations, 4)
    earlier = (advance(frozenset((x - dx, y - dy) for x, y in cells), 4 - r) if r
               else frozenset(cells))
    out = frozenset((x - q * dx, y - q * dy) for x, y in earlier)
    assert advance(out, generations) == frozenset(cells)
    return out


# Satellite: a lightweight spaceship crossing the orbit lane left to right once per loop.
# It moves 2 cells every 4 generations (c/2), so a loop carries it 300 cells: copies sit
# 300 cells apart, far to the left. SATELLITE_TIME is when, within each loop, it enters
# the window; it was chosen by tools/satellite_time.py so that no print-job glider (which
# cross the orbit lane on-screen) and no meteor (which cross it just past the right edge)
# is ever within reach.
SATELLITE_ROW = 2
SATELLITE_TIME = 304
SATELLITE_COPIES = range(-1, 3)


def satellite_entry() -> State:
    """The LWSS just left of the window, where it is at SATELLITE_TIME."""
    return SATELLITE.at(-SATELLITE.width - 3, SATELLITE_ROW)


def build_satellite(scene: Scene, time: int | None = None) -> None:
    t = SATELLITE_TIME if time is None else time
    for k in SATELLITE_COPIES:
        when = START + k * LOOP + t
        scene.add(f"satellite {k}", "satellite", "lightweight spaceship",
                  rewind_glider(satellite_entry(), when, step=(2, 0)), 0,
                  "a satellite pass: an LWSS crossing the orbit lane")


def zone_function():
    """cell -> region name, used only to colour the picture (see life/renderer.py).

    Pure geometry, checked in this order: the meteor lane, the print-job lanes
    above the seed, the gun's stream between gun and eater, the orbit lane, then
    the rack, the drone and the printer; everything else is sky.
    """
    m_lo, m_hi = meteor_lanes()
    j_lo, j_hi = salvo_lanes()
    s_lo, s_hi = stream_lanes()
    stream_top, stream_bottom = stream_rows()
    sx, sy = SEED_AT
    dx, dy = DRONE_AT
    rack_right = RACK["x"] + 3 * RACK["nx"] + 1
    px0, py0 = PRINTER["x"], PRINTER["y"]
    px1 = px0 + 3 * PRINTER["nx"]

    def zone_of(c: Cell) -> str:
        x, y = c
        if m_lo - 3 <= x + y <= m_hi + 3:
            return "meteor"
        if j_lo - 3 <= x - y <= j_hi + 3 and y < sy - 10:
            return "job"
        if s_lo - 3 <= x - y <= s_hi + 3 and stream_top <= y < stream_bottom:
            return "stream"
        if y < ORBIT_ROWS:
            return "orbit"
        if x <= rack_right:
            return "systems"
        if abs(x - dx) <= 14 and y < py0 - 1:
            return "flight"
        if px0 - 4 <= x <= px1 + 2 and y >= py0 - 1:
            return "making"
        return "sky"

    return zone_of


def labels(pitch: int):
    """Caption-strip labels, each centred under (or aligned with) its region."""
    from .renderer import Label
    printer_mid = (PRINTER["x"] + 3 * PRINTER["nx"] // 2) * pitch
    sky_left = (PRINTER["x"] + 3 * PRINTER["nx"] + 6) * pitch
    return (
        Label((("SYSTEMS", "systems"),), x=10),
        Label((("MAKING", "making"), (" · ", None), ("FLIGHT", "flight")), x=printer_mid,
              align="centre"),
        Label((("SKY", "sky"),), x=sky_left),
    )


def build_scene() -> Scene:
    scene = Scene()
    build_systems_region(scene)
    build_printer_region(scene)
    build_drone(scene)
    build_space_region(scene)
    build_onecreations_signature(scene)
    build_print_job(scene)
    build_meteor_shower(scene)
    build_satellite(scene)
    return scene


def pattern_map(scene: Scene | None = None) -> str:
    """Markdown table of every placed pattern: python -m life.composition"""
    scene = scene or build_scene()
    rows = ["| region | part | pattern | period | where (x, y) | meaning |",
            "|---|---|---|---|---|---|"]
    for p in scene.parts:
        if p.region in ("print job", "meteors", "satellite"):
            continue
        x0 = min(x for x, _ in p.cells)
        y0 = min(y for _, y in p.cells)
        per = {0: "moves", 1: "still"}.get(p.period, f"p{p.period}")
        rows.append(f"| {p.region} | {p.name} | {p.pattern} | {per} | {x0}, {y0} | {p.meaning} |")
    jobs = [p for p in scene.parts if p.region == "print job"]
    rows.append(f"| print job | {len(jobs)} gliders ({len(jobs) // len(PRINT_RECIPE)} copies of "
                f"the {len(PRINT_RECIPE)}-glider salvo) | glider | moves | far up-left, off-screen "
                f"| slow-salvo construction |")
    meteors = [p for p in scene.parts if p.region == "meteors"]
    rows.append(f"| meteors | {len(meteors)} gliders on {len(METEOR_LANES)} lane(s) | glider | "
                f"moves | far up-right, off-screen | a meteor shower |")
    satellites = [p for p in scene.parts if p.region == "satellite"]
    rows.append(f"| satellite | {len(satellites)} copies | lightweight spaceship | moves | "
                f"orbit lane, far left | a satellite pass |")
    return "\n".join(rows)


if __name__ == "__main__":
    print(pattern_map())
