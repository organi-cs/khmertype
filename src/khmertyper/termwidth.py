"""Measure how the terminal spaces Khmer, and make Rich/Textual agree.

Terminals disagree about how many columns Khmer marks take. Rich (and so
Textual) follows Unicode: spacing vowels such as ា and the COENG sign take no
column. macOS Terminal, for one, gives each of them a column of its own. When
the app and the terminal disagree, every row containing those characters ends
up a few columns longer on screen than Textual planned, which shifts the
cursor and spills the end of the row (e.g. the scrollbar) out of place.

Before the UI starts, :func:`measure` prints each Khmer mark after a base
letter and asks the terminal where the cursor ended up (the standard "cursor
position report", ESC [6n). :func:`apply` then patches Rich's width table so
that Textual lays text out the way this terminal draws it.

This only works for terminals whose widths are per character. Some terminals
(xterm.js-based ones) size a whole cluster as one column; that cannot be
expressed per character, so :func:`measure` checks whole clusters too and the
result is not applied if they don't add up.
"""

from __future__ import annotations

import atexit
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

BASE = "ក"  # ក
# Every Khmer combining mark: dependent vowels, signs, COENG, ATTHACAN.
MARKS = [chr(c) for c in range(0x17B4, 0x17D4)] + ["៝"]
# Whole clusters used to check that per-character widths add up.
CHECKS = ["ក្រ", "ស្ត្រី", "ញ៉ាំ"]


@dataclass
class Probe:
    """What the terminal reported, and what was done with it."""

    widths: Dict[str, int] = field(default_factory=dict)  # mark -> terminal columns
    defaults: Dict[str, int] = field(default_factory=dict)  # mark -> Rich's columns
    applied: bool = False
    reason: str = ""  # why nothing was applied
    grapheme_mode_off: bool = False  # we switched off DEC mode 2027

    def differences(self) -> Dict[str, Tuple[int, int]]:
        """Marks the terminal sizes differently: {mark: (rich, terminal)}."""
        return {ch: (self.defaults.get(ch, 0), w) for ch, w in self.widths.items()
                if w != self.defaults.get(ch, 0)}


_ORIGINAL_LOAD = None


def rich_widths() -> Dict[str, int]:
    """Rich's own (unpatched) widths for every Khmer mark."""
    import rich.cells as cells

    load = _ORIGINAL_LOAD or cells.load_cell_table
    table = load().widths
    out = {}
    for ch in MARKS:
        cp = ord(ch)
        out[ch] = next((w for a, b, w in table if a <= cp <= b), 1)
    return out


def _exchange(payload: str, replies: int, end: bytes, timeout: float) -> Optional[List[bytes]]:
    """Write ``payload`` with the terminal in raw mode and collect ``replies``
    escape-sequence replies, each ending in ``end``. None on timeout."""
    if os.name != "posix" or not (sys.stdin.isatty() and sys.stdout.isatty()):
        return None
    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    out: List[bytes] = []
    try:
        tty.setraw(fd)
        os.write(sys.stdout.fileno(), payload.encode("utf-8"))
        buf = b""
        deadline = time.monotonic() + timeout
        while len(out) < replies:
            left = deadline - time.monotonic()
            if left <= 0 or not select.select([fd], [], [], left)[0]:
                return None
            buf += os.read(fd, 1024)
            while end in buf and len(out) < replies:
                reply, buf = buf.split(end, 1)
                start = reply.rfind(b"\x1b[")
                if start >= 0:
                    out.append(reply[start + 2:])
    except (OSError, ValueError, termios.error):
        return None
    finally:
        # Drop any late replies so they can't turn up as keystrokes.
        try:
            termios.tcflush(fd, termios.TCIFLUSH)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return out


def measure(timeout: float = 1.0) -> Optional[Dict[str, int]]:
    """Ask the terminal how many columns each probe string advances.

    Returns ``{probe: columns}`` or None when the terminal can't be asked
    (not a TTY, Windows, or no reply within ``timeout`` seconds).
    """
    probes = [BASE] + [BASE + m for m in MARKS] + CHECKS
    # Start of line, clear it, draw the probe, ask for the cursor position.
    payload = "".join("\r\x1b[2K" + text + "\x1b[6n" for text in probes) + "\r\x1b[2K"
    replies = _exchange(payload, len(probes), b"R", timeout)
    if replies is None:
        return None
    try:
        cols = [int(r.split(b";")[1]) for r in replies]
    except (IndexError, ValueError):
        return None
    return {text: col - 1 for text, col in zip(probes, cols)}


