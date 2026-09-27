"""Write tests/fixtures/khmer_cases.json from the Python implementation.

The JavaScript port (src/khmertyper/web/js) is tested against this file, so
the terminal and browser versions judge typing identically. Re-run after
changing khmer.py or engine.py:

    uv run python scripts/make_parity_fixture.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from khmertyper.engine import TypingTest, compare_word  # noqa: E402
from khmertyper.khmer import (clusters_match, is_partial, keystroke_hint,  # noqa: E402
                              normalize_cluster, split_clusters)
from khmertyper.textsource import load_quotes, load_words  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "khmer_cases.json"

PAIRS = [
    ("ក្រា", "កា្រ"), ("ស្ត្រី", "ស្រ្តី"), ("ស្ត្រី", "ស្រី្ត"), ("កើ", "កេី"), ("កើ", "កីេ"),
    ("កោ", "កេា"), ("ញ៉ាំ", "ញាំ៉"), ("ញ៉ាំ", "ញ៉ំា"), ("ម៉្លេះ", "ម្ល៉េះ"), ("ស្ដាប់", "ស្តាប់"),
    ("ក", "ខ"), ("កា", "កិ"), ("ក្រ", "ក្ល"), ("កា", "កាា"), ("ក្ស", "ស្ក"), ("ឲ្យ", "ឱ្យ"),
    ("a", "a"), ("é", "é"),
]
PARTIALS = [
    (t, "ស្ត្រី") for t in ["ស", "ស្", "ស្ត", "ស្ត្", "ស្ត្រ", "ស្រ", "ស្រ្", "ស្រ្ត", "សី",
                           "ក", "សា", "ស្ក", "ស្ត្រ្", "្", "ី", "ស្ី"]
] + [("កេ", "កើ"), ("កេ", "កោ"), ("កា", "កើ"), ("ក្", "ក្រ"), ("ក្", "កា"), ("ក្រ្", "ក្រ")]
WORDS = [
    ("ក្រុង", "ក", False), ("ក្រុង", "ក្រ", False), ("ក្រុង", "កង", False), ("ក្រុង", "ក្រង", False),
    ("កាត", "កត", False), ("ក្រុង", "ក្រ", True), ("ក", "កខគ", False), ("cat", "cxt", False),
    ("ស្ត្រី", "ស្រ្តី", False), ("កើត", "កេីត", False), ("ខ្ញុំ", "", False), ("ខ្ញុំ", "", True),
]
# Keystroke sessions: "\b" is backspace, "\x17" is delete-word.
SESSIONS = [
    (["ខ្ញុំ", "ទៅ"], "ខ្ញុំ ទៅ"),
    (["កា", "ខ"], "កិ\bា ខ"),
    (["ក្រុង", "ខ"], "ក្រុ ខ"),
    (["ក", "ខ", "គ"], "ក \bង \b\bខ គ"),
    (["ស្ត្រី", "ខ"], "ស្ត\x17ស្រ្តី ខ"),
    (["ក", "ខ", "គ"], "ក​ខ គ"),
    (["hello", "world"], "helo wrld"),
]


def run_session(words, keys):
    t = TypingTest(list(words))
    now = 100.0
    for ch in keys:
        now += 0.25
        if ch == "\b":
            t.backspace(now)
        elif ch == "\x17":
            t.delete_word(now)
        else:
            t.type(ch, now)
    return {
        "typed": t.typed,
        "finished": t.finished,
        "net": t.net_chars(),
        "correct_keys": [e.correct for e in t.events if e.kind != "backspace"],
        "missed": dict(sorted(t.missed.items())),
    }


def build() -> dict:
    corpus = load_words("km") + [w for q in load_quotes("km") for w in q.words]
    clusters = sorted({c for w in corpus for c in split_clusters(w)})
    return {
        "split": {w: split_clusters(w) for w in sorted(set(corpus))},
        "normalize": {c: normalize_cluster(c) for c in clusters + [a for p in PAIRS for a in p]},
        "normalize_no_merge": {c: normalize_cluster(c, False) for c in ["ស្ដា", "ស្តា", "ដ្ដ"]},
        "match": [[a, b, clusters_match(a, b)] for a, b in PAIRS],
        "partial": [[t, g, is_partial(t, g)] for t, g in PARTIALS],
        "hint": {c: keystroke_hint(c) for c in ["ស្ត្រី", "ញ៉ាំ", "ក"]},
        "compare": [
            [target, typed, committed,
             [s.value for s in compare_word(split_clusters(target),
                                            [normalize_cluster(c) for c in split_clusters(target)],
                                            typed, committed=committed).statuses]]
            for target, typed, committed in WORDS
        ],
        "sessions": [[words, keys, run_session(words, keys)] for words, keys in SESSIONS],
    }


if __name__ == "__main__":
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(build(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {FIXTURE}")
