// The typing-test state machine (port of src/khmertyper/engine.py).
// Word-aligned like Monkeytype: what you type before a space is compared
// with the target word cluster by cluster; space moves to the next word.

import { WORD_SEPARATORS, clean, isPartial, normalizeCluster, splitClusters } from "./khmer.js";

export const Status = Object.freeze({
  UNTYPED: "untyped",
  CORRECT: "correct",
  WRONG: "wrong",
  PENDING: "pending", // a valid, unfinished cluster (the one being typed)
  MISSED: "missed", // skipped by pressing space early
});

export function compareWord(target, targetNorm, typedText, { committed, mergeDaTa = true }) {
  const typed = splitClusters(clean(typedText));
  const statuses = target.map((goal, i) => {
    if (i >= typed.length) return committed ? Status.MISSED : Status.UNTYPED;
    if (normalizeCluster(typed[i], mergeDaTa) === targetNorm[i]) return Status.CORRECT;
    if (!committed && i === typed.length - 1 && isPartial(typed[i], goal, mergeDaTa)) return Status.PENDING;
    return Status.WRONG;
  });
  const extras = typed.slice(target.length);
  const correct = !extras.length && statuses.every((s) => s === Status.CORRECT);
  // The target cluster the caret sits on (may equal target.length).
  let cursor = Math.min(typed.length, target.length);
  if (typed.length && typed.length <= target.length && statuses[typed.length - 1] !== Status.CORRECT) {
    cursor = typed.length - 1;
  }
  return { target, statuses, typed, extras, correct, cursor };
}

export class TypingTest {
  constructor(words, { timeLimit = null, mergeDaTa = true } = {}) {
    this.words = words.map(clean).filter((w) => w.trim());
    if (!this.words.length) throw new Error("a typing test needs at least one word");
    this.timeLimit = timeLimit;
    this.mergeDaTa = mergeDaTa;
    this.target = [];
    this.targetNorm = [];
    for (const w of this.words) this._addTarget(w);
    this.typed = [""];
    this.startedAt = null;
    this.endedAt = null;
    this.events = []; // {t, kind: "char"|"space"|"backspace", correct, net}
    this.missed = new Map();
    this.lastCommitted = false;
    this._wrong = new Set();
    this._extras = 0;
    this._committed = new Map(); // word index -> [net chars, correct]
    this._views = new Map();
  }

  _addTarget(word) {
    const clusters = splitClusters(word);
    this.target.push(clusters);
    this.targetNorm.push(clusters.map((c) => normalizeCluster(c, this.mergeDaTa)));
  }

  get index() { return this.typed.length - 1; }
  get started() { return this.startedAt !== null; }
  get finished() { return this.endedAt !== null; }

  elapsed(now) {
    if (this.startedAt === null) return 0;
    const end = this.endedAt ?? now;
    // Exactly the limit: (start + limit) - start can come out a hair short in
    // floating point, and then a timed test never ends.
    if (this.timeLimit !== null && end >= this.startedAt + this.timeLimit) return this.timeLimit;
    return Math.max(0, end - this.startedAt);
  }

  view(i) {
    const committed = i < this.index || (i === this.index && this.lastCommitted);
    const typed = i <= this.index ? this.typed[i] : "";
    const key = `${i}\u0000${committed}\u0000${typed}`;
    let v = this._views.get(key);
    if (!v) {
      if (this._views.size > 4096) this._views.clear();
      v = compareWord(this.target[i], this.targetNorm[i], typed, { committed, mergeDaTa: this.mergeDaTa });
      this._views.set(key, v);
    }
    return v;
  }

  current() { return this.view(this.index); }

  extend(words) {
    for (const w of words.map(clean)) {
      if (!w.trim()) continue;
      this.words.push(w);
      this._addTarget(w);
    }
  }