def grapheme_mode(timeout: float = 0.3) -> Optional[bool]:
    """Is the terminal's grapheme-cluster mode (DEC mode 2027) on?

    Ghostty and some newer terminals size whole clusters when it is on.
    None if the terminal doesn't answer the mode query (DECRQM)."""
    replies = _exchange("\x1b[?2027$p", 1, b"$y", timeout)
    if not replies or not replies[0].startswith(b"?2027;"):
        return None
    state = replies[0].split(b";")[1][:1]
    return {b"1": True, b"3": True, b"2": False, b"4": False}.get(state)


def _write(seq: str) -> None:
    try:
        os.write(sys.stdout.fileno(), seq.encode())
    except OSError:
        pass


def interpret(columns: Dict[str, int]) -> Probe:
    """Turn raw probe columns into per-mark widths, and check they add up."""
    base = columns.get(BASE, 1)
    widths = {m: columns[BASE + m] - base for m in MARKS if BASE + m in columns}
    probe = Probe(widths, rich_widths())
    if any(w < 0 or w > 2 for w in widths.values()):
        probe.reason = "the terminal reported impossible widths"
        return probe
    for cluster in CHECKS:
        expected = sum(widths.get(ch, 1) for ch in cluster)
        if cluster in columns and columns[cluster] != expected:
            probe.reason = ("this terminal sizes whole clusters rather than single "
                            "characters, which can't be matched")
            return probe
    return probe


def apply(probe: Probe) -> Probe:
    """Patch Rich's width table with the measured Khmer widths."""
    import rich.cells as cells
    from rich.cells import CellTable

    global _ORIGINAL_LOAD
    if not probe.widths or probe.reason:
        return probe
    if not probe.differences():
        return probe  # the terminal already agrees with Rich
    if _ORIGINAL_LOAD is None:
        _ORIGINAL_LOAD = cells.load_cell_table

    original = _ORIGINAL_LOAD
    overrides = {ord(ch): w for ch, w in probe.widths.items()}
    patched: Dict[str, CellTable] = {}

    def load(unicode_version: str = "auto") -> CellTable:
        table = original(unicode_version)
        key = table.unicode_version
        if key not in patched:
            patched[key] = table._replace(widths=override_ranges(table.widths, overrides))
        return patched[key]

    cells.load_cell_table = load
    cells.get_character_cell_size.cache_clear()
    cells.cached_cell_len.cache_clear()
    probe.applied = True
    return probe


def restore() -> None:
    """Undo :func:`apply` (used by tests)."""
    import rich.cells as cells

    global _ORIGINAL_LOAD
    if _ORIGINAL_LOAD is not None:
        cells.load_cell_table = _ORIGINAL_LOAD
        cells.get_character_cell_size.cache_clear()
        cells.cached_cell_len.cache_clear()
        _ORIGINAL_LOAD = None


def override_ranges(
    table: Sequence[Tuple[int, int, int]], overrides: Dict[int, int]
) -> List[Tuple[int, int, int]]:
    """Return a copy of a sorted (start, end, width) table with single code
    points replaced. Code points missing from the table default to width 1,
    so every override gets its own entry."""
    out: List[Tuple[int, int, int]] = []
    for start, end, width in table:
        cut = sorted(cp for cp in overrides if start <= cp <= end)
        for cp in cut:
            if start < cp:
                out.append((start, cp - 1, width))
            start = cp + 1
        if start <= end:
            out.append((start, end, width))
    out.extend((cp, cp, w) for cp, w in overrides.items())
    out.sort()
    return out


def calibrate(timeout: float = 1.0) -> Probe:
    """Measure and apply in one go; never raises.

    If the terminal sizes whole clusters (e.g. Ghostty, whose grapheme mode
    caps any multi-character cluster at 2 columns) and it lets us switch that
    mode off, switch it off for this session and measure again. Call
    :func:`restore_terminal` on exit to switch it back on.
    """
    try:
        columns = measure(timeout)
        if columns is None:
            return Probe(reason="the terminal did not answer the width query")
        probe = interpret(columns)
        if "whole clusters" in probe.reason and grapheme_mode():
            _write("\x1b[?2027l")
            if grapheme_mode() is False:
                columns = measure(timeout)
                retry = interpret(columns) if columns else probe
                if not retry.reason:
                    retry.grapheme_mode_off = True
                    atexit.register(restore_terminal)
                    return apply(retry)
            _write("\x1b[?2027h")  # didn't help: leave the terminal as it was
        return apply(probe)
    except Exception:  # pragma: no cover - a probe must never stop the app
        return Probe(reason="the width query failed")


_restored = False


def restore_terminal() -> None:
    """Switch grapheme mode back on if calibration switched it off."""
    global _restored
    if not _restored:
        _restored = True
        _write("\x1b[?2027h")
