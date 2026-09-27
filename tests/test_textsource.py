"""Checks on the bundled word lists and quotes, plus loading/segmenting."""

import random

import pytest

from khmertyper.khmer import is_khmer, is_valid_cluster, split_clusters
from khmertyper.segment import segment
from khmertyper.textsource import (load_quotes, load_words, make_text, parse_quotes, parse_words,
                                   random_words)


@pytest.mark.parametrize("lang", ["km", "en"])
def test_bundled_lists_load(lang):
    assert len(load_words(lang)) >= 150
    assert len(load_quotes(lang)) >= 8


def test_khmer_words_are_pre_segmented_and_well_formed():
    words = load_words("km")
    assert len(words) == len(set(words)), "duplicate words"
    for w in words:
        assert " " not in w and "​" not in w
        assert all(is_khmer(ch) for ch in w), w
        for cluster in split_clusters(w):
            assert is_valid_cluster(cluster), f"malformed cluster {cluster!r} in {w!r}"


def test_khmer_quotes_are_segmented_and_well_formed():
    for q in load_quotes("km"):
        assert q.source
        assert len(q.words) >= 3
        for w in q.words:
            for cluster in split_clusters(w):
                assert is_valid_cluster(cluster), f"malformed cluster {cluster!r} in {q.text!r}"


def test_parsers_skip_comments_and_clean_text():
    assert parse_words("# c\n\nក​\n  ខ \n") == ["ក", "ខ"]
    quotes = parse_quotes("# c\nក  ខ\tsrc\nគ\n")
    assert [(q.words, q.source) for q in quotes] == [(["ក", "ខ"], "src"), (["គ"], "")]


def test_user_override_file_wins(isolated_home):
    isolated_home.mkdir(parents=True)
    (isolated_home / "km_words.txt").write_text("ខ្ញុំ\nអ្នក\n", encoding="utf-8")
    assert load_words("km") == ["ខ្ញុំ", "អ្នក"]


def test_random_words_avoid_immediate_repeats():
    words = random_words(["a", "b"], 50, random.Random(1))
    assert all(x != y for x, y in zip(words, words[1:]))


def test_make_text_modes():
    rng = random.Random(0)
    assert len(make_text("km", "words", 25, rng).words) == 25
    quote = make_text("km", "quote", 0, rng)
    assert quote.source and quote.words


def test_segmenter_uses_dictionary_and_keeps_clusters_whole():
    words = ["ខ្ញុំ", "រៀន", "ភាសា", "ខ្មែរ", "ភាសាខ្មែរ"]
    assert segment("ខ្ញុំរៀនភាសាខ្មែរ", words) == ["ខ្ញុំ", "រៀន", "ភាសាខ្មែរ"]


def test_segmenter_handles_unknowns_punctuation_and_other_scripts():
    out = segment("ខ្ញុំរៀនស្ត្រី។ 2026 ok", ["ខ្ញុំ"])
    assert out == ["ខ្ញុំ", "រៀនស្ត្រី។", "2026", "ok"]
    assert segment("១២៣ក", ["ក"]) == ["១២៣", "ក"]
