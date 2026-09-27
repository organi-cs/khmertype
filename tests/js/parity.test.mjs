// The browser port must judge typing exactly like the Python version.
// Cases come from tests/fixtures/khmer_cases.json (scripts/make_parity_fixture.py).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { clustersMatch, isPartial, keystrokeHint, normalizeCluster, splitClusters } from "../../src/khmertyper/web/js/khmer.js";
import { TypingTest, compareWord } from "../../src/khmertyper/web/js/engine.js";
import { compute, consistency } from "../../src/khmertyper/web/js/metrics.js";

const cases = JSON.parse(readFileSync(new URL("../fixtures/khmer_cases.json", import.meta.url), "utf8"));

test("cluster splitting matches Python for every bundled word", () => {
  for (const [word, clusters] of Object.entries(cases.split)) assert.deepEqual(splitClusters(word), clusters, word);
});

test("normalisation matches Python", () => {
  for (const [c, norm] of Object.entries(cases.normalize)) assert.equal(normalizeCluster(c), norm, c);
  for (const [c, norm] of Object.entries(cases.normalize_no_merge)) assert.equal(normalizeCluster(c, false), norm, c);
});

test("cluster matching and in-progress detection match Python", () => {
  for (const [a, b, expected] of cases.match) assert.equal(clustersMatch(a, b), expected, `${a} vs ${b}`);
  for (const [t, g, expected] of cases.partial) assert.equal(isPartial(t, g), expected, `${t} -> ${g}`);
  for (const [c, keys] of Object.entries(cases.hint)) assert.deepEqual(keystrokeHint(c), keys);
});

test("word comparison matches Python", () => {
  for (const [target, typed, committed, statuses] of cases.compare) {
    const tc = splitClusters(target);
    const view = compareWord(tc, tc.map((c) => normalizeCluster(c)), typed, { committed });
    assert.deepEqual(view.statuses, statuses, `${target} / ${typed} / ${committed}`);
  }
});

test("whole typing sessions match Python", () => {
  for (const [words, keys, expected] of cases.sessions) {
    const t = new TypingTest(words);
    let now = 100;
    for (const ch of keys) {
      now += 0.25;
      if (ch === "\b") t.backspace(now);
      else if (ch === "\x17") t.deleteWord(now);
      else t.type(ch, now);
    }
    const missed = Object.fromEntries([...t.missed.entries()].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)));
    assert.deepEqual({
      typed: t.typed,
      finished: t.finished,
      net: t.netChars(),
      correct_keys: t.events.filter((e) => e.kind !== "backspace").map((e) => e.correct),
      missed,
    }, expected, JSON.stringify(keys));
  }
});

test("metrics: perfect run, timed limit and consistency", () => {
  const t = new TypingTest(["hello", "world"]);
  let now = 100;
  for (const ch of "hello world") { t.type(ch, now); now += 0.45; }
  const s = compute(t, now);
  assert.equal(s.keystrokes, 11);
  assert.equal(s.accuracy, 100);
  assert.equal(s.correctChars, 11);
  assert.ok(Math.abs(s.wpm - 11 / 5 / (4.5 / 60)) < 0.1);
  assert.equal(s.series.wpm.length, 5);

  const timed = new TypingTest(["abc", "def"], { timeLimit: 10 });
  now = 100;
  for (const ch of "abc de") { timed.type(ch, now); now += 1; }
  assert.equal(compute(timed, 500).duration, 10);

  assert.equal(consistency([50, 50, 50]), 100);
  assert.ok(consistency([10, 90, 10, 90]) < 50);
});

test("time limit is reached despite float rounding", () => {
  const t = new TypingTest(["a"], { timeLimit: 30 });
  const start = 25.276;
  assert.ok(start + 30 - start < 30); // the rounding this guards against
  t.type("a", start);
  assert.equal(t.elapsed(start + 30), 30);
  assert.equal(t.elapsed(start + 99), 30);
});
