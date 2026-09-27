import pytest

from khmertyper import metrics
from khmertyper.engine import TypingTest


def typed_test(words, keys, step=0.5, time_limit=None, start=100.0):
    """Run a test with one key every ``step`` seconds; returns (test, now)."""
    t = TypingTest(words, time_limit=time_limit)
    now = start
    for ch in keys:
        if ch == "\b":
            t.backspace(now)
        else:
            t.type(ch, now)
        now += step
    return t, now - step


def test_perfect_english_run():
    # 10 keys typed in 4.5 s (first key starts the clock).
    t, now = typed_test(["hello", "world"], "hello world"[:11], step=0.45)
    s = metrics.compute(t, now)
    assert t.finished
    assert s.duration == pytest.approx(4.5)
    assert s.keystrokes == 11 and s.errors == 0 and s.accuracy == 100.0
    assert s.correct_chars == 11                       # 10 letters + 1 space
    assert s.wpm == pytest.approx(11 / 5 / (4.5 / 60), abs=0.1)
    assert s.raw_wpm == s.wpm
    assert s.cpm == pytest.approx(11 / (4.5 / 60), abs=0.1)
    assert s.words_pm == pytest.approx(2 / (4.5 / 60), abs=0.1)


def test_khmer_cpm_counts_code_points_and_clusters_are_separate():
    # ស្ត្រី is 6 code points but one cluster.
    t, now = typed_test(["ស្ត្រី"], "ស្ត្រី", step=1.0)
    s = metrics.compute(t, now)
    assert s.duration == 5.0
    assert s.correct_chars == 6
    assert s.cpm == pytest.approx(6 * 60 / 5)
    assert s.clusters_pm == pytest.approx(1 * 60 / 5)
    assert s.cluster_counts["correct"] == 1


def test_raw_vs_net_and_accuracy_with_corrections():
    # "ab" target, typed a-x-backspace-b: 3 keystrokes, one of them wrong.
    t, now = typed_test(["ab"], "ax\bb", step=1.0)
    s = metrics.compute(t, now)
    assert s.keystrokes == 3 and s.errors == 1
    assert s.accuracy == pytest.approx(66.7)
    assert s.correct_chars == 2
    assert s.raw_wpm > s.wpm
    assert s.missed == [("b", 1)]


def test_uncorrected_errors_reduce_net_only():
    t, now = typed_test(["abc", "d"], "axc d", step=1.0)
    s = metrics.compute(t, now)
    assert s.correct_chars == 3  # a, c, d - no space credit for a wrong word
    assert s.cluster_counts["wrong"] == 1
    assert s.keystrokes == 5


def test_timed_mode_counts_partial_last_word():
    t, _ = typed_test(["abc", "def"], "abc de", step=1.0, time_limit=10)
    s = metrics.compute(t, 200.0)  # long after the limit
    assert s.duration == 10
    assert s.correct_chars == 3 + 1 + 2


def test_most_missed_is_sorted_and_skips_spaces():
    t, now = typed_test(["ក្រ", "ក្រ", "ខ"], "គ ក្រ ង", step=0.5)
    s = metrics.compute(t, now)
    assert s.missed[0] == ("ក្រ", 1)
    assert ("ខ", 1) in s.missed


def test_speed_series_has_one_point_per_second():
    t, now = typed_test(["aaaa", "bbbb"], "aaaa bbbb", step=0.5)   # 4 seconds
    s = metrics.compute(t, now)
    assert len(s.series.wpm) == 4 == len(s.series.raw) == len(s.series.errors)
    assert s.series.wpm[-1] == pytest.approx(s.wpm, abs=0.1)
    assert sum(s.series.errors) == 0


def test_errors_land_in_the_right_second():
    t, now = typed_test(["abcd"], "abxd", step=1.0)  # the x is typed at t=2s
    s = metrics.compute(t, now)
    assert s.series.errors == [0, 1, 0]


def test_no_keys_means_zero_not_crash():
    t = TypingTest(["a"])
    s = metrics.compute(t, 0.0)
    assert s.wpm == 0 and s.accuracy == 0 and s.keystrokes == 0
