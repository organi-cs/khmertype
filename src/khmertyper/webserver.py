"""Serve the browser version locally: ``khmertyper web``.

The page lives in ``khmertyper/web``; word lists and quotes are served from
the same data files the terminal app uses (``/data/<lang>_<kind>.txt``),
including a user's overrides in ``~/.khmertyper``.
"""

from __future__ import annotations

import http.server
import re
import threading
import webbrowser
from functools import partial
from importlib import resources
from pathlib import Path

from .textsource import _read

DATA_NAME = re.compile(r"^(km|en)_(words|quotes)\.txt$")


def web_root() -> Path:
    return Path(str(resources.files("khmertyper").joinpath("web")))


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".css": "text/css",
        ".html": "text/html",
    }

    def do_GET(self) -> None:  # noqa: N802 (http.server naming)
        path = self.path.split("?", 1)[0]
        if path.startswith("/data/"):
            name = path[len("/data/"):]
            if not DATA_NAME.match(name):
                self.send_error(404)
                return
            body = _read(name).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, format: str, *args) -> None:  # keep the terminal quiet
        pass


def make_server(host: str = "127.0.0.1", port: int = 8000) -> http.server.ThreadingHTTPServer:
    handler = partial(Handler, directory=str(web_root()))
    return http.server.ThreadingHTTPServer((host, port), handler)


def serve(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True) -> int:
    try:
        server = make_server(host, port)
    except OSError as exc:
        print(f"could not listen on {host}:{port} ({exc.strerror}); try --port {port + 1}")
        return 1
    url = f"http://{host}:{server.server_address[1]}/"
    print(f"khmertype is running at {url}  (ctrl+c to stop)")
    if open_browser:
        threading.Timer(0.3, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
    return 0
