"""The typing-test state machine. Pure Python, no UI, driven with timestamps.

The test is word-aligned like Monkeytype: whatever is typed before a space is
compared with the target word cluster by cluster, so one mistake never shifts
the rest of the text out of alignment. Pressing space moves to the next word;
clusters left untyped become "missed".
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .khmer import WORD_SEPARATORS, clean, is_partial, normalize_cluster, split_clusters


class Status(str, Enum):
    UNTYPED = "untyped"
    CORRECT = "correct"
    WRONG = "wrong"
    PENDING = "pending"  # a valid, unfinished cluster (the one being typed)
    MISSED = "missed"  # skipped by pressing space early


@dataclass(frozen=True)
class WordView:
    """How one target word compares with what was typed for it."""

    target: Tuple[str, ...]
    statuses: Tuple[Status, ...]
    typed: Tuple[str, ...]
    extras: Tuple[str, ...]

    @property
    def correct(self) -> bool:
        return not self.extras and all(s is Status.CORRECT for s in self.statuses)

    @property
    def cursor(self) -> int:
        """Index of the target cluster the cursor sits on (may equal len)."""
        if self.typed and len(self.typed) <= len(self.target):
            last = len(self.typed) - 1
            if self.statuses[last] is not Status.CORRECT:
                return last
        return min(len(self.typed), len(self.target))


def compare_word(
    target: Sequence[str],
    target_norm: Sequence[str],
    typed_text: str,
    *,
    committed: bool,
    merge_da_ta: bool = True,
) -> WordView:
    typed = split_clusters(clean(typed_text))
    statuses: List[Status] = []
    for i, goal in enumerate(target):
        if i >= len(typed):
            statuses.append(Status.MISSED if committed else Status.UNTYPED)
        elif normalize_cluster(typed[i], merge_da_ta) == target_norm[i]:
            statuses.append(Status.CORRECT)
        elif not committed and i == len(typed) - 1 and is_partial(typed[i], goal, merge_da_ta):
            statuses.append(Status.PENDING)
        else:
            statuses.append(Status.WRONG)
    return WordView(tuple(target), tuple(statuses), tuple(typed), tuple(typed[len(target):]))


@dataclass
class KeyEvent:
    t: float  # seconds since the test started
    kind: str  # "char" | "space" | "backspace"
    correct: bool
    net_chars: int  # correct characters on screen after this key


@dataclass
class TypingTest:
    words: List[str]
    time_limit: Optional[float] = None
    merge_da_ta: bool = True

    typed: List[str] = field(default_factory=lambda: [""])
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    events: List[KeyEvent] = field(default_factory=list)
    missed: Counter = field(default_factory=Counter)
    last_committed: bool = False  # the final word was ended with space

    def __post_init__(self) -> None:
        self.words = [clean(w) for w in self.words if clean(w).strip()]
        if not self.words:
            raise ValueError("a typing test needs at least one word")
        self.target: List[List[str]] = [split_clusters(w) for w in self.words]
        self.target_norm: List[List[str]] = [
            [normalize_cluster(c, self.merge_da_ta) for c in cl] for cl in self.target
        ]
        self._wrong: Set[int] = set()
        self._extras = 0
        self._committed: Dict[int, Tuple[int, bool]] = {}
        self._views: Dict[Tuple[int, str, bool], WordView] = {}

    # ------------------------------------------------------------------ state

    @property
    def index(self) -> int:
        return len(self.typed) - 1

    @property
    def started(self) -> bool:
        return self.started_at is not None

    @property
    def finished(self) -> bool:
        return self.ended_at is not None

    def elapsed(self, now: float) -> float:
        if self.started_at is None:
            return 0.0
        end = self.ended_at if self.ended_at is not None else now
        if self.time_limit is not None and end >= self.started_at + self.time_limit:
            # Exactly the limit: (start + limit) - start can come out a hair
            # short in floating point, and then a timed test never ends.
            return float(self.time_limit)
        return max(0.0, end - self.started_at)

    def view(self, i: int) -> WordView:
        committed = i < self.index or (i == self.index and self.last_committed)
        typed = self.typed[i] if i <= self.index else ""
        key = (i, typed, committed)
        view = self._views.get(key)
        if view is None:
            if len(self._views) > 4096:
                self._views.clear()
            view = self._views[key] = compare_word(
                self.target[i], self.target_norm[i], typed,
                committed=committed, merge_da_ta=self.merge_da_ta,
            )
        return view

    def current(self) -> WordView:
        return self.view(self.index)

    def extend(self, words: Sequence[str]) -> None:
        """Append more words (timed mode never runs out of text)."""
        for w in words:
            w = clean(w)
            if w.strip():
                self.words.append(w)
                cl = split_clusters(w)
                self.target.append(cl)
                self.target_norm.append([normalize_cluster(c, self.merge_da_ta) for c in cl])

    # ----------------------------------------------------------------- input

    def type(self, ch: str, now: float) -> None:
        """Feed one typed character (a single code point)."""
        if self.time_limit is not None and self.started_at is not None:
            if now >= self.started_at + self.time_limit:
                self.finish(self.started_at + self.time_limit)
        if self.finished:
            return
        if ch in WORD_SEPARATORS:
            self._space(now)
            return
        if clean(ch) == "":
            return  # ZWJ/ZWNJ etc. never count
        self._start(now)
        self.typed[-1] += ch
        view = self.current()
        new_wrong = self._track_errors(view)
        new_extra = len(view.extras) > self._extras
        self._extras = len(view.extras)
        last = len(view.typed) - 1
        landed_ok = 0 <= last < len(view.target) and view.statuses[last] in (
            Status.CORRECT, Status.PENDING,
        )
        self._record(now, "char", landed_ok and not new_wrong and not new_extra)
        if self.index == len(self.words) - 1 and view.correct and self.time_limit is None:
            self.ended_at = now

    def _space(self, now: float) -> None:
        if not self.typed[-1]:
            return  # like Monkeytype: space on an empty word does nothing
        self._start(now)
        i = self.index
        self.last_committed = True
        view = self.view(i)
        self._track_errors(view)
        for goal, status in zip(view.target, view.statuses):
            if status is Status.MISSED:
                self.missed[goal] += 1
        self._committed[i] = (self._word_net(i, view), view.correct)
        self._record(now, "space", view.correct)
        if i == len(self.words) - 1:
            self.ended_at = now
            return
        self.last_committed = False
        self.typed.append("")
        self._wrong, self._extras = set(), 0

    def backspace(self, now: float) -> None:
        """Delete one code point; at a word start, re-open the previous word
        (only if it has a mistake, as in Monkeytype)."""
        if self.finished or not self.started:
            return
        if self.typed[-1]:
            self.typed[-1] = self.typed[-1][:-1]
        elif not self._reopen_previous():
            return
        self._resync()
        self._record(now, "backspace", True)

    def delete_word(self, now: float) -> None:
        if self.finished or not self.started:
            return
        if not self.typed[-1] and not self._reopen_previous():
            return
        self.typed[-1] = ""
        self._resync()
        self._record(now, "backspace", True)

    def finish(self, now: float) -> None:
        if self.ended_at is None:
            self.ended_at = now

    # ------------------------------------------------------------- internals

    def _start(self, now: float) -> None:
        if self.started_at is None:
            self.started_at = now

    def _reopen_previous(self) -> bool:
        if self.index == 0 or self._committed[self.index - 1][1]:
            return False
        self.typed.pop()
        self._committed.pop(self.index, None)
        return True

    def _resync(self) -> None:
        view = self.current()
        self._wrong = {i for i, s in enumerate(view.statuses) if s is Status.WRONG}
        self._extras = len(view.extras)

    def _track_errors(self, view: WordView) -> bool:
        """Count clusters that just turned wrong as misses of that cluster."""
        now_wrong = {i for i, s in enumerate(view.statuses) if s is Status.WRONG}
        fresh = now_wrong - self._wrong
        for i in fresh:
            self.missed[view.target[i]] += 1
        self._wrong = now_wrong
        return bool(fresh)

    def _word_net(self, i: int, view: WordView) -> int:
        return sum(
            len(norm)
            for norm, status in zip(self.target_norm[i], view.statuses)
            if status is Status.CORRECT
        )

    def net_chars(self) -> int:
        """Characters of correctly typed clusters, plus one for each space
        between words that followed a fully correct word."""
        total = 0
        for i, (net, correct) in self._committed.items():
            total += net + (1 if correct and i < len(self.words) - 1 else 0)
        if self.index not in self._committed:
            total += self._word_net(self.index, self.current())
        return total

    def _record(self, now: float, kind: str, correct: bool) -> None:
        assert self.started_at is not None
        self.events.append(KeyEvent(now - self.started_at, kind, correct, self.net_chars()))
