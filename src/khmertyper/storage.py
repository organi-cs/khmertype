"""Settings, history and personal bests, kept in one local JSON file.

Location: ``$KHMERTYPER_HOME`` if set, otherwise ``~/.khmertyper``.
"""

from __future__ import annotations

import json
import os
import time
from collections import Counter
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HISTORY_LIMIT = 1000
SCHEMA_VERSION = 1


def data_dir() -> Path:
    env = os.environ.get("KHMERTYPER_HOME")
    return Path(env).expanduser() if env else Path.home() / ".khmertyper"


@dataclass
class Settings:
    lang: str = "km"  # "km" | "en"
    mode: str = "time"  # "time" | "words" | "quote"
    time: int = 30
    words: int = 25
    theme: str = "textual-dark"
    live_speed: bool = True
    hints: bool = True
    merge_da_ta: bool = True

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Settings":
        known = {f.name for f in fields(cls)}
        s = cls(**{k: v for k, v in raw.items() if k in known})
        if s.lang not in ("km", "en"):
            s.lang = "km"
        if s.mode not in ("time", "words", "quote"):
            s.mode = "time"
        if s.time not in (15, 30, 60, 120):
            s.time = 30
        if s.words not in (10, 25, 50):
            s.words = 25
        return s


def pb_key(lang: str, mode: str, value: Any) -> str:
    return f"{lang}:{mode}:{value}"


def mode_value(settings: Settings) -> Any:
    return {"time": settings.time, "words": settings.words}.get(settings.mode, "quote")


class Store:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or data_dir() / "history.json"
        self.settings = Settings()
        self.history: List[Dict[str, Any]] = []
        self.bests: Dict[str, Dict[str, Any]] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("not an object")
        except (OSError, ValueError):
            # Keep the broken file for the user rather than silently losing it.
            backup = self.path.with_name(f"{self.path.stem}.corrupt-{int(time.time())}.json")
            try:
                self.path.replace(backup)
            except OSError:
                pass
            return
        self.settings = Settings.from_dict(raw.get("settings") or {})
        self.history = list(raw.get("history") or [])
        self.bests = dict(raw.get("bests") or {})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": SCHEMA_VERSION,
            "settings": asdict(self.settings),
            "bests": self.bests,
            "history": self.history[-HISTORY_LIMIT:],
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)

    def add_result(self, result: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Record a finished test. Returns (is_new_pb, previous_pb)."""
        result = dict(result)
        result.setdefault("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S"))
        self.history.append(result)
        key = pb_key(result["lang"], result["mode"], result["mode_value"])
        previous = self.bests.get(key)
        is_pb = result.get("keystrokes", 0) > 0 and (
            previous is None
            or (result["wpm"], result["accuracy"]) > (previous["wpm"], previous["accuracy"])
        )
        if is_pb:
            self.bests[key] = {k: v for k, v in result.items() if k != "series"}
        self.save()
        return is_pb, previous

    def personal_best(self, lang: str, mode: str, value: Any) -> Optional[Dict[str, Any]]:
        return self.bests.get(pb_key(lang, mode, value))

    def most_missed(self, lang: str, limit: int = 15) -> List[Tuple[str, int]]:
        total: Counter = Counter()
        for r in self.history:
            if r.get("lang") == lang:
                for cluster, n in r.get("missed", []):
                    total[cluster] += n
        return total.most_common(limit)
