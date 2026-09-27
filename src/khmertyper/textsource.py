"""Loading bundled (or user-supplied) word lists and quotes."""

from __future__ import annotations

import random
from dataclasses import dataclass
from importlib import resources
from typing import List, NamedTuple, Optional

from .khmer import clean
from .storage import data_dir

LANGS = {"km": "Khmer", "en": "English"}


@dataclass(frozen=True)
class Quote:
    text: str
    source: str

    @property
    def words(self) -> List[str]:
        return self.text.split()


def _read(name: str) -> str:
    """User override in the data dir wins over the bundled file."""
    override = data_dir() / name
    if override.is_file():
        return override.read_text(encoding="utf-8")
    return resources.files("khmertyper").joinpath("data", name).read_text(encoding="utf-8")


def _lines(text: str) -> List[str]:
    out = []
    for line in text.splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            out.append(line.rstrip("\r\n"))
    return out


def parse_words(text: str) -> List[str]:
    words = []
    for line in _lines(text):
        word = clean(line).strip()
        if word:
            words.append(word)
    return words


def parse_quotes(text: str) -> List[Quote]:
    quotes = []
    for line in _lines(text):
        body, _, source = line.partition("\t")
        body = " ".join(clean(body).split())
        if body:
            quotes.append(Quote(body, source.strip()))
    return quotes


def load_words(lang: str) -> List[str]:
    return parse_words(_read(f"{lang}_words.txt"))


def load_quotes(lang: str) -> List[Quote]:
    return parse_quotes(_read(f"{lang}_quotes.txt"))


class PracticeText(NamedTuple):
    words: List[str]
    source: Optional[str]


def random_words(pool: List[str], count: int, rng: random.Random) -> List[str]:
    """Random words without immediate repeats."""
    out: List[str] = []
    for _ in range(count):
        choice = rng.choice(pool)
        if out and len(pool) > 1:
            while choice == out[-1]:
                choice = rng.choice(pool)
        out.append(choice)
    return out


def make_text(lang: str, mode: str, count: int, rng: Optional[random.Random] = None) -> PracticeText:
    """Build the words for one test. ``count`` is the word count for word
    mode and an initial batch size for timed mode."""
    rng = rng or random.Random()
    if mode == "quote":
        quote = rng.choice(load_quotes(lang))
        return PracticeText(quote.words, quote.source)
    return PracticeText(random_words(load_words(lang), count, rng), None)


def initial_batch(mode: str, words: int) -> int:
    return words if mode == "words" else 100

