"""Command-line entry point: ``khmertyper`` or ``python -m khmertyper``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__


def _utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


def run_segment(path: Optional[str], dict_path: Optional[str]) -> int:
    from .segment import segment
    from .textsource import load_words, parse_words

    words = parse_words(Path(dict_path).read_text(encoding="utf-8")) if dict_path else load_words("km")
    text = Path(path).read_text(encoding="utf-8") if path and path != "-" else sys.stdin.read()
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            print(line)
            continue
        body, tab, source = line.partition("\t")
        print(" ".join(segment(body, words)) + (tab + source if tab else ""))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="khmertyper",
        description="A Monkeytype-style typing test for Khmer (and English), in the terminal.",
    )
    parser.add_argument("--version", action="version", version=f"khmertyper {__version__}")
    parser.add_argument("--lang", choices=["km", "en"], help="text language (remembered)")
    parser.add_argument("--mode", choices=["time", "words", "quote"], help="test mode (remembered)")
    parser.add_argument("--time", type=int, choices=[15, 30, 60, 120], help="seconds for time mode")
    parser.add_argument("--words", type=int, choices=[10, 25, 50], help="words for word mode")
    parser.add_argument("--theme", help="colour theme, e.g. nord, gruvbox, textual-light")
    parser.add_argument("--font-check", action="store_true", help="open the font check screen first")
    parser.add_argument("--no-calibrate", action="store_true",
                        help="don't measure how the terminal spaces Khmer at startup")
    sub = parser.add_subparsers(dest="command")
    seg = sub.add_parser("segment", help="split unspaced Khmer text into words for a quotes file")
    seg.add_argument("file", nargs="?", help="input file (default: stdin); TAB + source is kept")
    seg.add_argument("--dict", dest="dict_path", help="word list to segment with (default: bundled)")
    web = sub.add_parser("web", help="run the browser version locally")
    web.add_argument("--port", type=int, default=8000, help="port to listen on (default 8000)")
    web.add_argument("--host", default="127.0.0.1", help="address to listen on (default 127.0.0.1)")
    web.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
    args = parser.parse_args(argv)

    _utf8_stdio()
    if args.command == "segment":
        return run_segment(args.file, args.dict_path)
    if args.command == "web":
        from .webserver import serve

        return serve(args.host, args.port, open_browser=not args.no_browser)

    from .app import KhmerTyper, non_shaping_terminal
    from .storage import Store
    from .termwidth import Probe, calibrate

    store = Store()
    for name in ("lang", "mode", "time", "words", "theme"):
        value = getattr(args, name)
        if value is not None:
            setattr(store.settings, name, value)
    # Must happen before Textual takes over the terminal.
    if args.no_calibrate:
        probe = Probe(reason="skipped (--no-calibrate)")
    elif non_shaping_terminal():
        probe = Probe(reason="skipped: this terminal can't shape Khmer anyway")
    else:
        probe = calibrate()
    KhmerTyper(store, start_with_font_check=args.font_check, width_probe=probe).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
