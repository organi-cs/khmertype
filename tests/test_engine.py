import pytest

from khmertyper.engine import Status, TypingTest, compare_word
from khmertyper.khmer import normalize_cluster, split_clusters

S = Status


def statuses(target, typed, committed=False):
    clusters = split_clusters(target)
    view = compare_word(clusters, [normalize_cluster(c) for c in clusters], typed, committed=committed)
    return list(view.statuses), list(view.extras)


def feed(test, text, clock):
    for ch in text:
        test.type(ch, clock())


# ------------------------------------------------------------ compare_word

def test_partial_cluster_is_pending_not_wrong():
    assert statuses("ស្ត្រី", "ស្") == ([S.PENDING], [])
    assert statuses("ក្រុង", "ក្រ") == ([S.PENDING, S.UNTYPED], [])


def test_alternative_typing_order_is_correct():
    assert statuses("ស្ត្រី", "ស្រ្តី") == ([S.CORRECT], [])
    assert statuses("កើត", "កេីត") == ([S.CORRECT, S.CORRECT], [])


def test_incomplete_cluster_becomes_wrong_once_you_move_on():
    # "ក" was still in progress for "ក្រុ", but typing "ង" started a new cluster.
    assert statuses("ក្រុង", "ក") == ([S.PENDING, S.UNTYPED], [])
    assert statuses("ក្រុង", "កង") == ([S.WRONG, S.CORRECT], [])
    assert statuses("ក្រុង", "ក្រង") == ([S.WRONG, S.CORRECT], [])


def test_skipping_a_vowel_only_costs_that_cluster():
    assert statuses("កាត", "កត") == ([S.WRONG, S.CORRECT], [])


def test_committed_word_marks_pending_wrong_and_untyped_missed():
    assert statuses("ក្រុង", "ក្រ", committed=True) == ([S.WRONG, S.MISSED], [])


def test_extra_clusters():
    assert statuses("ក", "កខគ") == ([S.CORRECT], ["ខ", "គ"])


def test_english_is_per_letter():
    assert statuses("cat", "cxt") == ([S.CORRECT, S.WRONG, S.CORRECT], [])
    assert statuses("cat", "ca") == ([S.CORRECT, S.CORRECT, S.UNTYPED], [])


# ------------------------------------------------------------- TypingTest

def test_word_mode_finishes_on_last_correct_cluster(clock):
    t = TypingTest(["ខ្ញុំ", "ទៅ"])
    feed(t, "ខ្ញុំ ទៅ", clock)
    assert t.finished
    assert all(e.correct for e in t.events)
    assert t.net_chars() == len("ខ្ញុំ") + 1 + len("ទៅ")


def test_space_on_empty_word_is_ignored(clock):
    t = TypingTest(["ក", "ខ"])
    feed(t, "  ក  ", clock)
    assert t.typed == ["ក", ""]
    assert len(t.events) == 2  # "ក" and one space


def test_zwsp_and_nbsp_work_as_word_separators(clock):
    """The Windows NiDA layout types ZWSP on the spacebar."""
    t = TypingTest(["ក", "ខ", "គ"])
    feed(t, "ក​ខ គ", clock)
    assert t.finished and t.net_chars() == 5


def test_keystroke_accuracy_counts_fixed_mistakes(clock):
    t = TypingTest(["កា", "ខ"])
    feed(t, "កិ", clock)            # wrong vowel
    t.backspace(clock())
    feed(t, "ា ខ", clock)
    assert t.finished
    keys = [e for e in t.events if e.kind != "backspace"]
    assert [e.correct for e in keys] == [True, False, True, True, True]
    assert t.missed["កា"] == 1


def test_moving_on_from_unfinished_cluster_is_an_error(clock):
    t = TypingTest(["ក្រុង"])
    feed(t, "ក", clock)
    assert t.events[-1].correct            # in progress
    feed(t, "ង", clock)
    assert not t.events[-1].correct        # left "ក្រុ" unfinished
    assert t.missed["ក្រុ"] == 1


def test_space_skips_rest_of_word_as_missed(clock):
    t = TypingTest(["ក្រុង", "ខ"])
    feed(t, "ក្រុ ", clock)
    assert not t.events[-1].correct
    assert t.missed["ង"] == 1
    assert t.view(0).statuses == (S.CORRECT, S.MISSED)


def test_backspace_reopens_only_incorrect_previous_word(clock):
    t = TypingTest(["ក", "ខ", "គ"])
    feed(t, "ក ", clock)
    t.backspace(clock())
    assert t.index == 1  # previous word was correct: stays locked
    feed(t, "ង ", clock)
    t.backspace(clock())
    assert t.index == 1 and t.typed[-1] == "ង"
    t.backspace(clock())
    feed(t, "ខ ", clock)
    assert t.view(1).correct


def test_delete_word(clock):
    t = TypingTest(["ស្ត្រី", "ខ"])
    feed(t, "ស្ត", clock)
    t.delete_word(clock())
    assert t.typed == [""]
    feed(t, "ស្ត្រី", clock)
    assert t.current().correct


def test_backspace_removes_one_code_point_not_a_whole_cluster(clock):
    t = TypingTest(["ស្ត្រី"])
    feed(t, "ស្ត្រ", clock)
    t.backspace(clock())
    assert t.typed[-1] == "ស្ត្"
    assert t.current().statuses == (S.PENDING,)


def test_timed_mode_ignores_keys_after_limit_and_does_not_end_on_last_word(clock):
    t = TypingTest(["ក", "ខ"], time_limit=5)
    feed(t, "ក ខ", clock)
    assert not t.finished  # timed tests only end on the clock (or the final space)
    t.type(" ", clock(10))
    assert t.finished and t.elapsed(clock()) == 5
    assert t.typed == ["ក", "ខ"]


def test_extend_adds_words(clock):
    t = TypingTest(["ក"], time_limit=30)
    t.extend(["ខ", " ", "គ"])
    assert t.words == ["ក", "ខ", "គ"]
    assert t.target[-1] == ["គ"]


def test_empty_test_is_rejected():
    with pytest.raises(ValueError):
        TypingTest(["", "​"])


def test_time_limit_is_reached_despite_float_rounding():
    start = 25.276
    assert (start + 30) - start < 30  # the rounding this guards against
    t = TypingTest(["ក"], time_limit=30)
    t.type("ក", start)
    assert t.elapsed(start + 30) == 30
    assert t.elapsed(start + 31) == 30
