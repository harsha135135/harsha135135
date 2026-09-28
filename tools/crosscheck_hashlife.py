"""Cross-check the banner against an unrelated Life engine: the HashLife engine in
Rust from life-lab (github.com/harsha135135/life-lab).

    python -m tools.crosscheck_hashlife --life-lab ../path/to/life-lab

Writes the banner's generation-0 world as RLE (with Golly's ``#CXRLE Pos=``
so coordinates survive), lets ``life-lab run`` advance it with HashLife, and
compares the result with ``life.engine`` cell for cell.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from life import composition as comp  # noqa: E402
from life.engine import advance  # noqa: E402


def to_rle(cells) -> str:
    xs = [x for x, _ in cells]
    ys = [y for _, y in cells]
    x0, y0 = min(xs), min(ys)
    live = set(cells)
    rows = []
    for y in range(y0, max(ys) + 1):
        runs: list[list] = []
        for x in range(x0, max(xs) + 1):
            ch = "o" if (x, y) in live else "b"
            if runs and runs[-1][0] == ch:
                runs[-1][1] += 1
            else:
                runs.append([ch, 1])
        if runs and runs[-1][0] == "b":
            runs.pop()
        rows.append("".join((str(n) if n > 1 else "") + ch for ch, n in runs))
    body = "$".join(rows) + "!"
    lines, line = [], ""
    for token in re.findall(r"\d*[bo$!]", body):   # never split a run count from its tag
        if len(line) + len(token) > 70:
            lines.append(line)
            line = ""
        line += token
    lines.append(line)
    header = (f"#CXRLE Pos={x0},{y0}\n"
              f"x = {max(xs) - x0 + 1}, y = {max(ys) - y0 + 1}, rule = B3/S23\n")
    return header + "\n".join(lines) + "\n"


def from_rle(text: str) -> frozenset:
    x0 = y0 = 0
    m = re.search(r"Pos=(-?\d+),(-?\d+)", text)
    if m:
        x0, y0 = int(m.group(1)), int(m.group(2))
    body = "".join(line.strip() for line in text.splitlines()
                   if line.strip() and not line.startswith(("#", "x")))
    cells, x, y, run = set(), 0, 0, ""
    for ch in body:
        if ch.isdigit():
            run += ch
            continue
        n = int(run) if run else 1
        run = ""
        if ch == "b":
            x += n
        elif ch == "o":
            cells.update((x0 + x + i, y0 + y) for i in range(n))
            x += n
        elif ch == "$":
            y, x = y + n, 0
        elif ch == "!":
            break
    return frozenset(cells)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--life-lab", type=Path, required=True, help="life-lab checkout")
    ap.add_argument("--gens", type=int, default=comp.START + comp.LOOP)
    args = ap.parse_args()
    world = comp.build_scene().cells
    assert from_rle(to_rle(world)) == world, "RLE round trip"
    with tempfile.TemporaryDirectory() as tmp:
        src, out = Path(tmp) / "banner.rle", Path(tmp) / "out.rle"
        src.write_text(to_rle(world))
        subprocess.run(["cargo", "run", "--release", "-q", "-p", "life-cli", "--", "run",
                        str(src), "--gens", str(args.gens), "--out", str(out)],
                       cwd=args.life_lab, check=True)
        theirs = from_rle(out.read_text())
    ours = advance(world, args.gens)
    same = theirs == ours
    print(f"generation {args.gens}: life.engine {len(ours)} cells, HashLife {len(theirs)} cells"
          f" — {'identical' if same else 'DIFFERENT'}")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
