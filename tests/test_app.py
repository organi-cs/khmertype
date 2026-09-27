"""Headless UI smoke tests using Textual's pilot."""

import asyncio

from textual.events import Key
from textual.keys import _character_to_key

from khmertyper.app import (FontCheckScreen, HistoryScreen, KhmerTyper, ResultsScreen,
                            SettingsScreen, TypingArea, TypingScreen)
from khmertyper.storage import Store


def run(coro):
    return asyncio.run(coro)


async def type_text(pilot, text):
    """Send keys exactly as Textual's terminal parser produces them: one Key
    event per code point, carrying the character. (``pilot.press`` loses the
    character for combining marks such as COENG, so it can't be used here.)"""
    for ch in text:
        pilot.app.post_message(Key(_character_to_key(ch), ch))
        await pilot.pause()


def make_app(**settings):
    store = Store()
    for k, v in settings.items():
        setattr(store.settings, k, v)
    return KhmerTyper(store)


def test_word_mode_to_results_and_history_saved():
    async def scenario():
        app = make_app(mode="words", words=10, lang="km")
        async with app.run_test(size=(100, 30)) as pilot:
            screen = app.screen
            assert isinstance(screen, TypingScreen)
            screen.new_test(["ស្ត្រី", "ក្រុង"])
            # Type the first word in a non-canonical order: ស ្ រ ្ ត ី
            await type_text(pilot, "ស្រ្តី")
            assert screen.test.current().correct
            screen.test.started_at -= 5  # results shorter than 1s are not saved
            await type_text(pilot, " ក្រុង")
            await pilot.pause()
            assert isinstance(app.screen, ResultsScreen)
            stats = app.screen.stats
            assert stats.accuracy == 100.0
            assert stats.cluster_counts["correct"] == 3
            assert len(app.store.history) == 1
            await pilot.press("enter")
            assert isinstance(app.screen, TypingScreen)

    run(scenario())


def test_render_marks_errors_and_pending():
    async def scenario():
        app = make_app(mode="words")
        async with app.run_test(size=(80, 24)) as pilot:
            screen = app.screen
            screen.new_test(["ក្រុង", "ខ្មែរ"])
            await type_text(pilot, "ក្")  # valid but unfinished
            area = screen.query_one(TypingArea)
            text = area.render()
            assert "ក្រុ" in text.plain and "ខ្មែរ" in text.plain
            await pilot.press("backspace", "backspace")
            await type_text(pilot, "ខ")
            assert "expected" in str(screen.query_one("#hint").render())

    run(scenario())


def test_typing_area_scrolls_to_the_current_line():
    async def scenario():
        app = make_app(mode="time", time=120, lang="en")
        async with app.run_test(size=(60, 24)) as pilot:
            screen = app.screen
            words = [f"w{i:03d}" for i in range(300)]
            screen.new_test(words)
            for n, ch in enumerate(" ".join(words[:149]) + " "):
                screen.test.type(ch, 1000.0 + n * 0.1)  # fast-forward via the engine
            await type_text(pilot, words[149] + " ")
            plain = screen.query_one(TypingArea).render().plain
            assert "w150" in plain            # the word being typed is visible
            assert "w000" not in plain         # early lines have scrolled away
            assert plain.count("\n\n") == 2   # three rows with blank spacers

    run(scenario())


def test_timed_mode_finishes_and_extends_words():
    async def scenario():
        app = make_app(mode="time", time=15, lang="en")
        async with app.run_test(size=(100, 30)) as pilot:
            screen = app.screen
            test = screen.test
            for word in test.words[:3]:
                await type_text(pilot, word + " ")
            test.started_at -= 20  # jump past the time limit
            screen.tick()
            await pilot.pause()
            assert isinstance(app.screen, ResultsScreen)
            assert app.screen.stats.duration == 15

    run(scenario())


def test_secondary_screens_open():
    async def scenario():
        app = make_app()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("escape")
            assert isinstance(app.screen, SettingsScreen)
            await pilot.press("escape")
            assert isinstance(app.screen, TypingScreen)
            await pilot.press("f2")
            assert isinstance(app.screen, FontCheckScreen)
            await pilot.press("escape", "f3")
            assert isinstance(app.screen, HistoryScreen)

    run(scenario())


def test_warns_in_terminals_that_cannot_shape_khmer(monkeypatch):
    monkeypatch.setenv("TERM_PROGRAM", "vscode")

    async def scenario():
        app = make_app(lang="km")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert any("can't join Khmer" in n.message for n in app._notifications)
            assert "can't draw Khmer" in str(app.screen.query_one("#config").render())
            await pilot.press("f2")
            assert isinstance(app.screen, FontCheckScreen)
            assert "xterm.js" in str(app.screen.environment())

    run(scenario())


def test_no_warning_in_other_terminals(monkeypatch):
    monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")

    async def scenario():
        app = make_app(lang="km")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert not list(app._notifications)
            assert "can't draw Khmer" not in str(app.screen.query_one("#config").render())

    run(scenario())


def test_font_check_reports_real_encoding_and_plural_clusters():
    async def scenario():
        app = make_app()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("f2")
            screen = app.screen
            assert "output encoding: ?" not in str(screen.environment())
            width = str(screen.width_check())
            assert "2 clusters\n" in width and "1 cluster\n" in width

    run(scenario())
