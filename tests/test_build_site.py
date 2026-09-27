"""The static build that GitHub Pages serves."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_site  # noqa: E402

sys.path.pop(0)


def test_build_contains_page_modules_and_data(tmp_path):
    out = build_site.build(tmp_path / "_site")
    for rel in ["index.html", "style.css", "js/app.js", ".nojekyll", *(f"data/{n}" for n in build_site.DATA_FILES)]:
        assert (out / rel).is_file(), rel
    assert "ខ្ញុំ" in (out / "data" / "km_words.txt").read_text(encoding="utf-8")


def test_build_rejects_absolute_paths(tmp_path, monkeypatch):
    web = tmp_path / "web"
    (web / "js").mkdir(parents=True)
    (web / "index.html").write_text('<script src="/js/app.js"></script>', encoding="utf-8")
    (web / "js" / "app.js").write_text("", encoding="utf-8")
    monkeypatch.setattr(build_site, "WEB", web)
    try:
        build_site.build(tmp_path / "_site")
    except SystemExit as exc:
        assert "absolute path" in str(exc)
    else:
        raise AssertionError("absolute path was accepted")


def test_page_fetches_data_relative_to_itself():
    # Must be relative so the site works under /khmertype/ on GitHub Pages.
    text = (ROOT / "src/khmertyper/web/js/text.js").read_text(encoding="utf-8")
    assert "fetch(`data/${name}`)" in text
