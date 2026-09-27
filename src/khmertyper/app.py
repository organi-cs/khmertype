"""The Textual user interface."""

from __future__ import annotations

import os
import random
import sys
import time
from typing import Dict, List, Optional, Sequence, Tuple

from rich.cells import cell_len
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.content import Content
from textual.screen import ModalScreen, Screen
from textual.widget import Widget
from textual.widgets import Button, DataTable, Digits, Footer, Label, Select, Static, Switch

from . import metrics
from .chart import ERR, NET, RAW, render_chart
from .engine import Status, TypingTest, WordView
from .khmer import DOTTED_CIRCLE, WORD_SEPARATORS, keystroke_hint, split_clusters
from .storage import Settings, Store, mode_value
from .termwidth import Probe
from .textsource import LANGS, initial_batch, load_words, make_text, random_words

STYLES = {
    Status.UNTYPED: "$foreground-muted",
    Status.CORRECT: "$foreground",
    Status.WRONG: "bold $error",
    Status.PENDING: "underline $warning",
    Status.MISSED: "underline $error",
}
EXTRA = "dim $error"
CURSOR = " reverse"
DELETE_WORD_KEYS = {"ctrl+backspace", "alt+backspace", "ctrl+w"}
VISIBLE_LINES = 3

# Terminals built on xterm.js draw each cell on its own and do not shape
# complex scripts, so Khmer vowels and subscripts come out detached.
NON_SHAPING_TERMINALS = {
    "vscode": "VS Code's terminal",
    "Hyper": "Hyper",
}
GOOD_TERMINALS = "Ghostty, WezTerm, kitty, Terminal.app or Windows Terminal"


def non_shaping_terminal() -> Optional[str]:
    """A readable name for the current terminal if it can't draw Khmer."""
    return NON_SHAPING_TERMINALS.get(os.environ.get("TERM_PROGRAM", ""))


def mode_label(s: Settings) -> str:
    if s.mode == "time":
        return f"time {s.time}s"
    if s.mode == "words":
        return f"words {s.words}"
    return "quote"


def hint_text(cluster: str) -> str:
    keys = keystroke_hint(cluster)
    return " ".join(keys) + f"  ({len(keys)} key{'s' if len(keys) != 1 else ''})"


# --------------------------------------------------------------------- typing


class TypingArea(Widget):
    """Target text coloured by what has been typed, three lines at a time.

    Rows are separated by a blank line: Khmer vowels and subscripts stack
    above and below the base, and in a terminal they would otherwise collide
    with the neighbouring row.
    """

    DEFAULT_CSS = """
    TypingArea { height: 5; margin: 1 0; }
    """

    def __init__(self) -> None:
        super().__init__()
        self.test: Optional[TypingTest] = None

    def word_parts(self, i: int) -> List[Tuple[str, str]]:
        test = self.test
        assert test is not None
        if i > test.index:
            return [(c, STYLES[Status.UNTYPED]) for c in test.target[i]]
        view = test.view(i)
        active = i == test.index and not test.finished
        parts = []
        for ci, (cluster, status) in enumerate(zip(view.target, view.statuses)):
            style = STYLES[status]
            if active and ci == view.cursor and not view.extras:
                style += CURSOR
            parts.append((cluster, style))
        parts.extend((extra, EXTRA) for extra in view.extras)
        return parts

    def cursor_on_space(self, i: int, view: Optional[WordView]) -> bool:
        test = self.test
        return (
            test is not None and view is not None and i == test.index and not test.finished
            and (bool(view.extras) or view.cursor >= len(view.target))
        )

    def render(self) -> Content:
        test = self.test
        if test is None:
            return Content("")
        width = max(10, self.size.width)
        lines: List[List[Tuple[str, str]]] = [[]]
        used = [0]
        current_line = 0
        for i in range(len(test.words)):
            parts = self.word_parts(i)
            w = sum(cell_len(t) for t, _ in parts)
            if used[-1] and used[-1] + w > width:
                if i > test.index and len(lines) > current_line + VISIBLE_LINES:
                    break  # nothing further down is visible
                lines.append([])
                used.append(0)
            lines[-1].extend(parts)
            used[-1] += w
            if i == test.index:
                current_line = len(lines) - 1
            if used[-1] < width:
                view = test.view(i) if i == test.index else None
                lines[-1].append((" ", CURSOR.strip() if self.cursor_on_space(i, view) else ""))
                used[-1] += 1
        start = max(0, current_line - 1)
        shown = [Content.assemble(*line) for line in lines[start:start + VISIBLE_LINES]]
        return Content("\n\n").join(shown)


