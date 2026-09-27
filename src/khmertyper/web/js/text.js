// Word lists and quotes, shared with the terminal app (served from /data/).

import { clean } from "./khmer.js";

const cache = new Map();

async function fetchText(name) {
  if (!cache.has(name)) {
    cache.set(name, fetch(`data/${name}`).then((r) => {
      if (!r.ok) throw new Error(`could not load ${name}`);
      return r.text();
    }));
  }
  return cache.get(name);
}

const lines = (text) =>
  text.split(/\r?\n/).filter((l) => l.trim() && !l.trimStart().startsWith("#"));

export function parseWords(text) {
  return lines(text).map((l) => clean(l).trim()).filter(Boolean);
}

export function parseQuotes(text) {
  return lines(text)
    .map((l) => {
      const [body, source = ""] = l.split("\t");
      const words = clean(body).split(/\s+/).filter(Boolean);
      return { words, source: source.trim() };
    })
    .filter((q) => q.words.length);
}

export const loadWords = async (lang) => parseWords(await fetchText(`${lang}_words.txt`));
export const loadQuotes = async (lang) => parseQuotes(await fetchText(`${lang}_quotes.txt`));

export function randomWords(pool, count, random = Math.random) {
  const out = [];
  for (let i = 0; i < count; i++) {
    let w = pool[Math.floor(random() * pool.length)];
    while (out.length && pool.length > 1 && w === out[out.length - 1]) {
      w = pool[Math.floor(random() * pool.length)];
    }
    out.push(w);
  }
  return out;
}

/** Words (and a source, for quotes) for one test. */
export async function makeText(settings) {
  if (settings.mode === "quote") {
    const quotes = await loadQuotes(settings.lang);
    const q = quotes[Math.floor(Math.random() * quotes.length)];
    return { words: q.words, source: q.source };
  }
  const count = settings.mode === "words" ? settings.words : 100;
  return { words: randomWords(await loadWords(settings.lang), count), source: null };
}
