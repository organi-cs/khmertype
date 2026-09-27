// Khmer text handling: clusters, canonical ordering and partial matching.
// A line-for-line port of src/khmertyper/khmer.py; tests/js checks the two
// agree on a shared set of cases (tests/fixtures/khmer_cases.json).

export const COENG = "្";
const RO = "រ";
const DA = "ដ";
const TA = "ត";
const ROBAT = "៌";
const SHIFTERS = new Set(["៉", "៊"]);
const E_VOWEL = "េ";

// ZWSP marks Khmer word boundaries invisibly (and is what the NiDA spacebar
// types); U+17B4/U+17B5 are invisible, deprecated inherent vowels.
const IGNORABLE = new Set(["​", "‌", "‍", "⁠", "﻿", "឴", "឵"]);
export const WORD_SEPARATORS = new Set([" ", "​", " ", "　"]);

const COMPOSITES = { "ើ": E_VOWEL + "ី", "ោ": E_VOWEL + "ា" };
const COMPOSE = Object.entries(COMPOSITES).map(([composed, parts]) => [[...parts].sort(), composed]);

export const DOTTED_CIRCLE = "◌";

const segmenter = new Intl.Segmenter("km", { granularity: "grapheme" });

const cp = (ch) => ch.codePointAt(0);
export const isConsonant = (ch) => cp(ch) >= 0x1780 && cp(ch) <= 0x17a2;
export const isIndependentVowel = (ch) => cp(ch) >= 0x17a3 && cp(ch) <= 0x17b3;
export const isKhmerBase = (ch) => isConsonant(ch) || isIndependentVowel(ch) || ch === "ៜ";
export const isDependentVowel = (ch) => cp(ch) >= 0x17b6 && cp(ch) <= 0x17c5;
export const isKhmer = (ch) => (cp(ch) >= 0x1780 && cp(ch) <= 0x17ff) || (cp(ch) >= 0x19e0 && cp(ch) <= 0x19ff);
export const isMark = (ch) => /\p{M}/u.test(ch);

export function clean(text) {
  let out = "";
  for (const ch of text.normalize("NFC")) if (!IGNORABLE.has(ch)) out += ch;
  return out;
}

export function splitClusters(text) {
  const out = [];
  for (const { segment } of segmenter.segment(text)) {
    // Older Unicode data splits after COENG (ក្ + រ); re-join those.
    if (out.length && out[out.length - 1].endsWith(COENG) && !/^\s/u.test(segment)) {
      out[out.length - 1] += segment;
    } else {
      out.push(segment);
    }
  }
  return out;
}

// ---- tiny multiset helpers -------------------------------------------------

function add(counter, key, n = 1) {
  counter.set(key, (counter.get(key) || 0) + n);
}
function minus(a, b) {
  // Like Python's Counter subtraction: keep positive counts only.
  const out = new Map();
  for (const [k, v] of a) {
    const left = v - (b.get(k) || 0);
    if (left > 0) out.set(k, left);
  }
  return out;
}

function canonicalSubscript(ch, mergeDaTa) {
  return mergeDaTa && ch === DA ? COENG + TA : COENG + ch;
}

/** Base letter plus a multiset of units that may be typed in any order. */
export function clusterUnits(cluster, mergeDaTa = true) {
  const s = [...clean(cluster)];
  if (!s.length) return { base: "", units: new Map(), trailingCoeng: false };
  const [base, ...rest] = s;
  const units = new Map();
  let trailing = false;
  for (let i = 0; i < rest.length; i++) {
    const ch = rest[i];
    if (ch === COENG) {
      if (i + 1 < rest.length && !isMark(rest[i + 1])) {
        add(units, canonicalSubscript(rest[i + 1], mergeDaTa));
        i++;
        continue;
      }
      if (i === rest.length - 1) trailing = true;
      else add(units, COENG);
    } else if (COMPOSITES[ch]) {
      for (const part of COMPOSITES[ch]) add(units, part);
    } else {
      add(units, ch);
    }
  }
  return { base, units, trailingCoeng: trailing };
}

function orderKey(unit) {
  const first = unit[0];
  if (first === ROBAT) return 1;
  if (first === COENG) return unit.slice(1) === RO ? 3 : 2;
  if (SHIFTERS.has(first)) return 4;
  if (isDependentVowel(first)) return 5;
  if (isKhmer(first)) return 6;
  return 7;
}

function stableUnits(chars, units, mergeDaTa) {
  const remaining = new Map(units);
  const seen = [];
  const rest = chars.slice(1);
  for (let i = 0; i < rest.length; i++) {
    if (rest[i] === COENG && i + 1 < rest.length && !isMark(rest[i + 1])) {
      const unit = canonicalSubscript(rest[i + 1], mergeDaTa);
      if ((remaining.get(unit) || 0) > 0) {
        seen.push(unit);
        remaining.set(unit, remaining.get(unit) - 1);
      }
    }
  }
  const others = [];
  for (const [k, v] of remaining) for (let i = 0; i < v; i++) others.push(k);
  others.sort();
  return seen.concat(others);
}

/** Canonical form of one cluster (used only for comparison). */
export function normalizeCluster(cluster, mergeDaTa = true) {
  const s = clean(cluster);
  const chars = [...s];
  if (!chars.length || !isKhmerBase(chars[0])) return s;
  const { base, units, trailingCoeng } = clusterUnits(s, mergeDaTa);
  for (const [parts, composed] of COMPOSE) {
    while (parts.every((p) => (units.get(p) || 0) > 0)) {
      for (const p of parts) units.set(p, units.get(p) - 1);
      add(units, composed);
    }
  }
  for (const [k, v] of [...units]) if (v <= 0) units.delete(k);
  const ordered = stableUnits(chars, units, mergeDaTa);
  ordered.sort((a, b) => orderKey(a) - orderKey(b) || (a[0] === COENG ? 0 : cp(a) - cp(b)));
  return base + ordered.join("") + (trailingCoeng ? COENG : "");
}

export function normalizeText(text, mergeDaTa = true) {
  return splitClusters(clean(text)).map((c) => normalizeCluster(c, mergeDaTa)).join("");
}

export function clustersMatch(typed, target, mergeDaTa = true) {
  return normalizeCluster(typed, mergeDaTa) === normalizeCluster(target, mergeDaTa);
}

/** Can `typed` still become `target` by typing more keys? */
export function isPartial(typed, target, mergeDaTa = true) {
  const t = clusterUnits(typed, mergeDaTa);
  const g = clusterUnits(target, mergeDaTa);
  if (!t.base || t.base !== g.base) return false;
  if (minus(t.units, g.units).size) return false;
  if (t.trailingCoeng) {
    for (const unit of minus(g.units, t.units).keys()) if (unit.startsWith(COENG)) return true;
    return false;
  }
  return true;
}

/** The keys that make up a cluster, marks shown on a dotted circle. */
export function keystrokeHint(cluster) {
  return [...clean(cluster)].map((ch) => (isMark(ch) ? DOTTED_CIRCLE + ch : ch));
}