class TypingScreen(Screen):
    BINDINGS = [
        Binding("tab", "restart", "new test", priority=True),
        Binding("ctrl+r", "repeat", "repeat text", priority=True),
        Binding("escape", "settings", "settings", priority=True),
        Binding("f2", "font_check", "font check", priority=True),
        Binding("f3", "history", "history", priority=True),
    ]

    DEFAULT_CSS = """
    TypingScreen { align: center middle; }
    #box { width: 100%; max-width: 110; height: auto; padding: 0 2; }
    #config { color: $text-muted; }
    #status { color: $warning; height: 1; }
    #echo { height: 1; }
    #hint { height: 1; color: $text-muted; }
    """

    def __init__(self) -> None:
        super().__init__()
        self.test: Optional[TypingTest] = None
        self.source: Optional[str] = None
        self.rng = random.Random()

    @property
    def store(self) -> Store:
        return self.app.store  # type: ignore[attr-defined]

    @property
    def settings(self) -> Settings:
        return self.store.settings

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Static(id="config")
            yield Static(id="status")
            yield TypingArea()
            yield Static(id="echo")
            yield Static(id="hint")
        yield Footer()

    def on_mount(self) -> None:
        self.new_test()
        self.set_interval(0.1, self.tick)

    # ------------------------------------------------------------- lifecycle

    def new_test(self, words: Optional[Sequence[str]] = None, source: Optional[str] = None) -> None:
        s = self.settings
        if words is None:
            text = make_text(s.lang, s.mode, initial_batch(s.mode, s.words), self.rng)
            words, source = text.words, text.source
        self.source = source
        self.test = TypingTest(
            list(words),
            time_limit=float(s.time) if s.mode == "time" else None,
            merge_da_ta=s.merge_da_ta,
        )
        self.query_one(TypingArea).test = self.test
        self.refresh_all()

    def action_restart(self) -> None:
        self.new_test()

    def action_repeat(self) -> None:
        if self.test is not None:
            self.new_test(self.test.words[: len(self.test.target)], self.source)

    def action_settings(self) -> None:
        def done(changed: Optional[bool]) -> None:
            self.new_test()

        self.app.push_screen(SettingsScreen(), done)

    def action_font_check(self) -> None:
        self.app.push_screen(FontCheckScreen())

    def action_history(self) -> None:
        self.app.push_screen(HistoryScreen())

    def tick(self) -> None:
        test = self.test
        if test is None or not test.started:
            return
        now = time.monotonic()
        if test.time_limit is not None and not test.finished:
            if test.elapsed(now) >= test.time_limit:
                test.finish(test.started_at + test.time_limit)  # type: ignore[operator]
        if test.finished:
            self.show_results(now)
            return
        self.refresh_status(now)

    def show_results(self, now: float) -> None:
        test = self.test
        if test is None:
            return
        self.test = None  # stop ticking into the results
        stats = metrics.compute(test, now)
        s = self.settings
        record = {
            "lang": s.lang,
            "mode": s.mode,
            "mode_value": mode_value(s),
            **{k: v for k, v in stats.to_dict().items() if k not in ("cluster_counts",)},
        }
        is_pb, previous = (False, None)
        if stats.keystrokes > 0 and stats.duration >= 1:
            is_pb, previous = self.store.add_result(record)

        def after(action: Optional[str]) -> None:
            if action == "repeat":
                self.new_test(test.words[: len(test.target)], self.source)
            elif action == "settings":
                self.new_test()
                self.action_settings()
            elif action == "history":
                self.new_test()
                self.action_history()
            else:
                self.new_test()

        self.app.push_screen(ResultsScreen(stats, s, is_pb, previous, self.source), after)

    # ----------------------------------------------------------------- input

    def on_key(self, event: events.Key) -> None:
        test = self.test
        if test is None or test.finished:
            return
        now = time.monotonic()
        key, ch = event.key, event.character
        if key == "backspace":
            test.backspace(now)
        elif key in DELETE_WORD_KEYS:
            test.delete_word(now)
        elif ch and len(ch) == 1 and (ch.isprintable() or ch in WORD_SEPARATORS):
            test.type(ch, now)
        else:
            return
        event.stop()
        event.prevent_default()
        if test.time_limit is not None and test.index > len(test.words) - 40:
            test.extend(random_words(load_words(self.settings.lang), 100, self.rng))
        if test.finished:
            self.show_results(now)
        else:
            self.refresh_all(now)

    def on_paste(self, event: events.Paste) -> None:
        event.stop()  # no pasting into a typing test

    # --------------------------------------------------------------- display

    def refresh_all(self, now: Optional[float] = None) -> None:
        s = self.settings
        config = f"{LANGS[s.lang]} · {mode_label(s)}"
        if self.source:
            config += f" · {self.source}"
        warning = ""
        if s.lang == "km" and non_shaping_terminal():
            warning = "   ⚠ this terminal can't draw Khmer properly - see f2"
        self.query_one("#config", Static).update(Content.assemble(config, (warning, "$warning")))
        self.query_one(TypingArea).refresh()
        self.refresh_echo()
        self.refresh_status(now if now is not None else time.monotonic())

    def refresh_status(self, now: float) -> None:
        test = self.test
        if test is None:
            return
        s = self.settings
        if s.mode == "time":
            left = s.time - test.elapsed(now) if test.started else s.time
            progress = f"{max(0, int(left + 0.999))}"
        else:
            progress = f"{min(test.index + (1 if test.typed[-1] else 0), len(test.words))}/{len(test.words)}"
        parts = [progress]
        if s.live_speed and test.started:
            elapsed = max(test.elapsed(now), 1.0)
            wpm = metrics.per_minute(test.net_chars() / metrics.CHARS_PER_WORD, elapsed)
            keys = [e for e in test.events if e.kind != "backspace"]
            acc = 100.0 * sum(e.correct for e in keys) / len(keys) if keys else 100.0
            parts.append(f"{wpm:.0f} wpm  {acc:.0f}%")
        elif not test.started:
            parts.append("start typing…")
        self.query_one("#status", Static).update(Content("   ".join(parts)))

    def refresh_echo(self) -> None:
        test = self.test
        echo = self.query_one("#echo", Static)
        hint = self.query_one("#hint", Static)
        if test is None:
            return
        view = test.current()
        pieces: List[Tuple[str, str]] = [("› ", "$text-muted")]
        for i, cluster in enumerate(view.typed):
            status = view.statuses[i] if i < len(view.statuses) else None
            pieces.append((cluster, STYLES[status] if status else EXTRA))
        pieces.append((" ", "reverse"))
        echo.update(Content.assemble(*pieces))

        message = ""
        if self.settings.hints:
            wrong = [i for i, st in enumerate(view.statuses) if st is Status.WRONG]
            if wrong:
                message = f"expected {view.target[wrong[0]]} = {hint_text(view.target[wrong[0]])}"
            elif view.extras:
                message = "extra characters - press backspace"
        hint.update(Content(message))


