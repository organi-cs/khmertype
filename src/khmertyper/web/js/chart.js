// Results chart: net WPM (area + line), raw WPM (line), error marks, and a
// hover guide showing the numbers for each second. Plain SVG, themed by CSS.

const NS = "http://www.w3.org/2000/svg";

function el(name, attrs = {}, parent) {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
}

function niceMax(v) {
  if (v <= 10) return 10;
  const step = 10 ** Math.floor(Math.log10(v));
  for (const m of [1, 2, 2.5, 5, 10]) if (step * m >= v) return step * m;
  return v;
}

export function drawChart(container, series) {
  container.innerHTML = "";
  const { wpm, raw, errors } = series;
  const n = wpm.length;
  const W = container.clientWidth || 640;
  const H = container.clientHeight || 200;
  const pad = { l: 40, r: 12, t: 16, b: 26 };
  const top = niceMax(Math.max(10, ...wpm, ...raw));
  const x = (i) => pad.l + (n <= 1 ? (W - pad.l - pad.r) / 2 : (i / (n - 1)) * (W - pad.l - pad.r));
  const y = (v) => pad.t + (1 - v / top) * (H - pad.t - pad.b);

  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, class: "chart-svg", role: "img",
    "aria-label": "speed over time" }, container);

  // 4 or 5 gridlines, whichever lands on whole numbers (250 -> 50s, 200 -> 50s).
  const steps = Number.isInteger(top / 4) ? 4 : 5;
  for (let k = 0; k <= steps; k++) {
    const v = (top * k) / steps;
    el("line", { x1: pad.l, x2: W - pad.r, y1: y(v), y2: y(v), class: "grid" }, svg);
    el("text", { x: pad.l - 8, y: y(v) + 4, class: "axis", "text-anchor": "end" }, svg).textContent = Math.round(v);
  }
  const ticks = Math.min(n, 8);
  for (let k = 0; k < ticks; k++) {
    const i = ticks === 1 ? 0 : Math.round((k * (n - 1)) / (ticks - 1));
    el("text", { x: x(i), y: H - 6, class: "axis", "text-anchor": "middle" }, svg).textContent = `${i + 1}`;
  }

  const path = (vals) => vals.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
  el("path", { d: `${path(wpm)}L${x(n - 1)},${y(0)}L${x(0)},${y(0)}Z`, class: "area" }, svg);
  el("path", { d: path(raw), class: "raw-line" }, svg);
  el("path", { d: path(wpm), class: "wpm-line" }, svg);
  errors.forEach((e, i) => {
    if (!e) return;
    const cx = x(i);
    const cy = pad.t + 2;
    el("path", { d: `M${cx - 4},${cy - 4}L${cx + 4},${cy + 4}M${cx + 4},${cy - 4}L${cx - 4},${cy + 4}`,
      class: "err-mark" }, svg);
  });

  // Hover guide.
  const guide = el("line", { y1: pad.t, y2: H - pad.b, class: "guide", visibility: "hidden" }, svg);
  const dot = el("circle", { r: 4, class: "guide-dot", visibility: "hidden" }, svg);
  const tip = document.createElement("div");
  tip.className = "chart-tip";
  container.appendChild(tip);
  svg.addEventListener("mousemove", (ev) => {
    const box = svg.getBoundingClientRect();
    const px = ((ev.clientX - box.left) / box.width) * W;
    const i = Math.max(0, Math.min(n - 1, Math.round(((px - pad.l) / (W - pad.l - pad.r)) * (n - 1))));
    guide.setAttribute("x1", x(i));
    guide.setAttribute("x2", x(i));
    dot.setAttribute("cx", x(i));
    dot.setAttribute("cy", y(wpm[i]));
    guide.setAttribute("visibility", "visible");
    dot.setAttribute("visibility", "visible");
    tip.innerHTML = `<b>${i + 1}s</b><span>wpm <em>${Math.round(wpm[i])}</em></span>` +
      `<span>raw <em>${Math.round(raw[i])}</em></span>` +
      (errors[i] ? `<span class="tip-err">errors <em>${errors[i]}</em></span>` : "");
    tip.style.left = `${(x(i) / W) * 100}%`;
    tip.classList.add("show");
  });
  svg.addEventListener("mouseleave", () => {
    guide.setAttribute("visibility", "hidden");
    dot.setAttribute("visibility", "hidden");
    tip.classList.remove("show");
  });
}
