import { TypingTest, Status } from "./engine.js";
import { clean, keystrokeHint } from "./khmer.js";
import { compute, perMinute, CHARS_PER_WORD } from "./metrics.js";
import { drawChart } from "./chart.js";
import { loadWords, makeText, randomWords } from "./text.js";
import * as store from "./storage.js";
import { play } from "./sound.js";

const $ = (sel) => document.querySelector(sel);
const now = () => performance.now() / 1000;
const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const LANG_NAME = { km: "ខ្មែរ", en: "english" };
// Swatch colours: background, main, text (keep in sync with style.css).
const THEMES = {
  classic: ["#323437", "#e2b714", "#d1d0c5"],
  angkor: ["#1d1914", "#d9a441", "#ecdfc8"],
  mekong: ["#0e1c22", "#4fd1c5", "#d3ebe7"],
  monsoon: ["#2e3440", "#88c0d0", "#eceff4"],
  lotus: ["#f5efe9", "#c2477f", "#3a2e34"],
  paper: ["#eeeeee", "#444444", "#b2b2b2"],
};

let settings = store.loadSettings();
let test = null;
let source = null;
let wordPool = [];
let wordEls = [];
let caret = null;
let inner = null;
let lastKeyAt = 0;
let generation = 0;
let shownResult = false;
let mouseRevealed = false; // mouse moved during a test: keep the header visible

const input = $("#input");
const body = document.body;

// ------------------------------------------------------------------ settings

function applySettings() {
  if (!THEMES[settings.theme]) settings.theme = "classic";
  body.dataset.theme = settings.theme;
  body.dataset.lang = settings.lang;
  body.classList.toggle("smooth-caret", settings.smoothCaret);
  document.documentElement.lang = settings.lang === "km" ? "km" : "en";
  for (const group of document.querySelectorAll("#config .group")) {
    const key = group.dataset.key;
    group.hidden = (key === "time" && settings.mode !== "time") || (key === "words" && settings.mode !== "words");
    for (const b of group.querySelectorAll("button")) {
      b.classList.toggle("active", String(settings[key]) === b.dataset.value);
    }
  }
  for (const s of document.querySelectorAll("#settings .setting[data-key]")) {
    for (const b of s.querySelectorAll("button[data-value]")) {
      b.classList.toggle("active", String(settings[s.dataset.key]) === b.dataset.value);
    }
  }
  const sound = $("#nav-sound");
  sound.classList.toggle("on", settings.sound !== "off");
  sound.title = `typing sound: ${settings.sound}`;
  $("#theme-name").textContent = `theme: ${settings.theme}`;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = THEMES[settings.theme][0];
}

function setSetting(key, value, restart = true) {
  if (typeof store.DEFAULTS[key] === "number") value = Number(value);
  if (typeof store.DEFAULTS[key] === "boolean") value = value === true || value === "true";
  settings = { ...settings, [key]: value };
  store.saveSettings(settings);
  applySettings();
  if (restart) newTest();
}

// ------------------------------------------------------------------ test

async function newTest(words = null, src = null) {
  const gen = ++generation;
  if (!words) {
    try {
      const text = await makeText(settings);
      words = text.words;
      src = text.source;
      if (settings.mode === "time") wordPool = await loadWords(settings.lang);
    } catch (err) {
      $("#words").textContent = `could not load the word list (${err.message}). Is the app running through "khmertyper web"?`;
      return;
    }
  }
  if (gen !== generation) return; // a newer restart won the race
  test = new TypingTest(words, {
    timeLimit: settings.mode === "time" ? settings.time : null,
    mergeDaTa: settings.mergeDaTa,
  });
  source = src;
  shownResult = false;
  showView("test");
  renderAll();
  focusInput();
}

function showView(which) {
  $("#test").hidden = which !== "test";
  $("#result").hidden = which !== "result";
  $("#config").hidden = which !== "test";
  body.classList.remove("typing");
}

