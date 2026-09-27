"""A small dictionary-based Khmer word segmenter for preparing quote files.

Khmer is written without spaces between words, so text has to be split into
words before it can be used as a typing test. This helper finds the split
with the fewest words from a dictionary (the bundled word list by default),
working on whole clusters so it can never cut through one. Unknown clusters
become single-cluster words, so always proof-read the output. For serious
work use a statistical segmenter such as khmer-nltk.

    khmertyper segment raw.txt > my_quotes.txt
"""

from __future__ import annotations

import unicodedata
from typing import Iterable, List, Set

from .khmer import clean, is_khmer_base, split_clusters

UNKNOWN_COST = 3  # prefer one known word over a run of unknown clusters


def segment(text: str, dictionary: Iterable[str], max_clusters: int = 12) -> List[str]:
    """Split one run of text into words. Existing spaces are kept as breaks."""
    words: Set[str] = {clean(w) for w in dictionary}
    out: List[str] = []
    for chunk in clean(text).split():
        out.extend(_segment_chunk(chunk, words, max_clusters))
    return out


def _segment_chunk(chunk: str, words: Set[str], max_clusters: int) -> List[str]:
    clusters = split_clusters(chunk)
    n = len(clusters)
    inf = float("inf")
    best = [inf] * (n + 1)
    back = [0] * (n + 1)
    best[0] = 0
    for i in range(n):
        if best[i] == inf:
            continue
        # A run of anything that is not a Khmer letter (digits, Latin,
        # punctuation) stays together.
        if not is_khmer_base(clusters[i][0]):
            j = i + 1
            while j < n and not is_khmer_base(clusters[j][0]):
                j += 1
            _relax(best, back, i, j, best[i] + 1)
            continue
        for j in range(i + 1, min(n, i + max_clusters) + 1):
            token = "".join(clusters[i:j])
            if token in words:
                _relax(best, back, i, j, best[i] + 1)
        _relax(best, back, i, i + 1, best[i] + UNKNOWN_COST)
    tokens: List[str] = []
    j = n
    while j > 0:
        i = back[j]
        tokens.append("".join(clusters[i:j]))
        j = i
    tokens.reverse()
    merged: List[str] = []
    prev_unknown = False
    for token in tokens:
        unknown = token not in words and is_khmer_base(token[0])
        if merged and all(_is_punct(c) for c in token):
            # Sentence punctuation belongs to the word before it ("កម្ពុជា។").
            merged[-1] += token
        elif merged and unknown and prev_unknown:
            # Consecutive unknown clusters are most likely one unknown word.
            merged[-1] += token
        else:
            merged.append(token)
        prev_unknown = unknown
    return merged


def _is_punct(ch: str) -> bool:
    return "\u17d4" <= ch <= "\u17da" or unicodedata.category(ch).startswith("P")


def _relax(best: list, back: list, i: int, j: int, cost: float) -> None:
    if cost < best[j]:
        best[j] = cost
        back[j] = i
