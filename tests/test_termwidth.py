import pytest
from rich.cells import cell_len

from khmertyper import termwidth
from khmertyper.termwidth import BASE, CHECKS, MARKS, apply, interpret, override_ranges, restore

AA, COENG, I = "ា", "្", "ិ"  # ា (spacing), ្, ិ (non-spacing)


@pytest.fixture(autouse=True)
def unpatched():
    restore()
    yield
    restore()


def columns_for(widths):
    """Fake cursor reports from a terminal with per-character widths."""
    cols = {BASE: 1}
    for m in MARKS:
        cols[BASE + m] = 1 + widths.get(m, 0)
    for cluster in CHECKS:
        cols[cluster] = sum(widths.get(ch, 0 if ch in MARKS else 1) for ch in cluster)
    return cols


def test_override_ranges_splits_existing_entries():
    table = [(10, 20, 0), (30, 30, 2)]
    assert override_ranges(table, {15: 1, 25: 0}) == [(10, 14, 0), (15, 15, 1), (16, 20, 0), (25, 25, 0), (30, 30, 2)]
    assert override_ranges(table, {10: 1, 20: 1}) == [(10, 10, 1), (11, 19, 0), (20, 20, 1), (30, 30, 2)]


def test_terminal_matching_unicode_needs_no_patch():
    probe = apply(interpret(columns_for({})))
    assert not probe.applied and not probe.reason and not probe.differences()
    assert cell_len("ក" + AA) == 1


def test_macos_terminal_style_widths_are_applied():
    """macOS Terminal gives spacing vowels and COENG a column each."""
    probe = apply(interpret(columns_for({AA: 1, COENG: 1})))
    assert probe.applied
    assert probe.differences() == {AA: (0, 1), COENG: (0, 1)}
    assert cell_len("កា") == 2
    assert cell_len("ក្រ") == 3
    assert cell_len("ក" + I) == 1          # untouched marks keep Rich's width
    assert cell_len("abc") == 3
    restore()
    assert cell_len("កា") == 1 and cell_len("ក្រ") == 2


def test_cluster_sized_terminals_are_not_patched():
    """xterm.js-style: the whole cluster is one column, not the sum of parts."""
    cols = columns_for({})
    cols[CHECKS[1]] = 1  # ស្ត្រី reported as a single column
    probe = apply(interpret(cols))
    assert not probe.applied and "whole clusters" in probe.reason


def test_impossible_reports_are_rejected():
    cols = columns_for({})
    cols[BASE + AA] = 9
    assert "impossible" in apply(interpret(cols)).reason


def test_no_tty_means_no_measurement(monkeypatch):
    assert termwidth.measure() is None  # pytest's stdin is not a terminal
    probe = termwidth.calibrate()
    assert not probe.applied and "did not answer" in probe.reason


def test_ghostty_style_grapheme_mode_is_switched_off(monkeypatch):
    """Cluster-sized while DEC mode 2027 is on, per-character once it's off."""
    state = {"on": True}
    written = []
    per_char = columns_for({AA: 1})
    clustered = dict(per_char, **{CHECKS[1]: 2})

    def fake_write(seq):
        written.append(seq)
        state["on"] = seq.endswith("h")

    monkeypatch.setattr(termwidth, "_write", fake_write)
    monkeypatch.setattr(termwidth, "grapheme_mode", lambda timeout=0.3: state["on"])
    monkeypatch.setattr(termwidth, "measure", lambda timeout=1.0: clustered if state["on"] else per_char)
    registered = []
    monkeypatch.setattr(termwidth.atexit, "register", registered.append)

    probe = termwidth.calibrate()
    assert probe.applied and probe.grapheme_mode_off
    assert written == ["\x1b[?2027l"] and registered == [termwidth.restore_terminal]
    assert cell_len("កា") == 2


def test_grapheme_mode_left_alone_when_switching_off_does_not_help(monkeypatch):
    state = {"on": True}
    written = []
    clustered = dict(columns_for({}), **{CHECKS[1]: 1})

    def fake_write(seq):
        written.append(seq)
        state["on"] = seq.endswith("h")

    monkeypatch.setattr(termwidth, "_write", fake_write)
    monkeypatch.setattr(termwidth, "grapheme_mode", lambda timeout=0.3: state["on"])
    monkeypatch.setattr(termwidth, "measure", lambda timeout=1.0: clustered)
    probe = termwidth.calibrate()
    assert not probe.applied and "whole clusters" in probe.reason
    assert written == ["\x1b[?2027l", "\x1b[?2027h"] and state["on"]