function wordHTML(i) {
  if (i > test.index) {
    return test.target[i].map((c) => `<span class="cl">${esc(c)}</span>`).join("");
  }
  const v = test.view(i);
  let html = v.target.map((c, k) => `<span class="cl ${v.statuses[k]}">${esc(c)}</span>`).join("");
  html += v.extras.map((c) => `<span class="cl extra">${esc(c)}</span>`).join("");
  return html;
}

function renderAll() {
  const words = $("#words");
  words.innerHTML = '<div id="words-inner"></div>';
  inner = words.firstChild;
  wordEls = [];
  caret = null; // the old caret went with the old words
  appendWords(0);
  caret = document.createElement("div");
  caret.id = "caret";
  inner.appendChild(caret);
  $("#source").textContent = source || "";
  updateAll();
}

function appendWords(from) {
  const frag = document.createDocumentFragment();
  for (let i = from; i < test.words.length; i++) {
    const w = document.createElement("div");
    w.className = "word";
    w.innerHTML = wordHTML(i);
    frag.appendChild(w);
    wordEls.push(w);
  }
  if (caret) inner.insertBefore(frag, caret);
  else inner.appendChild(frag);
}

function renderWord(i) {
  const el = wordEls[i];
  if (!el) return;
  el.innerHTML = wordHTML(i);
  const v = i <= test.index ? test.view(i) : null;
  const committed = v && (i < test.index || test.lastCommitted);
  el.classList.toggle("error", Boolean(committed && !v.correct));
}

function updateAll() {
  updateCaret();
  updateScroll();
  updateLive();
  updateHint();
}

function updateCaret() {
  if (!test || !caret) return;
  const i = test.index;
  const wordEl = wordEls[i];
  const v = test.current();
  const spans = wordEl.children;
  let left;
  if (v.extras.length || v.cursor >= v.target.length) {
    const last = spans[spans.length - 1];
    left = wordEl.offsetLeft + (last ? last.offsetLeft + last.offsetWidth : 0);
  } else {
    const span = spans[v.cursor];
    left = wordEl.offsetLeft + span.offsetLeft;
    // Glide through a multi-key cluster as its parts are typed.
    if (v.statuses[v.cursor] === Status.PENDING) {
      const typed = [...v.typed[v.cursor]].length;
      const total = [...v.target[v.cursor]].length;
      left += span.offsetWidth * Math.min(0.85, typed / Math.max(total, 1));
    } else if (v.statuses[v.cursor] === Status.WRONG) {
      left += span.offsetWidth; // after the mistake, where the next key lands
    }
  }
  caret.style.left = `${left - 1}px`;
  caret.style.top = `${wordEl.offsetTop}px`;
  caret.classList.toggle("hidden", test.finished);
}

function updateScroll() {
  const i = test.index;
  const top = wordEls[i].offsetTop;
  let prevTop = 0;
  for (let k = i - 1; k >= 0; k--) {
    if (wordEls[k].offsetTop < top) {
      prevTop = wordEls[k].offsetTop;
      break;
    }
  }
  inner.style.transform = `translateY(${-prevTop}px)`;
}

function updateLive() {
  if (!test) return;
  const t = now();
  if (settings.mode === "time") {
    const left = test.started ? settings.time - test.elapsed(t) : settings.time;
    $("#progress").textContent = String(Math.max(0, Math.ceil(left - 1e-9)));
  } else {
    const done = Math.min(test.index + (test.typed[test.index] ? 1 : 0), test.words.length);
    $("#progress").textContent = `${done}/${test.words.length}`;
  }
  if (settings.liveSpeed && test.started && !test.finished) {
    const secs = Math.max(test.elapsed(t), 1);
    $("#live-wpm").textContent = `${Math.round(perMinute(test.netChars() / CHARS_PER_WORD, secs))}`;
  } else {
    $("#live-wpm").textContent = "";
  }
  if (!mouseRevealed) body.classList.toggle("typing", test.started && !test.finished);
}

