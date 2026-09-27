"""Build the static site for GitHub Pages.

    python scripts/build_site.py _site

Copies the browser app (src/khmertyper/web) and the shared word lists and
quotes (src/khmertyper/data -> data/) into one folder that any static host
can serve, at the domain root or under a sub-path such as /khmertype/.
Standard library only, so CI needs no dependencies to run it.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "src" / "khmertyper" / "web"
DATA = ROOT / "src" / "khmertyper" / "data"
DATA_FILES = [f"{lang}_{kind}.txt" for lang in ("km", "en") for kind in ("words", "quotes")]


def build(out: Path) -> Path:
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(WEB, out, ignore=shutil.ignore_patterns(".DS_Store", "__pycache__"))
    (out / "data").mkdir()
    for name in DATA_FILES:
        shutil.copy2(DATA / name, out / "data" / name)
    (out / ".nojekyll").write_text("")  # serve files as-is, no Jekyll processing
    check(out)
    return out


def check(out: Path) -> None:
    """Fail the build if the page points at something that isn't there, or
    at an absolute path (which would break under a /repo-name/ sub-path)."""
    html = (out / "index.html").read_text(encoding="utf-8")
    refs = re.findall(r'(?:src|href)="([^"#:]+)"', html)
    for ref in refs:
        if ref.startswith("/"):
            raise SystemExit(f"index.html uses an absolute path: {ref}")
        if not (out / ref).is_file():
            raise SystemExit(f"index.html references a missing file: {ref}")
    for js in (out / "js").glob("*.js"):
        for mod in re.findall(r'from "(\.[^"]+)"', js.read_text(encoding="utf-8")):
            if not (js.parent / mod).resolve().is_file():
                raise SystemExit(f"{js.name} imports a missing module: {mod}")


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "_site")
    build(target)
    files = sorted(p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file())
    print(f"built {target} ({len(files)} files)")