  /** Feed one typed character (a single code point). `now` is in seconds. */
  type(ch, now) {
    if (this.timeLimit !== null && this.startedAt !== null && now >= this.startedAt + this.timeLimit) {
      this.finish(this.startedAt + this.timeLimit);
    }
    if (this.finished) return;
    if (WORD_SEPARATORS.has(ch)) return this._space(now);
    if (clean(ch) === "") return; // ZWJ/ZWNJ etc. never count
    this._start(now);
    this.typed[this.index] += ch;
    const view = this.current();
    const newWrong = this._trackErrors(view);
    const newExtra = view.extras.length > this._extras;
    this._extras = view.extras.length;
    const last = view.typed.length - 1;
    const landedOk = last >= 0 && last < view.target.length &&
      (view.statuses[last] === Status.CORRECT || view.statuses[last] === Status.PENDING);
    this._record(now, "char", landedOk && !newWrong && !newExtra);
    if (this.index === this.words.length - 1 && view.correct && this.timeLimit === null) this.endedAt = now;
  }

  _space(now) {
    if (!this.typed[this.index]) return; // space on an empty word does nothing
    this._start(now);
    const i = this.index;
    this.lastCommitted = true;
    const view = this.view(i);
    this._trackErrors(view);
    view.target.forEach((goal, k) => {
      if (view.statuses[k] === Status.MISSED) this.missed.set(goal, (this.missed.get(goal) || 0) + 1);
    });
    this._committed.set(i, [this._wordNet(i, view), view.correct]);
    this._record(now, "space", view.correct);
    if (i === this.words.length - 1) {
      this.endedAt = now;
      return;
    }
    this.lastCommitted = false;
    this.typed.push("");
    this._wrong = new Set();
    this._extras = 0;
  }

  /** Delete one code point; at a word start, re-open the previous word
   *  (only if it has a mistake, as in Monkeytype). */
  backspace(now) {
    if (this.finished || !this.started) return;
    const cur = this.typed[this.index];
    if (cur) this.typed[this.index] = [...cur].slice(0, -1).join("");
    else if (!this._reopenPrevious()) return;
    this._resync();
    this._record(now, "backspace", true);
  }

  deleteWord(now) {
    if (this.finished || !this.started) return;
    if (!this.typed[this.index] && !this._reopenPrevious()) return;
    this.typed[this.index] = "";
    this._resync();
    this._record(now, "backspace", true);
  }

  finish(now) {
    if (this.endedAt === null) this.endedAt = now;
  }

  _start(now) {
    if (this.startedAt === null) this.startedAt = now;
  }

  _reopenPrevious() {
    if (this.index === 0 || this._committed.get(this.index - 1)?.[1]) return false;
    this.typed.pop();
    this._committed.delete(this.index);
    return true;
  }

  _resync() {
    const view = this.current();
    this._wrong = new Set(view.statuses.flatMap((s, i) => (s === Status.WRONG ? [i] : [])));
    this._extras = view.extras.length;
  }

  /** Clusters that just turned wrong count as a miss of that cluster. */
  _trackErrors(view) {
    const nowWrong = new Set(view.statuses.flatMap((s, i) => (s === Status.WRONG ? [i] : [])));
    let fresh = false;
    for (const i of nowWrong) {
      if (!this._wrong.has(i)) {
        fresh = true;
        this.missed.set(view.target[i], (this.missed.get(view.target[i]) || 0) + 1);
      }
    }
    this._wrong = nowWrong;
    return fresh;
  }

  _wordNet(i, view) {
    let n = 0;
    view.statuses.forEach((s, k) => { if (s === Status.CORRECT) n += [...this.targetNorm[i][k]].length; });
    return n;
  }

  /** Correct characters, plus one per space after a fully correct word. */
  netChars() {
    let total = 0;
    for (const [i, [net, correct]] of this._committed) {
      total += net + (correct && i < this.words.length - 1 ? 1 : 0);
    }
    if (!this._committed.has(this.index)) total += this._wordNet(this.index, this.current());
    return total;
  }

  _record(now, kind, correct) {
    this.events.push({ t: now - this.startedAt, kind, correct, net: this.netChars() });
  }
}