function updateHint() {
  const hint = $("#hint");
  if (!settings.hints || !test || test.finished) {
    hint.classList.remove("show");
    return;
  }
  const v = test.current();
  const k = v.statuses.findIndex((s) => s === Status.WRONG);
  if (k >= 0) {
    const typedChars = new Set(clean(v.typed[k] || ""));
    const keys = keystrokeHint(v.target[k]);
    let marked = false;
    const chips = keys.map((key) => {
      const ch = key.slice(-1);
      let cls = typedChars.has(ch) ? "done" : "";
      if (!cls && !marked) {
        cls = "next";
        marked = true;
      }
      return `<span class="key ${cls}">${esc(key)}</span>`;
    }).join("");
    hint.innerHTML = `<span>expected</span><span class="expected">${esc(v.target[k])}</span>` +
      `<span class="keys">${chips}</span><span>${keys.length} key${keys.length === 1 ? "" : "s"}</span>`;
    hint.classList.add("show");
  } else if (v.extras.length) {
    hint.innerHTML = "<span>extra letters · backspace to remove</span>";
    hint.classList.add("show");
  } else {
    hint.classList.remove("show");
  }
}

// ------------------------------------------------------------------ input

function feed(ch) {
  if (!test || test.finished) return;
  const before = test.events.length;
  const prevIndex = test.index;
  test.type(ch, now());
  afterInput(prevIndex, before);
}

function afterInput(prevIndex, eventsBefore) {
  lastKeyAt = now();
  mouseRevealed = false;
  caret?.classList.remove("blink");
  if (test.events.length > eventsBefore) {
    const e = test.events[test.events.length - 1];
    if (e.kind !== "backspace") play(settings.sound, e.correct ? (e.kind === "space" ? "space" : "key") : "error");
  }
  if (test.timeLimit !== null && test.index > test.words.length - 40 && wordPool.length) {
    const from = test.words.length;
    test.extend(randomWords(wordPool, 60));
    appendWords(from);
  }
  const lo = Math.max(0, Math.min(prevIndex, test.index) - 1);
  const hi = Math.max(prevIndex, test.index) + 1;
  for (let i = lo; i <= hi; i++) renderWord(i);
  if (test.index > prevIndex) wordEls[test.index]?.classList.add("fresh");
  if (test.finished) {
    showResult();
    return;
  }
  updateAll();
}

function backspace(word = false) {
  if (!test || test.finished) return;
  const before = test.events.length;
  const prevIndex = test.index;
  if (word) test.deleteWord(now());
  else test.backspace(now());
  afterInput(prevIndex, before);
}

input.addEventListener("beforeinput", (e) => {
  if (e.isComposing || e.inputType === "insertCompositionText") return; // let IMEs compose
  e.preventDefault();
  switch (e.inputType) {
    case "insertText":
    case "insertReplacementText":
      for (const ch of e.data || "") feed(ch);
      break;
    case "deleteContentBackward":
      backspace(false);
      break;
    case "deleteWordBackward":
    case "deleteSoftLineBackward":
    case "deleteHardLineBackward":
      backspace(true);
      break;
    default:
      break; // no paste, no line breaks
  }
});
input.addEventListener("compositionend", (e) => {
  for (const ch of e.data || "") feed(ch);
  input.value = "";
});
input.addEventListener("input", () => { if (!input.value.length) return; input.value = ""; });
input.addEventListener("blur", () => setTimeout(syncFocus, 0));
input.addEventListener("focus", syncFocus);

function anyDialogOpen() {
  return $("#settings").open || $("#history").open;
}

function syncFocus() {
  const unfocused = !$("#test").hidden && document.activeElement !== input && !anyDialogOpen();
  body.classList.toggle("unfocused", unfocused);
}

