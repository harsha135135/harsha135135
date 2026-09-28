"""Offline search for the banner's "print job": a slow salvo of gliders that turns
a seed block into a printed part, and later turns the part back into the block.

Slow-salvo construction is how large Life machines (self-constructing
replicators, universal constructors) build things: gliders all travel in the
same direction, one at a time, and every reaction settles before the next
glider arrives. Timing between gliders is therefore free, which is what lets
the salvo fit into the banner loop.

The search is a breadth-first walk over clean collisions starting from a block:

    state --(one south-east glider: lane, glider phase, target phase)--> state

A state is a still life or a period-2 constellation (blinkers are useful
intermediates). A reaction is kept only if it settles, emits nothing, stays
inside the build box and stays small. ``--goal-return`` additionally searches
back from every state to the original block, which is what makes the banner
loop exact: build the part, show it, then un-build it.

Afterwards it looks for cycles through the seed: states P reachable from the
block such that more gliders turn P back into the *same* block at the *same*
place. That is what makes the banner loop exact: build the part, show it, then
un-build it.

Run:  python -m tools.salvo_search --depth 5          (≈3 minutes)

The cheapest cycle it reports — 1 glider to a honey farm, 4 gliders back —
is the recipe in ``life/composition.py``, where it is re-verified with
``life.engine`` (never with this bit-parallel stepper).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from life.engine import advance  # noqa: E402
from life.patterns import BLOCK, GLIDER  # noqa: E402
from tools.fastlife import Board  # noqa: E402

W = H = 64
SEED = BLOCK.at(32, 36)          # origin block of the build plate
BOX = (14, 14, 50, 44)           # build volume: min_x, min_y, max_x, max_y inclusive
MAX_GENS = 320
MAX_POP = 90                     # during a reaction
MAX_STATE_POP = 48               # settled states
MAX_STATE_SPAN = 22

GLIDER_PHASES = [advance(GLIDER.cells, p) for p in range(4)]


def normal(cells):
    return tuple(sorted(cells))


def canonical(board, b):
    """(canonical cells, period) for a settled p1/p2 board, phase chosen deterministically."""
    nb = board.step(b)
    if nb == b:
        return normal(board.decode(b)), 1
    return min(normal(board.decode(b)), normal(board.decode(nb))), 2


def acceptable(cells):
    if not cells or len(cells) > MAX_STATE_POP:
        return False
    xs = [x for x, _ in cells]
    ys = [y for _, y in cells]
    if max(xs) - min(xs) > MAX_STATE_SPAN or max(ys) - min(ys) > MAX_STATE_SPAN:
        return False
    x0, y0, x1, y1 = BOX
    return x0 <= min(xs) and max(xs) <= x1 and y0 <= min(ys) and max(ys) <= y1


def place_glider(target, phase, lane):
    """Glider on a lane (x - y of its bbox corner), far enough up-left not to touch yet."""
    g = GLIDER_PHASES[phase]
    gx = min(x for x, _ in g)
    gy = min(y for _, y in g)
    g = [(x - gx, y - gy) for x, y in g]
    tmin = min(x + y for x, y in target)
    gmax = max(u + v for u, v in g)
    t = (tmin - 6 - lane - gmax) // 2
    cells = [(lane + t + u, t + v) for u, v in g]
    if min(x for x, _ in cells) < 2 or min(y for _, y in cells) < 2:
        return None
    return cells


def react(board: Board, cells):
    """Settle a reaction. Returns (canonical cells, period) or None if unclean."""
    b = board.encode(cells)
    hist = [b]
    for _ in range(MAX_GENS):
        b = board.step(b)
        if b & board.edge or b.bit_count() > MAX_POP:
            return None
        if b == hist[-1] or (len(hist) > 1 and b == hist[-2]):
            return canonical(board, b)
        hist.append(b)
        if len(hist) > 2:
            hist.pop(0)
    return None


def expansions(board, state, period):
    d = [x - y for x, y in state]
    target_phases = [state] if period == 1 else [state, normal(advance(state, 1))]
    for tphase, target in enumerate(target_phases):
        for lane in range(min(d) - 6, max(d) + 5):
            for gphase in range(4):
                g = place_glider(target, gphase, lane)
                if g is None:
                    continue
                r = react(board, list(target) + g)
                if r and acceptable(r[0]):
                    yield r, (lane, gphase, tphase)


def search(depth: int):
    board = Board(W, H)
    start = normal(SEED)
    info = {start: (0, 1)}                 # state -> (level, period)
    edges = []
    q = deque([start])
    t0, n = time.time(), 0
    while q:
        s = q.popleft()
        lvl, per = info[s]
        if lvl >= depth:
            continue
        for (r, rper), move in expansions(board, s, per):
            n += 1
            edges.append((s, r, move))
            if r not in info:
                info[r] = (lvl + 1, rper)
                q.append(r)
        if len(info) % 500 < 3: print(f"  {len(info)} states, {len(edges)} edges, {time.time()-t0:.0f}s",
              flush=True)
    print()
    return info, edges


def cycles(info, edges, limit):
    """Cheapest seed → part → seed cycles, as lists of (move, resulting state)."""
    start = normal(SEED)
    back = {}                                 # state -> (next state towards seed, move)
    adj, radj = {}, {}
    for a, b, move in edges:
        adj.setdefault(a, []).append((b, move))
        radj.setdefault(b, []).append((a, move))
    dist_out = {s: info[s][0] for s in info}
    dist_back = {start: 0}
    q = deque([start])
    while q:                                  # reverse BFS: gliders needed to get back
        u = q.popleft()
        for a, move in radj.get(u, []):
            if a not in dist_back:
                dist_back[a] = dist_back[u] + 1
                back[a] = (u, move)
                q.append(a)
    found = sorted((dist_out[s] + dist_back[s], -len(s), s) for s in dist_back
                   if s != start and len(s) >= 10)
    out = []
    for total, _, part in found[:limit]:
        path, u = [], part                    # forward path via BFS parents
        prev = _bfs_parents(adj, start)
        while u != start:
            p, move = prev[u]
            path.append((move, u))
            u = p
        path.reverse()
        u = part
        while u != start:
            nxt, move = back[u]
            path.append((move, nxt))
            u = nxt
        out.append((total, part, path))
    return out


def _bfs_parents(adj, start):
    prev = {start: None}
    q = deque([start])
    while q:
        u = q.popleft()
        for v, move in adj.get(u, []):
            if v not in prev:
                prev[v] = (u, move)
                q.append(v)
    return prev


def picture(cells):
    xs = [x for x, _ in cells]
    ys = [y for _, y in cells]
    return "\n".join("    " + "".join("#" if (x, y) in set(cells) else "." for x in
                                        range(min(xs), max(xs) + 1))
                      for y in range(min(ys), max(ys) + 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--depth", type=int, default=5)
    ap.add_argument("--cycles", type=int, default=3, help="how many cycles to print")
    ap.add_argument("--out", help="optionally dump the reaction graph as JSON")
    args = ap.parse_args()
    info, edges = search(args.depth)
    if args.out:
        ids = {s: i for i, s in enumerate(info)}
        json.dump({
            "seed": normal(SEED), "box": BOX,
            "states": [{"id": ids[s], "level": info[s][0], "period": info[s][1], "cells": s}
                       for s in info],
            "edges": [[ids[a], ids[b], *move] for a, b, move in edges],
        }, open(args.out, "w"))
        print("wrote", args.out)
    sx, sy = min(SEED)
    for total, part, path in cycles(info, edges, args.cycles):
        print(f"\n{total}-glider cycle through a {len(part)}-cell part:\n{picture(part)}")
        for (lane, gphase, tphase), state in path:
            print(f"  glider lane {lane - (sx - sy):+d} (relative to the seed), phase {gphase}"
                  f", target phase {tphase} -> {len(state)} cells")


if __name__ == "__main__":
    main()
