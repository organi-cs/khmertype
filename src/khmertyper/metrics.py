"""Speed and accuracy metrics.

Definitions (also documented in the README):

* **character** - one code point of the (normalised) target text. On a Khmer
  keyboard that is one keystroke, so CPM measures keystroke throughput.
* **cluster** - one visible Khmer letter block (see :mod:`khmertyper.khmer`).
* **WPM** - characters / 5 per minute, the same convention as English typing
  tests. For Khmer this is not an arbitrary choice: an average Khmer word is
  about two syllables, and a syllable is 2-3 code points, so "5 characters"
  is roughly one real Khmer word. Using the same definition in both languages
  is what makes the English comparison mode meaningful.
* **net** counts only correctly typed clusters (plus the spaces after fully
  correct words). **raw** counts every keystroke, right or wrong.
* **accuracy** - keystrokes that left their cluster correct or validly
  in-progress, divided by all keystrokes (backspace excluded). Mistakes stay
  counted even if you fix them.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Tuple

from .engine import Status, TypingTest

CHARS_PER_WORD = 5


@dataclass
class Series:
    wpm: List[float] = field(default_factory=list)  # cumulative net WPM
    raw: List[float] = field(default_factory=list)  # raw WPM within each second
    errors: List[int] = field(default_factory=list)  # wrong keystrokes per second


@dataclass
class Stats:
    duration: float
    wpm: float
    raw_wpm: float
    cpm: float
    raw_cpm: float
    clusters_pm: float
    words_pm: float
    accuracy: float
    keystrokes: int
    errors: int
    correct_chars: int
    cluster_counts: Dict[str, int]
    missed: List[Tuple[str, int]]
    series: Series

    def to_dict(self) -> dict:
        return asdict(self)


def per_minute(amount: float, seconds: float) -> float:
    return amount * 60.0 / seconds if seconds > 0 else 0.0


def speed_series(test: TypingTest, duration: float) -> Series:
    """Per-second samples for the results chart."""
    seconds = max(1, math.ceil(duration - 1e-9))
    series = Series()
    net = 0
    events = test.events
    j = 0
    for s in range(1, seconds + 1):
        keys = errors = 0
        while j < len(events) and events[j].t <= s:
            e = events[j]
            net = e.net_chars
            if e.kind != "backspace":
                keys += 1
                errors += 0 if e.correct else 1
            j += 1
        span = min(float(s), duration) if duration > 0 else float(s)
        window = span - (s - 1)
        series.wpm.append(round(per_minute(net / CHARS_PER_WORD, span), 1))
        series.raw.append(round(per_minute(keys / CHARS_PER_WORD, window), 1) if window > 0 else 0.0)
        series.errors.append(errors)
    return series


def compute(test: TypingTest, now: float, top_missed: int = 10) -> Stats:
    duration = test.elapsed(now)
    keys = [e for e in test.events if e.kind != "backspace"]
    keystrokes = len(keys)
    correct_keys = sum(1 for e in keys if e.correct)

    counts: Counter = Counter()
    correct_clusters = correct_words = 0
    for i in range(test.index + 1):
        view = test.view(i)
        for status in view.statuses:
            counts[status.value] += 1
        counts["extra"] += len(view.extras)
        correct_clusters += sum(1 for s in view.statuses if s is Status.CORRECT)
        if view.correct:
            correct_words += 1
    counts.pop(Status.UNTYPED.value, None)

    net = test.net_chars()
    return Stats(
        duration=round(duration, 2),
        wpm=round(per_minute(net / CHARS_PER_WORD, duration), 1),
        raw_wpm=round(per_minute(keystrokes / CHARS_PER_WORD, duration), 1),
        cpm=round(per_minute(net, duration), 1),
        raw_cpm=round(per_minute(keystrokes, duration), 1),
        clusters_pm=round(per_minute(correct_clusters, duration), 1),
        words_pm=round(per_minute(correct_words, duration), 1),
        accuracy=round(100.0 * correct_keys / keystrokes, 1) if keystrokes else 0.0,
        keystrokes=keystrokes,
        errors=keystrokes - correct_keys,
        correct_chars=net,
        cluster_counts={k: counts.get(k, 0) for k in ("correct", "wrong", "pending", "missed", "extra")},
        missed=[(c, n) for c, n in test.missed.most_common() if c.strip()][:top_missed],
        series=speed_series(test, duration),
    )