function focusInput() {
  if (!anyDialogOpen() && !$("#test").hidden) input.focus({ preventScroll: true });
  syncFocus();
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Tab") {
    if (anyDialogOpen()) return;
    e.preventDefault();
    newTest();
    return;
  }
  if (e.key === "Escape" && !anyDialogOpen()) {
    e.preventDefault();
    openSettings();
    return;
  }
  if (!$("#result").hidden && e.key === "Enter") {
    e.preventDefault();
    newTest();
    return;
  }
  if (!anyDialogOpen() && !$("#test").hidden && document.activeElement !== input &&
      !e.metaKey && !e.ctrlKey && !e.altKey && e.key.length === 1) {
    input.focus({ preventScroll: true });
  }
});
$("#words-wrap").addEventListener("click", focusInput);
document.addEventListener("paste", (e) => { if (e.target === input) e.preventDefault(); });

// ------------------------------------------------------------------ result

function modeLabel(s) {
  if (s.mode === "time") return `time ${s.time}`;
  if (s.mode === "words") return `words ${s.words}`;
  return "quote";
}

function showResult() {
  if (shownResult) return;
  shownResult = true;
  const st = compute(test, now());
  const modeValue = settings.mode === "time" ? settings.time : settings.mode === "words" ? settings.words : "quote";
  const record = {
    lang: settings.lang, mode: settings.mode, modeValue, timestamp: new Date().toISOString(),
    wpm: st.wpm, rawWpm: st.rawWpm, accuracy: st.accuracy, consistency: st.consistency, cpm: st.cpm,
    clustersPm: st.clustersPm, wordsPm: st.wordsPm, duration: st.duration, keystrokes: st.keystrokes,
    errors: st.errors, missed: st.missed, series: st.series,
  };
  let pb = { isPb: false, previous: null };
  const valid = st.keystrokes > 0 && st.duration >= 1;
  if (valid) pb = store.addResult(record);

  showView("result");
  $("#r-wpm").textContent = Math.round(st.wpm);
  $("#r-acc").textContent = `${Math.round(st.accuracy)}%`;
  const c = st.clusterCounts;
  const stat = (label, value, title) =>
    `<div class="stat"${title ? ` title="${esc(title)}"` : ""}><div class="label">${label}</div><div class="value">${value}</div></div>`;
  $("#res-stats").innerHTML = [
    stat("test type", `<small>${esc(modeLabel(settings))}<br>${esc(LANG_NAME[settings.lang])}</small>`),
    stat("raw", Math.round(st.rawWpm), "every keystroke ÷ 5 per minute, right or wrong"),
    stat("clusters", `${c.correct}/${c.wrong}/${c.extra}/${c.missed}`, "correct / wrong / extra / missed letter clusters"),
    stat("consistency", `${Math.round(st.consistency)}%`, "how steady your raw speed was, second to second"),
    stat("cpm", Math.round(st.cpm), `correct characters per minute (raw ${Math.round(st.rawCpm)})`),
    stat("clusters/min", Math.round(st.clustersPm), "correct letter clusters per minute"),
    stat("time", `${Math.round(st.duration)}s`, `${st.duration}s · ${st.keystrokes} keystrokes, ${st.errors} errors`),
  ].join("");
  $("#res-missed").innerHTML = st.missed.length
    ? `<div class="label">most missed</div><div class="chips">${st.missed.slice(0, 8).map(([cl, n]) =>
        `<span class="chip"><b>${esc(cl)}</b><span class="keys">${esc(keystrokeHint(cl).join(" "))}</span>×${n}</span>`).join("")}</div>`
    : "";

  const banner = $("#pb-banner");
  if (pb.isPb) {
    banner.hidden = false;
    banner.querySelector("span").textContent = pb.previous
      ? `new personal best! previous ${Math.round(pb.previous.wpm)} wpm`
      : "first result in this mode · personal best set";
    if (pb.previous) confetti();
  } else {
    banner.hidden = !pb.previous;
    if (pb.previous) banner.querySelector("span").textContent = `personal best ${Math.round(pb.previous.wpm)} wpm`;
  }
  if (!valid) {
    banner.hidden = false;
    banner.querySelector("span").textContent = "too short to save";
  }
  requestAnimationFrame(() => drawChart($("#chart"), st.series));
  input.blur();
  $("#res-next").focus({ preventScroll: true });
}

