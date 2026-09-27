"""Khmer text handling: cluster segmentation, canonical ordering and matching.

Terminology used throughout the project:

* **code point** - one Unicode scalar value. For Khmer this is (almost always)
  one keystroke on a NiDA-style keyboard, so it is also the unit behind CPM.
* **cluster** - what a reader sees as one "letter block": a base consonant (or
  independent vowel) plus any subscripts (COENG + consonant), register
  shifters, dependent vowels and signs. For example ``ស្ត្រី`` is one cluster
  typed with six keystrokes: ស ្ ត ្ រ ី.

Clusters come from the Unicode extended grapheme cluster regex ``\\X``. Recent
Unicode versions keep COENG stacks together; older ones split ``ក្រ`` into
``ក្`` + ``រ``, so :func:`split_clusters` re-joins any cluster that ends in
COENG with the one that follows. The result is the same on every version of
the ``regex`` module.

Normalisation
-------------
Khmer marks all have canonical combining class 0 (except COENG), so Unicode
NFC does *not* fix typing-order differences. People legitimately type the
same cluster in different orders (e.g. ``ក្រា`` vs ``កា្រ``, ``ស្ត្រ`` vs
``ស្រ្ត``, or ``េ`` + ``ី`` instead of ``ើ``). :func:`normalize_cluster`
rewrites a cluster into one internal canonical order, modelled on the
Unicode Khmer syllable structure and SIL's ``khnormal``:

    base, robat, subscripts (COENG RO last), register shifter, vowels, signs

It also composes ``េ + ី → ើ`` and ``េ + ា → ោ`` and (optionally) treats
COENG DA and COENG TA as the same subscript because they render
identically in almost every font. The canonical form is only used for
comparison; the text shown on screen is always the original.
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from typing import Iterable, List, NamedTuple

import regex

COENG = "្"
RO = "រ"
DA = "ដ"
TA = "ត"
ROBAT = "៌"
SHIFTERS = frozenset("៉៊")  # MUUSIKATOAN, TRIISAP
E_VOWEL = "េ"  # េ

# Characters removed before comparison. ZWSP is how Khmer marks word
# boundaries invisibly (and what the NiDA spacebar types); the inherent
# vowels U+17B4/U+17B5 are invisible and deprecated.
IGNORABLE = frozenset("​‌‍⁠﻿឴឵")

# Keys that end a word in the test. Khmer keyboards differ: Windows NiDA puts
# ZWSP on the spacebar and a real space on Shift+Space.
WORD_SEPARATORS = frozenset(" ​ 　")

# Two-part vowels that have a precomposed code point.
COMPOSITES = {
    "ើ": E_VOWEL + "ី",  # ើ = េ + ី
    "ោ": E_VOWEL + "ា",  # ោ = េ + ា
}
_COMPOSE = {tuple(sorted(v)): k for k, v in COMPOSITES.items()}

DOTTED_CIRCLE = "◌"

_CLUSTER_RE = regex.compile(r"\X")


def is_consonant(ch: str) -> bool:
    return "ក" <= ch <= "អ"


def is_independent_vowel(ch: str) -> bool:
    return "ឣ" <= ch <= "ឳ"


def is_khmer_base(ch: str) -> bool:
    """A character that can start a Khmer cluster."""
    return is_consonant(ch) or is_independent_vowel(ch) or ch == "ៜ"


def is_dependent_vowel(ch: str) -> bool:
    return "ា" <= ch <= "ៅ"


def is_khmer(ch: str) -> bool:
    return "ក" <= ch <= "៿" or "᧠" <= ch <= "᧿"


def is_mark(ch: str) -> bool:
    return unicodedata.category(ch) in ("Mn", "Mc", "Me")


def clean(text: str) -> str:
    """NFC-normalise and drop invisible characters that should never count."""
    text = unicodedata.normalize("NFC", text)
    return "".join(ch for ch in text if ch not in IGNORABLE)


def split_clusters(text: str) -> List[str]:
    """Split text into user-perceived clusters (see module docstring)."""
    out: List[str] = []
    for cluster in _CLUSTER_RE.findall(text):
        if out and out[-1].endswith(COENG) and not cluster[0].isspace():
            out[-1] += cluster
        else:
            out.append(cluster)
    return out


class Units(NamedTuple):
    """A cluster broken into the pieces that can be typed in any order."""

    base: str
    units: Counter
    trailing_coeng: bool


def _canonical_subscript(ch: str, merge_da_ta: bool) -> str:
    if merge_da_ta and ch == DA:
        return COENG + TA
    return COENG + ch


def cluster_units(cluster: str, merge_da_ta: bool = True) -> Units:
    """Break a cluster into its base plus a multiset of order-free units.

    Subscripts are kept as two-character ``COENG + consonant`` units because
    their internal order does matter. Composite vowels are decomposed so that
    typing ``េ`` is recognised as the first half of ``ើ``.
    """
    s = clean(cluster)
    if not s:
        return Units("", Counter(), False)
    base, rest = s[0], s[1:]
    units: Counter = Counter()
    trailing = False
    i = 0
    while i < len(rest):
        ch = rest[i]
        if ch == COENG:
            if i + 1 < len(rest) and not is_mark(rest[i + 1]):
                units[_canonical_subscript(rest[i + 1], merge_da_ta)] += 1
                i += 2
                continue
            if i == len(rest) - 1:
                trailing = True
            else:
                units[COENG] += 1
        elif ch in COMPOSITES:
            for part in COMPOSITES[ch]:
                units[part] += 1
        else:
            units[ch] += 1
        i += 1
    return Units(base, units, trailing)


def _order_key(unit: str) -> int:
    first = unit[0]
    if first == ROBAT:
        return 1
    if first == COENG:
        return 3 if unit[1:] == RO else 2
    if first in SHIFTERS:
        return 4
    if is_dependent_vowel(first):
        return 5
    if is_khmer(first):
        return 6
    return 7


def normalize_cluster(cluster: str, merge_da_ta: bool = True) -> str:
    """Return the canonical form of one cluster (for comparison only)."""
    s = clean(cluster)
    if not s or not is_khmer_base(s[0]):
        return s
    base, units, trailing = cluster_units(s, merge_da_ta)

    # Compose two-part vowels regardless of the order they were typed in.
    for parts, composed in _COMPOSE.items():
        while all(units[p] > 0 for p in parts):
            for p in parts:
                units[p] -= 1
            units[composed] += 1
    units += Counter()  # drop zero counts

    # Subscripts keep their typed order (except COENG RO, which goes last);
    # everything else is ordered by category, then code point.
    ordered: List[str] = []
    for unit in _stable_units(s, units, merge_da_ta):
        ordered.append(unit)
    ordered.sort(key=lambda u: (_order_key(u), 0 if u[0] == COENG else ord(u[0])))
    return base + "".join(ordered) + (COENG if trailing else "")


def _stable_units(s: str, units: Counter, merge_da_ta: bool) -> Iterable[str]:
    """Expand a unit multiset, preserving first-seen order for subscripts."""
    remaining = Counter(units)
    seen: List[str] = []
    rest = s[1:]
    for i, ch in enumerate(rest):
        if ch == COENG and i + 1 < len(rest) and not is_mark(rest[i + 1]):
            unit = _canonical_subscript(rest[i + 1], merge_da_ta)
            if remaining[unit] > 0:
                seen.append(unit)
                remaining[unit] -= 1
    return seen + sorted(remaining.elements())


def normalize_text(text: str, merge_da_ta: bool = True) -> str:
    return "".join(normalize_cluster(c, merge_da_ta) for c in split_clusters(clean(text)))


def clusters_match(typed: str, target: str, merge_da_ta: bool = True) -> bool:
    return normalize_cluster(typed, merge_da_ta) == normalize_cluster(target, merge_da_ta)


def is_partial(typed: str, target: str, merge_da_ta: bool = True) -> bool:
    """True if ``typed`` can still become ``target`` by typing more keys.

    This is what lets a half-typed cluster show as "in progress" instead of
    wrong: every unit typed so far must belong to the target, in any order.
    """
    t = cluster_units(typed, merge_da_ta)
    g = cluster_units(target, merge_da_ta)
    if not t.base or t.base != g.base:
        return False
    if t.units - g.units:
        return False
    if t.trailing_coeng:
        missing = g.units - t.units
        return any(u.startswith(COENG) for u in missing)
    return True


def is_valid_cluster(cluster: str) -> bool:
    """Structural sanity check used to validate bundled word lists."""
    s = clean(cluster)
    if not s:
        return False
    if not is_khmer(s[0]):
        return True
    if is_mark(s[0]) or s.endswith(COENG):
        return False
    for i, ch in enumerate(s[1:], start=1):
        if not is_mark(ch) and s[i - 1] != COENG:
            return False
    return True


def keystroke_hint(cluster: str) -> List[str]:
    """The keys that make up a cluster, marks shown on a dotted circle.

    Composite vowels are left whole because most layouts have one key for
    them. Follows the target's own order, i.e. the conventional typing order.
    """
    out: List[str] = []
    for ch in clean(cluster):
        out.append(DOTTED_CIRCLE + ch if is_mark(ch) else ch)
    return out
