import pytest

from khmertyper.khmer import (clean, clusters_match, is_partial, is_valid_cluster, keystroke_hint,
                              normalize_cluster, normalize_text, split_clusters)


# ------------------------------------------------------------------ clusters

@pytest.mark.parametrize("text, expected", [
    ("ស្ត្រី", ["ស្ត្រី"]),
    ("ក្រុង", ["ក្រុ", "ង"]),
    ("ញ៉ាំ", ["ញ៉ាំ"]),
    ("ធម៌", ["ធ", "ម៌"]),
    ("សៀវភៅ", ["សៀ", "វ", "ភៅ"]),
    ("កម្ពុជា។", ["ក", "ម្ពុ", "ជា", "។"]),
    ("hi ក", ["h", "i", " ", "ក"]),
])
def test_split_clusters(text, expected):
    assert split_clusters(text) == expected


def test_split_rejoins_coeng_even_with_old_unicode_data(monkeypatch):
    """Older \\X implementations split after COENG; we must re-join."""
    import khmertyper.khmer as kh

    class OldRegex:
        @staticmethod
        def findall(text):
            return ["ក្", "រុ", "ង"]

    monkeypatch.setattr(kh, "_CLUSTER_RE", OldRegex)
    assert kh.split_clusters("ក្រុង") == ["ក្រុ", "ង"]


def test_trailing_coeng_does_not_swallow_a_space():
    assert split_clusters("ក្ ខ") == ["ក្", " ", "ខ"]


def test_clean_strips_invisible_characters():
    assert clean("ខ្មែរ​ភាសា‍") == "ខ្មែរភាសា"
    assert clean("ក឴") == "ក"


# ------------------------------------------------------------- normalisation

@pytest.mark.parametrize("a, b", [
    ("ក្រា", "កា្រ"),          # vowel typed before the subscript
    ("ស្ត្រី", "ស្រ្តី"),        # COENG RO typed first
    ("ស្ត្រី", "ស្រី្ត"),        # vowel in the middle
    ("កើ", "កេី"),            # composite vowel from its two parts
    ("កើ", "កីេ"),            # ... in either order
    ("កោ", "កេា"),
    ("ញ៉ាំ", "ញាំ៉"),          # shifter typed last
    ("ញ៉ាំ", "ញ៉ំា"),          # nikahit before aa
    ("ម៉្លេះ", "ម្ល៉េះ"),        # shifter before or after the subscript
    ("ស្ដាប់", "ស្តាប់"),      # COENG DA vs COENG TA look identical
    ("ខ្មែរ​", "ខ្មែរ"),  # ZWSP never matters
])
def test_equivalent_orders_match(a, b):
    assert normalize_text(a) == normalize_text(b)
    if len(split_clusters(a)) == 1:
        assert clusters_match(a, b)


@pytest.mark.parametrize("a, b", [
    ("ក", "ខ"),
    ("កា", "កិ"),
    ("ក្រ", "ក្ល"),
    ("កា", "កាា"),
    ("ក្ស", "ស្ក"),
    ("ឲ្យ", "ឱ្យ"),  # different letters, not an ordering issue
])
def test_different_clusters_do_not_match(a, b):
    assert not clusters_match(a, b)


def test_da_ta_merge_can_be_disabled():
    assert not clusters_match("ស្ដា", "ស្តា", merge_da_ta=False)
    assert clusters_match("ស្ដា", "ស្ដា", merge_da_ta=False)


def test_canonical_order_puts_coeng_ro_last_and_composes_vowels():
    assert normalize_cluster("ស្រ្តី") == "ស្ត្រី"
    assert normalize_cluster("កីេ") == "កើ"


def test_normalisation_is_idempotent():
    for word in ["ស្រ្តី", "កេី", "ញាំ៉", "ធម៌", "កម្ពុជា"]:
        once = normalize_text(word)
        assert normalize_text(once) == once


def test_non_khmer_is_left_alone():
    assert normalize_cluster("a") == "a"
    assert clusters_match("é", "é")  # NFC still applies


# ------------------------------------------------------------ partial input

@pytest.mark.parametrize("typed", ["ស", "ស្", "ស្ត", "ស្ត្", "ស្ត្រ", "ស្រ", "ស្រ្", "ស្រ្ត", "សី"])
def test_valid_prefixes_are_in_progress(typed):
    assert is_partial(typed, "ស្ត្រី")


@pytest.mark.parametrize("typed", ["ក", "សា", "ស្ក", "ស្ត្រ្", "្", "ី", "ស្ី"])
def test_invalid_prefixes_are_wrong(typed):
    assert not is_partial(typed, "ស្ត្រី")


def test_first_half_of_composite_vowel_is_in_progress():
    assert is_partial("កេ", "កើ")
    assert is_partial("កេ", "កោ")
    assert not is_partial("កា", "កើ")


def test_trailing_coeng_needs_a_subscript_left_to_type():
    assert is_partial("ក្", "ក្រ")
    assert not is_partial("ក្", "កា")
    assert not is_partial("ក្រ្", "ក្រ")


# --------------------------------------------------------------- utilities

def test_keystroke_hint_shows_each_key():
    assert keystroke_hint("ស្ត្រី") == ["ស", "◌្", "ត", "◌្", "រ", "◌ី"]


@pytest.mark.parametrize("cluster, ok", [
    ("ស្ត្រី", True), ("ក", True), ("។", True), ("a", True),
    ("ា", False), ("ក្", False), ("កខ", False),
])
def test_is_valid_cluster(cluster, ok):
    assert is_valid_cluster(cluster) is ok