function confetti() {
  const canvas = $("#confetti");
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  canvas.width = innerWidth * dpr;
  canvas.height = innerHeight * dpr;
  ctx.scale(dpr, dpr);
  const colours = THEMES[settings.theme];
  const parts = Array.from({ length: 90 }, () => ({
    x: innerWidth / 2, y: innerHeight / 3,
    vx: (Math.random() - 0.5) * 14, vy: -Math.random() * 12 - 4,
    r: Math.random() * 4 + 2, c: colours[1 + Math.floor(Math.random() * 2)], a: Math.random() * Math.PI,
  }));
  const start = performance.now();
  (function frame(t) {
    const age = (t - start) / 1000;
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    for (const p of parts) {
      p.vy += 0.35;
      p.x += p.vx;
      p.y += p.vy;
      p.a += 0.2;
      ctx.globalAlpha = Math.max(0, 1 - age / 1.8);
      ctx.fillStyle = p.c;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.a);
      ctx.fillRect(-p.r, -p.r / 2, p.r * 2, p.r);
      ctx.restore();
    }
    if (age < 1.8) requestAnimationFrame(frame);
    else ctx.clearRect(0, 0, innerWidth, innerHeight);
  })(start);
}

// ------------------------------------------------------------------ dialogs

function openSettings() {
  const themes = $("#settings .themes");
  themes.innerHTML = Object.entries(THEMES).map(([name, [bg, main, text]]) =>
    `<button type="button" data-value="${name}"><span class="swatch" style="background:${bg}"><i style="background:${main}"></i><i style="background:${text}"></i></span>${name}</button>`,
  ).join("");
  applySettings();
  $("#settings").showModal();
}

document.querySelectorAll("#settings .setting[data-key]").forEach((row) => {
  row.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-value]");
    if (!b) return;
    const key = row.dataset.key;
    const restart = key === "mergeDaTa";
    setSetting(key, b.dataset.value, restart);
    if (key === "sound") play(settings.sound, "key");
    if (key === "smoothCaret" || key === "theme") requestAnimationFrame(updateCaret);
  });
});
$("#clear-history").addEventListener("click", () => {
  if (confirm("Delete all saved results and personal bests from this browser?")) store.clearHistory();
});
$("#settings").addEventListener("close", focusInput);
$("#history").addEventListener("close", focusInput);

// Results are stored as UTC ISO strings; show them in the viewer's time zone.
function localDate(iso, withTime = false) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return withTime
    ? d.toLocaleString([], { dateStyle: "medium", timeStyle: "short" })
    : d.toLocaleDateString([], { dateStyle: "medium" });
}

