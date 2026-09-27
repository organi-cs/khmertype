# khmertyper

A Monkeytype-style typing test for **Khmer**, in the browser or the terminal.
It measures speed and accuracy on real Khmer text and copes with the fact that
one visible letter block, like **ស្ត្រី**, takes six keystrokes (ស ្ ត ្ រ ី)
and can be typed in more than one valid order.

It's built for students and anyone learning the Khmer keyboard. An English mode
is included so you can compare the two.

**Start here:** the browser version draws Khmer perfectly in any modern browser,
with no terminal or font setup:

```bash
uv run khmertyper web
```

The terminal version (`uv run khmertyper`) is there too; see
[Terminal and font setup](#terminal-and-font-setup) for which terminals can
draw Khmer.

```
Khmer · time 30s
23   41 wpm  96%

ខ្ញុំ រៀន ភាសា ខ្មែរ រាល់ ថ្ងៃ ដើម្បី អាច អាន សៀវភៅ …

› ស្ក▌
expected ស្ត្រី = ស ◌្ ត ◌្ រ ◌ី  (6 keys)
```

## Web app

```bash
khmertyper web
```

This starts a small local server (127.0.0.1:8000; `--port` changes it,
`--no-browser` skips opening a tab) and opens the app in your browser. It
reads the same word lists and quotes as the terminal version, including your
overrides in `~/.khmertyper/`.

It works like Monkeytype:

- **Typing:** the timer starts on your first key, and the header and toolbar
  fade out while you type. Move the mouse to bring them back.
- **Caret:** a smooth caret glides *through* a multi-key cluster as you type
  its parts (ស → ស្ → ស្ត → …), so every keystroke visibly moves it.
- **Colours:** correct clusters turn bright, wrong ones red, and a half-typed
  cluster gold. A finished word with a mistake gets a red underline.
- **Key hints:** get a cluster wrong and a hint appears under the words
  showing its keys, with the ones you've already typed ticked off and the
  next one highlighted.
- **Results:** WPM and accuracy, an interactive chart (net and raw speed
  with error marks; hover for per-second numbers), raw speed, cluster counts,
  consistency, CPM, clusters per minute, and your most-missed clusters with
  their keys. Beating a personal best sets off confetti.
- **History:** personal bests per mode and language, recent tests, a Khmer vs
  English comparison, and your all-time most-missed clusters.
- **Settings:** six themes (classic, angkor, mekong, monsoon, lotus, paper),
  synthesised typing sounds (click or soft; off by default), live speed,
  smooth caret, key hints, and ្ដ/្ត equivalence.
- **Storage:** settings and history are kept in the browser's `localStorage`,
  separately from the terminal app's history.

| Key | Action |
| --- | --- |
| `tab` | new test (and next test on the results screen) |
| `esc` | settings |
| `enter` | next test, on the results screen |
| `backspace` | delete one keystroke |
| `alt+backspace` / `ctrl+backspace` | delete the word |

Text comes in through the browser's input events rather than key codes, so
any Khmer keyboard layout works, including ones that type several code points
per key and the NiDA layout's ZWSP spacebar. Pasting is blocked.

The page loads the *Kantumruy Pro* and *Roboto Mono* fonts from Google Fonts,
and falls back to your system's Khmer font when you're offline.

## Terminal version: features

- **Modes:** time (15 / 30 / 60 / 120 s), words (10 / 25 / 50) and quote.
- **Cluster-aware checking.** A half-typed cluster shows as *in progress*
  (yellow underline), not as an error. Mistakes show in red, extra input in
  dim red, and there's a block cursor.
- **Canonical ordering.** Different valid typing orders count as correct:
  `ក្រា` = `កា្រ`, `ស្ត្រី` = `ស្រ្តី`, `េ`+`ី` = `ើ`, and so on.
- **Key hints.** When you get a cluster wrong, the app shows the keys that make
  it up.
- **Metrics:** WPM, raw WPM, CPM, clusters per minute, words per minute,
  accuracy, and your most-missed clusters.
- **Results screen** with an ASCII chart of speed over time. Every result is
  saved to a local JSON file, along with your personal bests.
- **Settings:** language (Khmer / English), mode, theme (all Textual themes),
  live speed display, hints, and ្ដ/្ត equivalence.
- **Font check screen** with sample text, a width-alignment test and
  terminal diagnostics.

## Install and run

You need Python 3.9 or newer.

```bash
pipx install .
```

Or use `uv tool install .`, or `pip install .` inside a virtualenv. Then run:

```bash
khmertyper
```

Useful flags (they're remembered as your new defaults):

```bash
khmertyper --mode words --words 25 --lang km --theme nord
```

```bash
khmertyper --font-check
```

### Keys

| Key | Action |
| --- | --- |
| type | start the test (the timer starts on the first key) |
| `space` | next word. Khmer layouts that put ZWSP on the spacebar (Windows NiDA) work too |
| `backspace` | delete one keystroke. At the start of a word it re-opens the previous word, but only if that word has a mistake |
| `ctrl+w` / `alt+backspace` | delete the current word |
| `tab` | new test |
| `ctrl+r` | repeat the same text |
| `esc` | settings |
| `f2` / `f3` | font check / history |
| `ctrl+q` | quit |

On the results screen: `enter`/`tab` starts the next test, `r` repeats the
text, `s` opens settings, `h` opens history.

## How Khmer is handled

### Clusters

Comparison happens per **cluster**: a base consonant (or independent vowel)
plus its subscripts, register shifter, vowels and signs. Clusters come from the
Unicode grapheme regex `\X` (the `regex` module). Recent Unicode versions keep
COENG stacks together, but older ones split `ក្រ` into `ក្` + `រ`, so any
cluster ending in COENG is re-joined with the next one. That gives the same
result on every version.

### Normalisation (canonical ordering)

Khmer marks have combining class 0, so Unicode NFC does *not* make different
typing orders equal. Before comparing, both the target and your input are
rewritten into one internal order, modelled on the Unicode Khmer syllable
structure and SIL's `khnormal`:

```
base · robat · subscripts (COENG RO last) · register shifter · vowels · signs
```

This step also:

- composes `េ + ី → ើ` and `េ + ា → ោ`, whichever order you type them in;
- treats COENG DA (`្ដ`) and COENG TA (`្ត`) as the same subscript, because
  they look identical in almost every font. You can turn this off in settings;
- ignores invisible characters: ZWSP, ZWJ/ZWNJ and the deprecated inherent
  vowels U+17B4/U+17B5.

The screen always shows the original text. The canonical form is only used for
comparison.

### "In progress" vs wrong

The cluster you're typing counts as in progress as long as everything typed so
far belongs to the target cluster, in any order. For example, `ស`, `ស្`, `ស្រ`
and `ស្រ្ត` are all valid ways to be partway through `ស្ត្រី`. A trailing
COENG is only allowed if the target still has a subscript left to type.

As soon as you start the next cluster, an unfinished one becomes wrong. The
test is word-aligned like Monkeytype, so a mistake never shifts the rest of the
text out of line.

## Metrics: what counts as a "word"

| Metric | Definition |
| --- | --- |
| **character** | one Unicode code point of the normalised target. On a Khmer keyboard that's one keystroke. |
| **cluster** | one visible Khmer letter block (see above). |
| **WPM** | correct characters ÷ 5, per minute |
| **raw WPM** | all keystrokes ÷ 5, per minute, right or wrong |
| **CPM / raw CPM** | the same, without the ÷ 5 |
| **clusters/min** | correctly typed clusters per minute |
| **words/min** | fully correct dictionary words per minute (the pre-segmented words) |
| **accuracy** | keystrokes that left their cluster correct or validly in progress ÷ all keystrokes. Backspace doesn't count, and a fixed mistake still counts as a mistake. |

"Correct characters" means characters in clusters that are correct at the end,
plus one for each space after a fully correct word.

**Why a Khmer "word" is 5 characters.** Khmer has no spaces and no standard
word length, so WPM needs a definition. khmertyper uses the same one as
English typing tests: 5 keystrokes = 1 word. It's a reasonable fit for Khmer
too. A typical word is about two syllables, and a syllable is 2–3 code points,
so 5 characters is roughly one real Khmer word. Using the same definition in
both languages is also what makes the English comparison meaningful: the
history screen shows your Khmer personal best as a percentage of your English
one. If you'd rather count real words, use words/min. For raw finger speed, use
CPM.

Speed is measured from your first keystroke to the end. Timed tests always
count exactly the chosen duration.

**Most missed clusters.** A cluster counts as missed each time a keystroke
turns it from right (or in progress) to wrong, and each time you skip it with
space. The all-time list is on the history screen (`f3`).

## Why Textual (and not curses)

Both libraries end up relying on the terminal to draw Khmer. The difference is
in how text reaches the terminal:

- **curses works cell by cell.** It uses the C library's `wcwidth()` to put
  each code point into a grid cell and attaches zero-width marks to the cell
  before them. When it optimises screen updates, it can redraw a single cell
  in the middle of a cluster. The terminal then gets a subscript consonant or
  vowel without its base and can't shape it, so you see dotted circles or
  detached marks until the next full repaint. On top of that, macOS ships an
  old ncurses with outdated width tables, and Windows has no curses at all
  unless you install `windows-curses`.
- **Textual redraws each changed widget line as one run of text.** Clusters
  always reach the terminal whole, so its shaper (DirectWrite, Core Text or
  HarfBuzz) sees complete syllables. Textual measures widths with its own
  up-to-date Unicode tables, and it runs on Windows, macOS and Linux with no
  extra packages. It also brings themes and a headless test harness, which the
  UI tests use.

One more detail: the typing area puts a blank row between lines of text. Khmer
vowels and subscripts stack above and below the base letter, and in a
fixed-height terminal cell they would otherwise collide with the next row.

No library can fix a terminal that doesn't shape Khmer. That's why the font
check screen exists.

## Terminal and font setup

Open the font check (`f2`, or `khmertyper --font-check`). Things to look for:

- subscripts sit **under** their base;
- `េ` draws to the **left** of the consonant;
- no dotted circles (◌) or empty boxes;
- the bars in the width check form a straight column. If they wobble, your
  terminal measures Khmer differently from Textual. Typing still works, but
  the cursor may look slightly off.

You also need a UTF-8 locale and a Khmer keyboard layout.

### Width calibration

Terminals don't agree on how many columns Khmer marks take. Unicode (and so
Rich and Textual) gives spacing vowels like `ា`, `េ` and `ះ` zero columns;
macOS Terminal gives each of them one. When the app and the terminal disagree,
rows end up longer on screen than planned, which pushes the cursor and the
scrollbar out of place.

So before the interface starts, khmertyper prints each Khmer mark after a
letter, asks the terminal where the cursor ended up (the standard cursor
position report, `ESC [6n`), and adjusts Rich's width table to match. This
takes a few milliseconds. The font check screen shows what was adjusted.
Turn it off with `--no-calibrate`.

Calibration only works when widths add up character by character. Some
terminals size whole clusters instead. **Ghostty** does this by default: its
grapheme-cluster mode (DEC mode 2027) caps any multi-character cluster at 2
columns. When a terminal reports that mode, khmertyper switches it off for the
session, measures again, and switches it back on when the app exits. Terminals
that size clusters with no way to turn it off (xterm.js-based ones) are left
alone.

### Terminals that can't display Khmer

Terminals built on **xterm.js** draw each character cell separately and don't
do the text shaping Khmer needs. This includes VS Code's integrated terminal,
Hyper, and the terminal panes built into some other editors and apps. Vowels such as `ា`
and `េ` come out detached, often on a dotted circle, and some words become
unreadable. The text itself is correct; only the drawing is broken, and
nothing inside khmertyper can fix it.

khmertyper detects these terminals (by `TERM_PROGRAM`) and shows a warning.
Open a standalone terminal instead:

```bash
open -a Terminal .
```

### Windows: use Windows Terminal

- Use **Windows Terminal**, not the old console window (`conhost`), which has
  poor complex-script support. Windows Terminal renders through DirectWrite
  and falls back automatically to the Khmer font that ships with Windows
  (*Khmer UI*), so Cascadia Mono plus fallback usually just works.
- If glyphs look wrong, set a Khmer-capable font in your profile under
  Settings → Profile → Appearance → Font face. Recent versions accept a
  comma-separated fallback list, e.g. `Cascadia Mono, Khmer UI`.
- To add the keyboard: Settings → Time & language → Language & region → Add a
  language → **Khmer**, then add the **Khmer (NIDA)** keyboard. Its spacebar
  types an invisible ZWSP; khmertyper accepts that as a word separator.
- Install Python from python.org or the Microsoft Store, then run
  `py -m pip install .` (or use pipx/uv).

### macOS

- **Ghostty** gives the best results we've seen: subscripts stack under their
  letter, `េ` sits on the left, and with the calibration above the layout
  lines up exactly. Some words have small gaps where a spacing vowel takes its
  own column, as in `ប្រាក់`.
- **Terminal.app** falls back to the system Khmer fonts (*Khmer Sangam MN*,
  *Khmer MN*) automatically. In testing, vowels, including `េ` on
  the left, are drawn correctly. Stacked subscripts (`ស្ត្រី`, `ប្រ`) are
  readable but gappy, and rows containing them drift a column or two to the
  right. That drift is how Terminal.app draws shaped text, not the width
  calibration below.
- **iTerm2:** if Khmer looks broken, try Settings → Profiles → Text →
  **Use ligatures**. This switches iTerm2 to Core Text shaping; it's slower
  but handles complex scripts better. You can also pick a Khmer font under
  "Use a different font for non-ASCII text".
- **WezTerm** and **kitty** shape with HarfBuzz and should also work well
  (config below), but they haven't been tested with khmertyper yet.
- To add the keyboard: System Settings → Keyboard → Text Input → Edit → **+**
  → Khmer.

### Linux

- Install a Khmer font:
  - Debian/Ubuntu: `sudo apt install fonts-khmeros` (or `fonts-noto-core`)
  - Fedora: `sudo dnf install google-noto-sans-khmer-fonts`
  - Arch: `sudo pacman -S noto-fonts`
- Choose a terminal that shapes complex scripts. **WezTerm**, **kitty** and
  **mlterm** do. VTE-based terminals (GNOME Terminal, Tilix, …) generally
  don't shape Khmer, so marks show up detached.
- Make sure `locale` reports a `UTF-8` charset.
- To add the keyboard: GNOME Settings → Keyboard → Input Sources → + → Khmer,
  or `setxkbmap -layout us,kh -option grp:alt_shift_toggle`.

### WezTerm and kitty font fallback

WezTerm (`~/.wezterm.lua`):

```lua
config.font = wezterm.font_with_fallback({ "JetBrains Mono", "Noto Sans Khmer" })
```

kitty (`~/.config/kitty/kitty.conf`):

```
symbol_map U+1780-U+17FF,U+19E0-U+19FF Noto Sans Khmer
```

## Word lists, quotes and your own text

Bundled files are in `src/khmertyper/data/`:

| File | Format |
| --- | --- |
| `km_words.txt`, `en_words.txt` | one word per line; `#` starts a comment |
| `km_quotes.txt`, `en_quotes.txt` | one quote per line, words separated by spaces, then a TAB and the source |

Khmer is written without spaces, so word lists and quotes are stored
**pre-segmented**, and the test shows the words separated by spaces. The Khmer
quotes are traditional proverbs (សុភាសិតខ្មែរ) plus some simple sample
sentences written for this app (marked ប្រយោគគំរូ).

To use your own lists, put files with the same names in `~/.khmertyper/`.
They replace the bundled ones.

To prepare unspaced Khmer text, there's a small dictionary-based segmenter.
It works on whole clusters, attaches punctuation to the word before it, and
keeps unknown runs together:

```bash
khmertyper segment raw_sentences.txt > ~/.khmertyper/km_quotes.txt
```

Always proof-read the output. The segmenter is only as good as its word list;
for serious work, use a statistical segmenter such as `khmer-nltk`.

## Data

Settings, history (the last 1000 tests, with per-second speed series) and
personal bests are stored in `~/.khmertyper/history.json`. Set
`KHMERTYPER_HOME` to use a different folder. If the file is ever unreadable,
it's moved aside as `history.corrupt-<time>.json` rather than overwritten.

## Development

```bash
uv sync
```

```bash
uv run pytest
```

| Path | What it does |
| --- | --- |
| `src/khmertyper/khmer.py` | clusters, normalisation, in-progress matching, key hints |
| `src/khmertyper/engine.py` | typing-test state machine (pure, driven with timestamps) |
| `src/khmertyper/metrics.py` | WPM/CPM/cluster/accuracy definitions and per-second series |
| `src/khmertyper/chart.py` | ASCII speed chart |
| `src/khmertyper/storage.py` | settings, history, personal bests |
| `src/khmertyper/termwidth.py` | startup width calibration (cursor position probe, Rich table patch) |
| `src/khmertyper/textsource.py`, `segment.py` | word lists, quotes, segmenter |
| `src/khmertyper/app.py` | Textual UI |
| `src/khmertyper/web/` | browser version: `js/khmer.js`, `engine.js`, `metrics.js` are ports of the Python modules; `app.js` is the UI |
| `src/khmertyper/webserver.py` | local server for `khmertyper web` |

The browser version re-implements the Khmer logic in JavaScript. To keep both
versions judging typing identically, `scripts/make_parity_fixture.py` records
the Python results for every bundled word and cluster plus a set of typing
sessions in `tests/fixtures/khmer_cases.json`, and `tests/js/parity.test.mjs`
checks the JavaScript gets the same answers. `uv run pytest` runs the JS tests
with Node (they're skipped if Node isn't installed) and fails if the fixture
is out of date. After changing `khmer.py` or `engine.py`, run:

```bash
uv run python scripts/make_parity_fixture.py
```

The tests cover:

- cluster splitting, including the old-Unicode fallback;
- equivalent typing orders and non-equivalent clusters;
- in-progress detection;
- engine behaviour: backspace rules, word skipping, ZWSP spacebar, timed-mode
  limits;
- every metric and the speed series;
- chart layout;
- storage and personal bests;
- well-formedness of every bundled word and quote;
- the segmenter;
- headless UI flows;
- the web server;
- Python/JavaScript parity.

Note on UI tests: `pilot.press()` drops the character for combining marks such
as COENG. The tests post `Key` events the way Textual's terminal parser does
instead.

## Known limitations

- The web app keeps its history in the browser, so results don't sync between
  browsers or with the terminal app.
- Terminals place text on a fixed grid, but Khmer glyph widths vary, so
  spacing inside words can look uneven in some terminals. That's a terminal
  limitation; the width check shows how your terminal behaves.
- The bundled word list and sample sentences are a starting point. A native
  speaker should review them before classroom use.
