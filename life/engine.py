"""Conway's Game of Life (B3/S23) on an unbounded plane.

A state is a ``frozenset`` of live ``(x, y)`` cells; everything absent is dead.
There is no grid edge, no wrapping and no clipping: gliders that leave the
banner keep flying in the simulation, they just stop being drawn.

The engine has no dependencies so it can be ported as-is (for example to the
JavaScript on onecreations.in) and it is the only place where Life is stepped.
Rendering, cell ages and colours are derived from states and never feed back.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Iterator

Cell = tuple[int, int]
State = frozenset[Cell]

NEIGHBOUR_OFFSETS: tuple[Cell, ...] = tuple(
    (dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dx, dy) != (0, 0)
)


def next_generation(live: Iterable[Cell]) -> State:
    """Return the next B3/S23 generation of ``live``.

    Only cells with at least one live neighbour can be alive next generation,
    so counting neighbours of live cells covers every candidate.
    """
    live = live if isinstance(live, (set, frozenset)) else set(live)
    counts: Counter[Cell] = Counter(
        (x + dx, y + dy) for x, y in live for dx, dy in NEIGHBOUR_OFFSETS
    )
    return frozenset(
        cell
        for cell, n in counts.items()
        # birth on exactly 3; survival on 2 or 3
        if n == 3 or (n == 2 and cell in live)
    )


def run(live: Iterable[Cell], generations: int) -> Iterator[State]:
    """Yield generation 0 through ``generations`` (inclusive)."""
    state: State = frozenset(live)
    yield state
    for _ in range(generations):
        state = next_generation(state)
        yield state


def advance(live: Iterable[Cell], generations: int) -> State:
    """Return the state ``generations`` steps after ``live``."""
    state: State = frozenset(live)
    for _ in range(generations):
        state = next_generation(state)
    return state


def update_ages(ages: dict[Cell, int], state: State) -> dict[Cell, int]:
    """Visual metadata only: consecutive generations each live cell has been alive.

    ``ages`` belongs to the previous generation. A cell born this generation has
    age 1. Dead cells are dropped. Nothing here influences ``next_generation``.
    """
    return {cell: ages.get(cell, 0) + 1 for cell in state}


def bounding_box(live: Iterable[Cell]) -> tuple[int, int, int, int] | None:
    """(min_x, min_y, max_x, max_y) of the live cells, or None when empty."""
    cells = list(live)
    if not cells:
        return None
    xs = [x for x, _ in cells]
    ys = [y for _, y in cells]
    return min(xs), min(ys), max(xs), max(ys)


def window(live: Iterable[Cell], x0: int, y0: int, width: int, height: int) -> State:
    """Live cells inside the rectangle ``[x0, x0+width) × [y0, y0+height)``."""
    return frozenset(
        (x, y) for x, y in live if x0 <= x < x0 + width and y0 <= y < y0 + height
    )


def period(live: Iterable[Cell], max_period: int) -> int | None:
    """Smallest p ≤ max_period with advance(live, p) == live (no translation)."""
    start = frozenset(live)
    state = start
    for p in range(1, max_period + 1):
        state = next_generation(state)
        if state == start:
            return p
    return None
