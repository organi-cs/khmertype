// Small synthesised key sounds (no audio files). Off by default.

let ctx = null;

function audio() {
  if (!ctx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    ctx = new AC();
  }
  if (ctx.state === "suspended") ctx.resume();
  return ctx;
}

function noiseBurst(ac, when, duration, freq, gain) {
  const frames = Math.floor(ac.sampleRate * duration);
  const buffer = ac.createBuffer(1, frames, ac.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < frames; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / frames) ** 3;
  const src = ac.createBufferSource();
  src.buffer = buffer;
  const filter = ac.createBiquadFilter();
  filter.type = "bandpass";
  filter.frequency.value = freq;
  filter.Q.value = 1.2;
  const g = ac.createGain();
  g.gain.value = gain;
  src.connect(filter).connect(g).connect(ac.destination);
  src.start(when);
}

function tone(ac, when, freq, duration, gain, type = "sine") {
  const osc = ac.createOscillator();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, when);
  osc.frequency.exponentialRampToValueAtTime(freq * 0.6, when + duration);
  const g = ac.createGain();
  g.gain.setValueAtTime(gain, when);
  g.gain.exponentialRampToValueAtTime(0.0001, when + duration);
  osc.connect(g).connect(ac.destination);
  osc.start(when);
  osc.stop(when + duration);
}

/** kind: "key" | "space" | "error"; style: "off" | "click" | "soft" */
export function play(style, kind) {
  if (style === "off") return;
  const ac = audio();
  if (!ac) return;
  const t = ac.currentTime;
  const jitter = 1 + (Math.random() - 0.5) * 0.12; // keeps repeats from sounding robotic
  if (kind === "error") {
    tone(ac, t, 180, 0.09, 0.08, "triangle");
    return;
  }
  if (style === "click") {
    noiseBurst(ac, t, 0.03, (kind === "space" ? 1800 : 3200) * jitter, kind === "space" ? 0.5 : 0.35);
  } else {
    tone(ac, t, (kind === "space" ? 330 : 520) * jitter, 0.06, 0.05);
  }
}
