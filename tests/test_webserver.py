"""The local server behind ``khmertyper web``."""

import threading
import urllib.error
import urllib.request

import pytest

from khmertyper.webserver import make_server, web_root


@pytest.fixture
def base_url():
    server = make_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read().decode("utf-8")


def test_serves_the_page_and_modules(base_url):
    status, ctype, body = get(base_url + "/")
    assert status == 200 and "text/html" in ctype and 'src="js/app.js"' in body
    status, ctype, _ = get(base_url + "/js/app.js")
    assert status == 200 and "javascript" in ctype  # ES modules need a JS type


def test_every_asset_the_page_references_exists():
    root = web_root()
    for rel in ["index.html", "style.css", "js/app.js", "js/khmer.js", "js/engine.js",
                "js/metrics.js", "js/chart.js", "js/text.js", "js/storage.js", "js/sound.js"]:
        assert (root / rel).is_file(), rel


def test_serves_shared_word_lists(base_url):
    status, ctype, body = get(base_url + "/data/km_words.txt")
    assert status == 200 and "charset=utf-8" in ctype and "ខ្ញុំ" in body
    assert "\t" in get(base_url + "/data/en_quotes.txt")[2]


def test_user_word_list_override_is_used(base_url, isolated_home):
    isolated_home.mkdir(parents=True)
    (isolated_home / "km_words.txt").write_text("ស្រមោច\n", encoding="utf-8")
    assert get(base_url + "/data/km_words.txt")[2] == "ស្រមោច\n"


@pytest.mark.parametrize("path", ["/data/secret.txt", "/data/../pyproject.toml", "/data/km_words.txt.bak"])
def test_only_known_data_files_are_served(base_url, path):
    with pytest.raises(urllib.error.HTTPError) as err:
        get(base_url + path)
    assert err.value.code == 404
