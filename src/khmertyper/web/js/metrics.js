// Speed and accuracy metrics (port of src/khmertyper/metrics.py).
// WPM = correct characters / 5 per minute; see the README for why a Khmer
// "word" is 5 characters.

import { Status } from "./engine.js";

export const CHARS_PER_WORD = 5;

export const perMinute = (amount, seconds) => (seconds > 0 ? (amount * 60) / seconds : 0);
const round1 = (x) => Math.round(x * 10) / 10;

export function speedSeries(test, duration) {
  const seconds = Math.max(1, Math.ceil(duration - 1e-9));
  const series = { wpm: [], raw: [], errors: [] };
  let net = 0;
  let j = 0;
  const events = test.events;
  for (let s = 1; s <= seconds; s++) {
    let keys = 0;
    let errors = 0;
    while (j < events.length && events[j].t <= s) {
      const e = events[j];
      net = e.net;
      if (e.kind !== "backspace") {
        keys += 1;
        if (!e.correct) errors += 1;
      }
      j++;
    }
    const span = duration > 0 ? Math.min(s, duration) : s;
    const window = span - (s - 1);
    series.wpm.push(round1(perMinute(net / CHARS_PER_WORD, span)));
    series.raw.push(window > 0 ? round1(perMinute(keys / CHARS_PER_WORD, window)) : 0);
    series.errors.push(errors);
  }
  return series;
}

/** Monkeytype-style consistency: 100 when raw speed is perfectly steady. */
export function consistency(raw) {
  if (raw.length < 2) return 100;
  const mean = raw.reduce((a, b) => a + b, 0) / raw.length;
  if (mean === 0) return 0;
  const sd = Math.sqrt(raw.reduce((a, b) => a + (b - mean) ** 2, 0) / raw.length);
  const cov = sd / mean;
  return round1(100 * (1 - Math.tanh(cov + cov ** 3 / 3 + cov ** 5 / 5)));
}

export function compute(test, now, topMissed = 10) {
  const duration = test.elapsed(now);
  const keys = test.events.filter((e) => e.kind !== "backspace");
  const keystrokes = keys.length;
  const correctKeys = keys.filter((e) => e.correct).length;

  const counts = { correct: 0, wrong: 0, pending: 0, missed: 0, extra: 0 };
  let correctClusters = 0;
  let correctWords = 0;
  for (let i = 0; i <= test.index; i++) {
    const v = test.view(i);
    for (const s of v.statuses) if (s !== Status.UNTYPED) counts[s] += 1;
    counts.extra += v.extras.length;
    correctClusters += v.statuses.filter((s) => s === Status.CORRECT).length;
    if (v.correct) correctWords += 1;
  }

  const net = test.netChars();
  const series = speedSeries(test, duration);
  const missed = [...test.missed.entries()]
    .filter(([c]) => c.trim())
    .sort((a, b) => b[1] - a[1])
    .slice(0, topMissed);
  return {
    duration: Math.round(duration * 100) / 100,
    wpm: round1(perMinute(net / CHARS_PER_WORD, duration)),
    rawWpm: round1(perMinute(keystrokes / CHARS_PER_WORD, duration)),
    cpm: round1(perMinute(net, duration)),
    rawCpm: round1(perMinute(keystrokes, duration)),
    clustersPm: round1(perMinute(correctClusters, duration)),
    wordsPm: round1(perMinute(correctWords, duration)),
    accuracy: keystrokes ? round1((100 * correctKeys) / keystrokes) : 0,
    consistency: consistency(series.raw),
    keystrokes,
    errors: keystrokes - correctKeys,
    correctChars: net,
    clusterCounts: counts,
    missed,
    series,
  };
}
