"""A tiny pure-ASCII speed chart for the results screen.

    120 |         .
        |  .  .  ***  .
     60 |***.***   ****
        |
      0 +--------------
           x     x
        1s          30s

``*`` is cumulative net WPM, ``.`` is raw WPM for that second (hidden where
it overlaps the net line) and ``x`` marks seconds that contained an error.
"""

from __future__ import annotations

import math
from typing import List, Sequence

NET, RAW, ERR = "*", ".", "x"


def _nice_max(value: float) -> int:
    if value <= 10:
        return 10
    step = 10 ** int(math.log10(value))
    for mult in (1, 2, 2.5, 5, 10):
        top = step * mult
        if top >= value:
            return int(math.ceil(top))
    return int(math.ceil(value))


def _bucket(values: Sequence[float], width: int, how: str = "mean") -> List[float]:
    """Shrink a series to at most ``width`` points."""
    n = len(values)
    if n <= width:
        return list(values)
    out = []
    for c in range(width):
        lo, hi = c * n // width, (c + 1) * n // width
        chunk = values[lo:max(hi, lo + 1)]
        out.append(sum(chunk) if how == "sum" else sum(chunk) / len(chunk))
    return out


def render_chart(
    wpm: Sequence[float],
    raw: Sequence[float],
    errors: Sequence[int],
    width: int = 60,
    height: int = 8,
) -> List[str]:
    """Return the chart as a list of equal-length lines."""
    if not wpm:
        return ["(no data)"]
    height = max(3, height)
    wpm_b = _bucket(wpm, width)
    raw_b = _bucket(raw, width)
    err_b = _bucket([float(e) for e in errors], width, how="sum")
    n = len(wpm_b)
    col = max(1, width // n)  # stretch short tests so they are readable
    plot_w = n * col
    top = _nice_max(max(max(wpm_b), max(raw_b) if raw_b else 0))

    grid = [[" "] * plot_w for _ in range(height)]

    def row_of(v: float) -> int:
        r = int(round(v / top * (height - 1)))
        return height - 1 - max(0, min(height - 1, r))

    for i in range(n):
        for dx in range(col):
            x = i * col + dx
            if i < len(raw_b):
                grid[row_of(raw_b[i])][x] = RAW
            grid[row_of(wpm_b[i])][x] = NET

    label_w = len(str(top))
    labels = {0: str(top), height - 1: "0"}
    if (height - 1) % 2 == 0:  # only label the middle row when it is exactly half
        labels[(height - 1) // 2] = str(round(top / 2))
    lines = []
    for r in range(height):
        label = labels.get(r, "").rjust(label_w)
        lines.append(f"{label} |" + "".join(grid[r]))
    lines.append(" " * label_w + " +" + "-" * plot_w)
    marks = "".join((ERR if i < len(err_b) and err_b[i] > 0 else " ") + " " * (col - 1) for i in range(n))
    lines.append(" " * (label_w + 2) + marks)
    start, end = "1s", f"{len(wpm)}s"
    axis = start + end.rjust(max(0, plot_w - len(start)))
    lines.append(" " * (label_w + 2) + axis)
    full = max(len(line) for line in lines)
    return [line.ljust(full) for line in lines]