# -------------------------------------------------------------------- results


class ResultsScreen(Screen[str]):
    BINDINGS = [
        Binding("tab,enter,escape", "choose('next')", "next test", priority=True),
        Binding("r", "choose('repeat')", "repeat text"),
        Binding("s", "choose('settings')", "settings"),
        Binding("h", "choose('history')", "history"),
    ]

    DEFAULT_CSS = """
    ResultsScreen { align: center top; }
    #results { width: 100%; max-width: 100; padding: 1 2; }
    .big { height: auto; width: auto; margin-right: 4; }
    .big Digits { color: $warning; width: auto; }
    .big Label { color: $text-muted; }
    #headline { height: auto; }
    #pb { margin: 1 0; }
    #chart { margin: 1 0; }
    .section { color: $text-muted; margin-top: 1; }
    """

    def __init__(self, stats: metrics.Stats, settings: Settings, is_pb: bool,
                 previous: Optional[Dict], source: Optional[str]) -> None:
        super().__init__()
        self.stats = stats
        self.settings = settings
        self.is_pb = is_pb
        self.previous = previous
        self.source = source

    def compose(self) -> ComposeResult:
        st, s = self.stats, self.settings
        with VerticalScroll(id="results"):
            with Horizontal(id="headline"):
                for value, label in ((st.wpm, "wpm"), (st.accuracy, "acc %"), (st.raw_wpm, "raw")):
                    with Vertical(classes="big"):
                        yield Label(label)
                        yield Digits(f"{value:.0f}")
            c = st.cluster_counts
            yield Static(Content.assemble(
                (f"{LANGS[s.lang]} · {mode_label(s)}", "bold"),
                (f" · {self.source}" if self.source else "", "$text-muted"),
                "\n",
                f"cpm {st.cpm:.0f} (raw {st.raw_cpm:.0f})   clusters/min {st.clusters_pm:.0f}   "
                f"words/min {st.words_pm:.0f}   time {st.duration:.1f}s\n",
                f"keystrokes {st.keystrokes} ({st.errors} errors)   clusters: ",
                (f"{c['correct']} correct", "$success"), " / ",
                (f"{c['wrong']} wrong", "$error"), " / ",
                (f"{c['extra']} extra", "$error"), " / ",
                (f"{c['missed']} missed", "$error"),
            ))
            yield Static(self.pb_line(), id="pb")
            yield Static(self.chart(), id="chart")
            yield Static(self.missed(), id="missed")
        yield Footer()

    def pb_line(self) -> Content:
        if self.is_pb:
            if self.previous:
                return Content.assemble(("New personal best!", "bold $success"),
                                        f"  (previous {self.previous['wpm']:.0f} wpm)")
            return Content.assemble(("First result for this mode - personal best set.", "$success"))
        if self.previous:
            return Content(f"personal best: {self.previous['wpm']:.0f} wpm, {self.previous['accuracy']:.0f}% acc")
        return Content("(too short to save)")

    def chart(self) -> Content:
        width = max(20, min(70, self.app.size.width - 16))
        series = self.stats.series
        lines = render_chart(series.wpm, series.raw, series.errors, width=width, height=9)
        colours = {NET: "bold $warning", RAW: "$primary", ERR: "bold $error"}
        out: List[Tuple[str, str]] = [("speed  ", "bold"), ("* net wpm", colours[NET]), ("  ", ""),
                                      (". raw wpm", colours[RAW]), ("  ", ""), ("x error", colours[ERR]), ("\n", "")]
        for line in lines:
            # Only plot markers are coloured; axes and labels stay muted.
            out.extend((ch, colours.get(ch, "$text-muted")) for ch in line)
            out.append(("\n", ""))
        return Content.assemble(*out)

    def missed(self) -> Content:
        if not self.stats.missed:
            return Content.assemble(("No missed clusters. ", "$success"), "Nice.")
        parts: List[Tuple[str, str]] = [("most missed clusters\n", "bold")]
        for cluster, n in self.stats.missed[:8]:
            parts.append((f"  {cluster}", "bold $error"))
            parts.append((f"  ×{n}   ", ""))
            parts.append((hint_text(cluster) + "\n", "$text-muted"))
        return Content.assemble(*parts)

    def action_choose(self, what: str) -> None:
        self.dismiss(what)


