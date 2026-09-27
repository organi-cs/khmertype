// Settings, history and personal bests in localStorage (this browser only).
// Every access is guarded: storage can be missing or full.

const KEY = "khmertype.v1";
const HISTORY_LIMIT = 500;

export const DEFAULTS = {
  lang: "km",
  mode: "time",
  time: 30,
  words: 25,
  theme: "classic",
  sound: "off",
  liveSpeed: true,
  hints: true,
  mergeDaTa: true,
  smoothCaret: true,
};

const CHOICES = {
  lang: ["km", "en"],
  mode: ["time", "words", "quote"],
  time: [15, 30, 60, 120],
  words: [10, 25, 50],
  sound: ["off", "click", "soft"],
};

function read() {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || "{}");
    return raw && typeof raw === "object" ? raw : {};
  } catch {
    return {};
  }
}

function write(data) {
  try {
    localStorage.setItem(KEY, JSON.stringify(data));
  } catch {
    /* storage unavailable or full: keep working in memory */
  }
}

let state = read();

export function loadSettings() {
  const s = { ...DEFAULTS, ...(state.settings || {}) };
  for (const [k, allowed] of Object.entries(CHOICES)) if (!allowed.includes(s[k])) s[k] = DEFAULTS[k];
  return s;
}

export function saveSettings(settings) {
  state.settings = settings;
  write(state);
}

export const pbKey = (r) => `${r.lang}:${r.mode}:${r.modeValue}`;
export const history = () => state.history || [];
export const bests = () => state.bests || {};

/** Save a finished test. Returns the previous best for its mode (or null)
 *  and whether this result beat it. */
export function addResult(result) {
  state.history = [...history(), result].slice(-HISTORY_LIMIT);
  const key = pbKey(result);
  const previous = bests()[key] || null;
  const isPb = result.keystrokes > 0 &&
    (!previous || result.wpm > previous.wpm || (result.wpm === previous.wpm && result.accuracy > previous.accuracy));
  if (isPb) {
    const { series, ...small } = result;
    state.bests = { ...bests(), [key]: small };
  }
  write(state);
  return { isPb, previous };
}

export function mostMissed(lang, limit = 15) {
  const total = new Map();
  for (const r of history()) {
    if (r.lang !== lang) continue;
    for (const [cluster, n] of r.missed || []) total.set(cluster, (total.get(cluster) || 0) + n);
  }
  return [...total.entries()].sort((a, b) => b[1] - a[1]).slice(0, limit);
}

export function clearHistory() {
  state = { settings: state.settings };
  write(state);
}