function openHistory() {
  const bests = Object.values(store.bests()).sort((a, b) =>
    a.lang.localeCompare(b.lang) || a.mode.localeCompare(b.mode) || String(a.modeValue).localeCompare(String(b.modeValue), undefined, { numeric: true }));
  $("#h-bests").innerHTML = bests.length
    ? `<table><thead><tr><th>language</th><th>mode</th><th>wpm</th><th>acc</th><th>raw</th><th>date</th></tr></thead><tbody>${
      bests.map((r) => `<tr><td>${esc(LANG_NAME[r.lang])}</td><td>${esc(`${r.mode} ${r.modeValue}`)}</td><td class="num">${Math.round(r.wpm)}</td><td>${Math.round(r.accuracy)}%</td><td>${Math.round(r.rawWpm)}</td><td>${esc(localDate(r.timestamp))}</td></tr>`).join("")}</tbody></table>`
    : '<div class="empty">no results yet · finish a test to set a personal best</div>';

  const all = store.bests();
  const pairs = Object.entries(all).filter(([k]) => k.startsWith("km:") && all[`en:${k.slice(3)}`]);
  $("#h-compare").innerHTML = pairs.map(([k, km]) => {
    const en = all[`en:${k.slice(3)}`];
    const pct = en.wpm ? Math.round((100 * km.wpm) / en.wpm) : 0;
    return `<div>${esc(`${km.mode} ${km.modeValue}`)}: ខ្មែរ ${Math.round(km.wpm)} wpm vs english ${Math.round(en.wpm)} wpm · <b>${pct}%</b></div><div class="bar"><i style="width:${Math.min(100, pct)}%"></i></div>`;
  }).join("") || '<div class="empty">finish the same mode in both languages to compare your Khmer and English speed</div>';

  const recent = store.history().slice(-20).reverse();
  $("#h-recent").innerHTML = recent.length
    ? `<table><thead><tr><th>date</th><th>language</th><th>mode</th><th>wpm</th><th>acc</th><th>time</th></tr></thead><tbody>${
      recent.map((r) => `<tr><td>${esc(localDate(r.timestamp, true))}</td><td>${esc(LANG_NAME[r.lang])}</td><td>${esc(`${r.mode} ${r.modeValue}`)}</td><td class="num">${Math.round(r.wpm)}</td><td>${Math.round(r.accuracy)}%</td><td>${Math.round(r.duration)}s</td></tr>`).join("")}</tbody></table>`
    : '<div class="empty">no tests yet</div>';

  const missed = store.mostMissed("km");
  $("#h-missed").innerHTML = missed.length
    ? `<h2>most missed khmer clusters</h2><div class="chips">${missed.map(([cl, n]) =>
        `<span class="chip"><b>${esc(cl)}</b><span class="keys">${esc(keystrokeHint(cl).join(" "))}</span>×${n}</span>`).join("")}</div>`
    : "";
  $("#history").showModal();
}

// ------------------------------------------------------------------ wiring

// Toolbar buttons shouldn't pull focus away from the typing area.
for (const sel of ["#config", "#nav-restart", "#nav-sound", "#res-next", "#res-repeat"]) {
  $(sel).addEventListener("mousedown", (e) => { if (e.target.closest("button")) e.preventDefault(); });
}
$("#config").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-value]");
  if (!b) return;
  setSetting(b.closest(".group").dataset.key, b.dataset.value);
});
$("#logo").addEventListener("click", (e) => { e.preventDefault(); newTest(); });
$("#nav-restart").addEventListener("click", () => newTest());
$("#nav-settings").addEventListener("click", openSettings);
$("#nav-history").addEventListener("click", openHistory);
$("#nav-sound").addEventListener("click", () => {
  const order = ["off", "click", "soft"];
  setSetting("sound", order[(order.indexOf(settings.sound) + 1) % order.length], false);
  play(settings.sound, "key");
  focusInput();
});
$("#res-next").addEventListener("click", () => newTest());
$("#res-repeat").addEventListener("click", () => {
  if (test) newTest(test.words.slice(0, test.target.length), source);
});
$("#focus-overlay").addEventListener("click", focusInput);

setInterval(() => {
  if (!test || $("#test").hidden) return;
  const t = now();
  if (test.started && !test.finished && test.timeLimit !== null && test.elapsed(t) >= test.timeLimit) {
    test.finish(test.startedAt + test.timeLimit);
    showResult();
    return;
  }
  updateLive();
  if (caret && t - lastKeyAt > 0.6) caret.classList.add("blink");
}, 100);

// Focus mode: the header and toolbar fade out while typing and come back as
// soon as the mouse moves.
document.addEventListener("mousemove", (e) => {
  if (Math.abs(e.movementX) + Math.abs(e.movementY) < 3 || !body.classList.contains("typing")) return;
  mouseRevealed = true;
  body.classList.remove("typing");
});
window.addEventListener("resize", () => { if (test && !$("#test").hidden) updateAll(); });
document.fonts?.ready.then(() => { if (test) updateAll(); });

// Expose a tiny hook for automated UI checks.
window.khmertype = { feed, backspace, get test() { return test; }, newTest };

applySettings();
newTest();