# ------------------------------------------------------------------- settings


class SettingsScreen(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "close", "close")]

    DEFAULT_CSS = """
    SettingsScreen { align: center middle; }
    #dialog { width: 64; height: auto; max-height: 100%; border: round $primary;
              background: $surface; padding: 0 2; overflow-y: auto; }
    #dialog .title { margin: 1 0; }
    #dialog .row { height: 1; margin-bottom: 1; }
    #dialog .row Label { width: 22; }
    #dialog .row Select { width: 1fr; }
    #dialog Switch { border: none; padding: 0; height: 1; width: auto; margin-right: 2; }
    #dialog .switch Label { width: 1fr; }
    #buttons { height: 1; margin: 1 0; }
    #buttons Button { margin-right: 2; }
    """

    @property
    def settings(self) -> Settings:
        return self.app.store.settings  # type: ignore[attr-defined]

    def compose(self) -> ComposeResult:
        s = self.settings
        themes = sorted(self.app.available_themes)
        rows = [
            ("Language", "lang", [("ខ្មែរ Khmer", "km"), ("English (comparison)", "en")], s.lang),
            ("Mode", "mode", [("time", "time"), ("words", "words"), ("quote", "quote")], s.mode),
            ("Time (seconds)", "time", [(str(v), v) for v in (15, 30, 60, 120)], s.time),
            ("Word count", "words", [(str(v), v) for v in (10, 25, 50)], s.words),
            ("Theme", "theme", [(t, t) for t in themes], s.theme if s.theme in themes else themes[0]),
        ]
        with Vertical(id="dialog"):
            yield Label("[b]Settings[/b]", classes="title")
            for label, key, options, value in rows:
                with Horizontal(classes="row"):
                    yield Label(label)
                    yield Select(options, value=value, allow_blank=False, id=key, compact=True)
            for label, key, value in (
                ("Live speed while typing", "live_speed", s.live_speed),
                ("Show key hints on errors", "hints", s.hints),
                ("Treat ្ដ and ្ត as the same", "merge_da_ta", s.merge_da_ta),
            ):
                with Horizontal(classes="row switch"):
                    yield Switch(value=value, id=key)
                    yield Label(label)
            with Horizontal(id="buttons"):
                yield Button("Done", id="done", variant="primary", compact=True)
                yield Button("Font check", id="font", compact=True)
                yield Button("History", id="history", compact=True)

    def on_select_changed(self, event: Select.Changed) -> None:
        key = event.select.id
        if key is None or event.value is Select.BLANK:
            return
        setattr(self.settings, key, event.value)
        if key == "theme":
            self.app.theme = str(event.value)

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id:
            setattr(self.settings, event.switch.id, event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "font":
            self.app.push_screen(FontCheckScreen())
        elif event.button.id == "history":
            self.app.push_screen(HistoryScreen())
        else:
            self.action_close()

    def action_close(self) -> None:
        self.app.store.save()  # type: ignore[attr-defined]
        self.dismiss(True)


# ----------------------------------------------------------------- font check

FONT_SAMPLES = [
    ("Consonants", "ក ខ គ ឃ ង ច ឆ ជ ឈ ញ ដ ឋ ឌ ឍ ណ ត ថ ទ ធ ន ប ផ ព ភ ម យ រ ល វ ស ហ ឡ អ"),
    ("Vowels", "កា កិ កី កឹ កឺ កុ កូ កួ កើ កឿ កៀ កេ កែ កៃ កោ កៅ កុំ កំ កាំ កះ"),
    ("Subscripts", "ក្ក ខ្ញ ង្គ ញ្ញ ន្ធ ប្រ ស្ត្រី ក្សត្រ ល្អ ម្ល៉េះ"),
    ("Signs", "ប៉ា ស៊ី ធម៌ កំ ទេ៍ ៗ ។ ៕ ៛"),
    ("Digits", "០ ១ ២ ៣ ៤ ៥ ៦ ៧ ៨ ៩"),
    ("Sentence", "ប្រាសាទអង្គរវត្តជានិមិត្តរូបរបស់ប្រទេសកម្ពុជា។"),
]
WIDTH_SAMPLES = ["ក", "កា", "ក្រ", "ស្ត្រី", "ញ៉ាំ", "ឡើង", "abc"]


class FontCheckScreen(Screen):
    BINDINGS = [Binding("escape,q,enter", "app.pop_screen", "back")]

    DEFAULT_CSS = """
    FontCheckScreen { align: center top; }
    #font { width: 100%; max-width: 100; padding: 1 2; }
    .sample { margin-bottom: 1; }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="font"):
            yield Static(Content.assemble(
                ("Font check\n", "bold"),
                ("Every line below should show joined Khmer letters: subscripts under their "
                 "base, េ drawn to the left, and no dotted circles (◌) or empty boxes.", "$text-muted"),
            ), classes="sample")
            for title, sample in FONT_SAMPLES:
                yield Static(Content.assemble((f"{title}\n", "$text-muted"), (sample, "bold")), classes="sample")
            yield Static(self.width_check(), classes="sample")
            yield Static(self.calibration(), classes="sample")
            yield Static(self.environment(), classes="sample")
            yield Static(Content(
                "If letters show as boxes, install a Khmer font (see README). If subscripts sit "
                "beside the base or marks float on dotted circles, your terminal does not shape "
                "Khmer. Ghostty draws it best on macOS; WezTerm, kitty and Windows Terminal "
                "also shape Khmer, and macOS Terminal works with some gaps in stacked letters."),
                classes="sample")
        yield Footer()

    def width_check(self) -> Content:
        parts: List[Tuple[str, str]] = [
            ("Width check\n", "$text-muted"),
            ("The right-hand bars should form a straight column. If they wobble, your terminal "
             "measures Khmer differently from this app; typing still works but the cursor may "
             "look slightly off.\n\n", "$text-muted"),
        ]
        for sample in WIDTH_SAMPLES:
            w, n = cell_len(sample), len(split_clusters(sample))
            parts.append(("│", "$accent"))
            parts.append((sample + " " * (8 - w), "bold"))
            parts.append(("│", "$accent"))
            parts.append((f"  {w} cell{'s' if w != 1 else ''}, {n} cluster{'s' if n != 1 else ''}\n", "$text-muted"))
        return Content.assemble(*parts)

    def calibration(self) -> Content:
        probe: Optional[Probe] = getattr(self.app, "width_probe", None)
        head = ("Width calibration\n", "$text-muted")
        if probe is None:
            return Content.assemble(head, "not run")
        diffs = probe.differences()
        if probe.applied:
            listed = "  ".join(f"{DOTTED_CIRCLE}{ch} {term}" for ch, (_, term) in sorted(diffs.items()))
            mode = ("Switched off the terminal's grapheme-cluster mode (DEC 2027) for this "
                    "session so widths add up per character; it is switched back on at exit. "
                    if probe.grapheme_mode_off else "")
            return Content.assemble(
                head,
                (f"Adjusted: {mode}This terminal gives {len(diffs)} Khmer marks a column of their "
                 "own (Unicode gives them none), so the layout now follows the terminal. "
                 "If the bars above line up, the adjustment worked.\n", "$success"),
                (listed, "$text-muted"),
            )
        if probe.reason:
            return Content.assemble(head, f"not adjusted - {probe.reason}")
        return Content.assemble(head, ("this terminal spaces Khmer the same way as the app", "$success"))

    def environment(self) -> Content:
        env = os.environ
        term = env.get("TERM_PROGRAM") or env.get("WT_SESSION") and "Windows Terminal" or env.get("TERM", "?")
        # Textual replaces sys.stdout while running; ask the real terminal stream.
        enc = getattr(sys.__stdout__, "encoding", None) or "?"
        lang = env.get("LC_ALL") or env.get("LC_CTYPE") or env.get("LANG") or "(not set)"
        ok = "utf" in enc.lower()
        parts: List[Tuple[str, str]] = [
            ("Environment\n", "$text-muted"),
            (f"terminal: {term}   locale: {lang}   output encoding: ", ""),
            (enc, "$success" if ok else "bold $error"),
        ]
        bad = non_shaping_terminal()
        if bad:
            parts.append((
                f"\n\n{bad[0].upper() + bad[1:]} is built on xterm.js, which draws each character "
                f"cell on its own and cannot join Khmer vowels and subscripts to their letters. "
                f"Nothing inside khmertyper can fix that. Run it in {GOOD_TERMINALS} instead.",
                "bold $warning",
            ))
        return Content.assemble(*parts)


# -------------------------------------------------------------------- history


class HistoryScreen(Screen):
    BINDINGS = [Binding("escape,q", "app.pop_screen", "back")]

    DEFAULT_CSS = """
    HistoryScreen { align: center top; }
    #history { width: 100%; max-width: 110; padding: 1 2; }
    DataTable { height: auto; max-height: 16; margin-bottom: 1; }
    .section { margin-top: 1; color: $text-muted; }
    """

    @property
    def store(self) -> Store:
        return self.app.store  # type: ignore[attr-defined]

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="history"):
            yield Label("Personal bests", classes="section")
            yield DataTable(id="bests", zebra_stripes=True)
            yield Static(self.comparison())
            yield Label("Recent tests", classes="section")
            yield DataTable(id="recent", zebra_stripes=True)
            yield Static(self.all_time_missed())
            yield Static(Content(f"saved in {self.store.path}"), classes="section")
        yield Footer()

    def on_mount(self) -> None:
        bests = self.query_one("#bests", DataTable)
        bests.add_columns("language", "mode", "wpm", "raw", "acc", "clusters/min", "date")
        for key in sorted(self.store.bests):
            r = self.store.bests[key]
            bests.add_row(LANGS.get(r["lang"], r["lang"]), f"{r['mode']} {r['mode_value']}",
                          f"{r['wpm']:.0f}", f"{r['raw_wpm']:.0f}", f"{r['accuracy']:.0f}%",
                          f"{r['clusters_pm']:.0f}", r.get("timestamp", "")[:10])
        recent = self.query_one("#recent", DataTable)
        recent.add_columns("date", "language", "mode", "wpm", "acc", "time")
        for r in reversed(self.store.history[-25:]):
            recent.add_row(r.get("timestamp", "")[:16].replace("T", " "), LANGS.get(r["lang"], r["lang"]),
                           f"{r['mode']} {r['mode_value']}", f"{r['wpm']:.0f}", f"{r['accuracy']:.0f}%",
                           f"{r['duration']:.0f}s")

    def comparison(self) -> Content:
        rows = []
        for key, km in sorted(self.store.bests.items()):
            if not key.startswith("km:"):
                continue
            en = self.store.bests.get("en:" + key[3:])
            if en and en["wpm"] > 0:
                rows.append(f"  {km['mode']} {km['mode_value']}: Khmer {km['wpm']:.0f} wpm vs "
                            f"English {en['wpm']:.0f} wpm  ({100 * km['wpm'] / en['wpm']:.0f}%)\n")
        if not rows:
            return Content("Khmer vs English: finish the same mode in both languages to compare.")
        return Content.assemble(("Khmer vs English (personal bests)\n", "bold"), *rows)

    def all_time_missed(self) -> Content:
        missed = self.store.most_missed("km", 12)
        if not missed:
            return Content("")
        parts: List[Tuple[str, str]] = [("Most missed Khmer clusters (all time)\n", "bold")]
        for cluster, n in missed:
            parts += [(f"  {cluster}", "bold $error"), (f" ×{n}  ", "")]
        return Content.assemble(*parts)


# ------------------------------------------------------------------------ app


class KhmerTyper(App):
    TITLE = "khmertyper"

    def __init__(self, store: Store, start_with_font_check: bool = False,
                 width_probe: Optional[Probe] = None) -> None:
        super().__init__()
        self.store = store
        self.start_with_font_check = start_with_font_check
        self.width_probe = width_probe

    def on_mount(self) -> None:
        theme = self.store.settings.theme
        self.theme = theme if theme in self.available_themes else "textual-dark"
        self.push_screen(TypingScreen())
        if self.start_with_font_check:
            self.push_screen(FontCheckScreen())
        bad = non_shaping_terminal()
        if bad and self.store.settings.lang == "km":
            self.notify(
                f"You're in {bad}, which can't join Khmer letters, so some words will look "
                f"broken. For readable Khmer, run khmertyper in {GOOD_TERMINALS}.",
                title="Khmer won't display correctly here",
                severity="warning",
                timeout=20,
            )
