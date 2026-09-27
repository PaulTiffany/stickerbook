// StickerBook — the farm page.
//
// This file is a PROPOSER and a RENDERER. It is not an authority.
//
//   * It never decides that something happened. It says where the pointer
//     went, then draws whatever the kernel returns. A refused drag simply
//     redraws at the old position, because that is what is true.
//   * A refusal is not an error message. The sticker does not go — the same
//     feedback a real sticker gives when it will not stick.
//
// Everything here is presentation. Anyone may tamper with it; the Python
// kernel still decides.

const PAGE_W = 1000, PAGE_H = 640;
const DEV = new URLSearchParams(location.search).get("dev") === "1";

const svg = document.getElementById("page");
const layers = {
  picture: document.getElementById("picture"),
  stickers: document.getElementById("stickers"),
};
const trayEl = document.getElementById("tray");
const trayItems = document.getElementById("tray-items");
const dev = {
  panel: document.getElementById("dev"),
  revision: document.getElementById("revision"),
  principal: document.getElementById("principal"),
  verdict: document.getElementById("verdict"),
  receipts: document.getElementById("receipts"),
};

let state = null;
let seq = 0;
const nextId = (kind) => `ui-${kind}-${Date.now()}-${++seq}`;

const el = (name, attrs = {}) => {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
};

// ---------------------------------------------------------------- picture
// Painted scenery. Not governed objects, never interactive.

const PICTURE = {
  barn(g) {
    g.appendChild(el("rect", { x: -58, y: -34, width: 116, height: 84,
      fill: "#b4453a", stroke: "#8d332a", "stroke-width": 2, rx: 3 }));
    g.appendChild(el("path", { d: "M -70 -34 L 0 -80 L 70 -34 Z", fill: "#8d332a" }));
    g.appendChild(el("rect", { x: -18, y: 8, width: 36, height: 42,
      fill: "#f2e3cd", stroke: "#8d332a", "stroke-width": 2 }));
  },
  tree(g) {
    g.appendChild(el("rect", { x: -9, y: 6, width: 18, height: 56, fill: "#7a5a3a", rx: 3 }));
    g.appendChild(el("circle", { cx: 0, cy: -18, r: 46, fill: "#4f9a5c" }));
    g.appendChild(el("circle", { cx: -28, cy: 6, r: 29, fill: "#59a866" }));
    g.appendChild(el("circle", { cx: 28, cy: 4, r: 27, fill: "#458a52" }));
  },
  pond(g) {
    g.appendChild(el("ellipse", { cx: 0, cy: 0, rx: 96, ry: 48,
      fill: "#6fb3d6", stroke: "#4e93b8", "stroke-width": 2 }));
    g.appendChild(el("path", { d: "M -48 -8 q 24 -11 48 0", fill: "none",
      stroke: "#9ed2ea", "stroke-width": 3, "stroke-linecap": "round" }));
  },
  fence(g) {
    for (let i = -2; i <= 2; i++) {
      g.appendChild(el("rect", { x: i * 36 - 5, y: -32, width: 10, height: 66,
        fill: "#c9ab7e", rx: 2 }));
    }
    for (const y of [-17, 9]) {
      g.appendChild(el("rect", { x: -96, y, width: 192, height: 9,
        fill: "#dcc296", rx: 2 }));
    }
  },
};

function drawPicture(picture) {
  layers.picture.replaceChildren();
  // sky and ground, so the page reads as a place rather than a white box
  layers.picture.appendChild(el("rect", { x: 0, y: 0, width: PAGE_W,
    height: PAGE_H * 0.58, fill: "#cfe8f5" }));
  layers.picture.appendChild(el("rect", { x: 0, y: PAGE_H * 0.58,
    width: PAGE_W, height: PAGE_H * 0.42, fill: "#93c47d" }));
  layers.picture.appendChild(el("circle", { cx: 880, cy: 90, r: 42, fill: "#ffe08a" }));
  for (const f of picture.features) {
    const g = el("g", { transform: `translate(${f.x * PAGE_W} ${f.y * PAGE_H})` });
    (PICTURE[f.id] || (() => {}))(g);
    layers.picture.appendChild(g);
  }
}

// --------------------------------------------------------------- stickers

const ART = {
  cow(g) {
    g.appendChild(el("ellipse", { cx: 0, cy: 0, rx: 42, ry: 28,
      fill: "#fbfbfb", stroke: "#3a3a3a", "stroke-width": 2.5 }));
    g.appendChild(el("ellipse", { cx: -15, cy: -6, rx: 14, ry: 10, fill: "#3a3a3a" }));
    g.appendChild(el("ellipse", { cx: 17, cy: 9, rx: 10, ry: 8, fill: "#3a3a3a" }));
    g.appendChild(el("circle", { cx: 36, cy: -15, r: 15, fill: "#fbfbfb",
      stroke: "#3a3a3a", "stroke-width": 2.5 }));
    g.appendChild(el("circle", { cx: 41, cy: -18, r: 2.6, fill: "#3a3a3a" }));
    for (const dx of [-24, -7, 10, 25]) {
      g.appendChild(el("rect", { x: dx, y: 23, width: 8, height: 17,
        fill: "#3a3a3a", rx: 2 }));
    }
  },
  butterfly(g) {
    g.appendChild(el("ellipse", { cx: -14, cy: -9, rx: 16, ry: 20,
      fill: "#e89ac4", stroke: "#b96b98", "stroke-width": 1.8 }));
    g.appendChild(el("ellipse", { cx: 14, cy: -9, rx: 16, ry: 20,
      fill: "#e89ac4", stroke: "#b96b98", "stroke-width": 1.8 }));
    g.appendChild(el("ellipse", { cx: -11, cy: 13, rx: 12, ry: 14,
      fill: "#f0b7d4", stroke: "#b96b98", "stroke-width": 1.8 }));
    g.appendChild(el("ellipse", { cx: 11, cy: 13, rx: 12, ry: 14,
      fill: "#f0b7d4", stroke: "#b96b98", "stroke-width": 1.8 }));
    g.appendChild(el("rect", { x: -3, y: -22, width: 6, height: 44, rx: 3,
      fill: "#5a4633" }));
  },
  duck(g) {
    g.appendChild(el("ellipse", { cx: -2, cy: 6, rx: 30, ry: 21,
      fill: "#fdfdfd", stroke: "#c9a227", "stroke-width": 2 }));
    g.appendChild(el("circle", { cx: 22, cy: -14, r: 15, fill: "#fdfdfd",
      stroke: "#c9a227", "stroke-width": 2 }));
    g.appendChild(el("path", { d: "M 34 -13 l 18 5 l -18 6 z", fill: "#f0a930" }));
    g.appendChild(el("circle", { cx: 26, cy: -17, r: 2.4, fill: "#3a3a3a" }));
    g.appendChild(el("path", { d: "M -14 2 q 14 -12 26 2 q -13 9 -26 -2 z",
      fill: "#f2f2f2", stroke: "#c9a227", "stroke-width": 1.5 }));
  },
  hen(g) {
    g.appendChild(el("ellipse", { cx: 0, cy: 4, rx: 27, ry: 22,
      fill: "#e8c9a0", stroke: "#a9794a", "stroke-width": 2 }));
    g.appendChild(el("circle", { cx: 17, cy: -16, r: 13, fill: "#e8c9a0",
      stroke: "#a9794a", "stroke-width": 2 }));
    g.appendChild(el("path", { d: "M 11 -28 q 5 -9 10 0 q 5 -8 8 1 z", fill: "#c8443a" }));
    g.appendChild(el("path", { d: "M 28 -14 l 12 3 l -12 4 z", fill: "#f0a930" }));
    g.appendChild(el("circle", { cx: 21, cy: -18, r: 2.2, fill: "#3a3a3a" }));
    g.appendChild(el("path", { d: "M -26 0 q -12 6 -4 16 q 10 0 12 -10 z", fill: "#d6b184" }));
    for (const dx of [-6, 8]) {
      g.appendChild(el("rect", { x: dx, y: 24, width: 4, height: 12,
        fill: "#f0a930", rx: 2 }));
    }
  },
};

function stickerNode(kind, cls = "sticker") {
  const g = el("g", { class: cls });
  const art = el("g", { class: "art" });
  (ART[kind] || (() => {}))(art);
  g.appendChild(art);
  return g;
}

function drawStickers(stickers) {
  layers.stickers.replaceChildren();
  for (const s of stickers) {
    const g = stickerNode(s.is);
    g.setAttribute("data-id", s.id);
    g.setAttribute("transform", `translate(${s.x * PAGE_W} ${s.y * PAGE_H})`);
    g.addEventListener("pointerdown", (e) => grabPlaced(e, s));
    layers.stickers.appendChild(g);
  }
}

function drawTray(kinds) {
  trayItems.replaceChildren();
  for (const kind of kinds) {
    const button = document.createElement("button");
    button.className = "tray-sticker";
    button.type = "button";
    button.title = kind;
    button.setAttribute("aria-label", "Add a " + kind);
    const mini = el("svg", { viewBox: "-60 -60 120 120" });
    mini.appendChild(stickerNode(kind, ""));
    button.appendChild(mini);
    button.addEventListener("pointerdown", (e) => grabFromTray(e, kind));
    trayItems.appendChild(button);
  }
}

// ------------------------------------------------------------------ render

function render() {
  if (!state) return;
  drawPicture(state.picture);
  drawStickers(state.stickers);
  if (!trayItems.childElementCount) drawTray(state.tray);
  if (DEV) {
    dev.revision.textContent = state.revision;
    dev.principal.textContent = state.principal;
  }
}

// ------------------------------------------------------------------- input

const pageFraction = (e) => {
  const box = svg.getBoundingClientRect();
  return { x: (e.clientX - box.left) / box.width,
           y: (e.clientY - box.top) / box.height };
};
const overTray = (e) => {
  const box = trayEl.getBoundingClientRect();
  return e.clientY >= box.top;
};

// Drag a sticker already on the page: move it, or drop it on the tray to
// take it off.
function grabPlaced(evt, sticker) {
  evt.preventDefault();
  const node = evt.currentTarget;
  node.classList.add("held");
  node.setPointerCapture(evt.pointerId);

  const onMove = (e) => {
    const p = pageFraction(e);
    node.setAttribute("transform",
      `translate(${p.x * PAGE_W} ${p.y * PAGE_H})`);
    trayEl.classList.toggle("open", overTray(e));
  };
  const onUp = async (e) => {
    node.removeEventListener("pointermove", onMove);
    node.removeEventListener("pointerup", onUp);
    node.removeEventListener("pointercancel", onUp);
    node.classList.remove("held");
    trayEl.classList.remove("open");
    if (overTray(e)) await send("/api/remove", { sticker: sticker.id,
      command_id: nextId("rm") });
    else await send("/api/propose-move", { sticker: sticker.id,
      command_id: nextId("mv"), point: pageFraction(e) });
  };
  node.addEventListener("pointermove", onMove);
  node.addEventListener("pointerup", onUp);
  node.addEventListener("pointercancel", onUp);
}

// Drag out of the tray and onto the page: put a new sticker down.
function grabFromTray(evt, kind) {
  evt.preventDefault();
  const button = evt.currentTarget;
  button.setPointerCapture(evt.pointerId);

  const ghost = document.createElement("div");
  ghost.id = "ghost";
  const mini = el("svg", { viewBox: "-60 -60 120 120" });
  mini.setAttribute("width", "100%");
  mini.setAttribute("height", "100%");
  mini.appendChild(stickerNode(kind, ""));
  ghost.appendChild(mini);
  document.body.appendChild(ghost);

  const place = (e) => {
    ghost.style.left = e.clientX + "px";
    ghost.style.top = e.clientY + "px";
  };
  place(evt);

  const onMove = (e) => place(e);
  const onUp = async (e) => {
    button.removeEventListener("pointermove", onMove);
    button.removeEventListener("pointerup", onUp);
    button.removeEventListener("pointercancel", onUp);
    ghost.remove();
    const box = svg.getBoundingClientRect();
    const onPage = e.clientX >= box.left && e.clientX <= box.right
                && e.clientY >= box.top && e.clientY <= box.bottom;
    if (onPage) {
      await send("/api/place", { asset: kind, command_id: nextId("add"),
        point: pageFraction(e) });
    }
  };
  button.addEventListener("pointermove", onMove);
  button.addEventListener("pointerup", onUp);
  button.addEventListener("pointercancel", onUp);
}

// ----------------------------------------------------------------- the wire

async function send(path, body) {
  body.based_on_revision = state ? state.revision : null;
  let payload;
  try {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    payload = await res.json();
  } catch (err) {
    await reload();                       // draw whatever is actually true
    return;
  }

  // Draw what the kernel says is true, whatever we proposed.
  if (payload.state) state = payload.state;
  render();

  const receipt = payload.receipt;
  if (receipt && !receipt.accepted && receipt.object) {
    const node = layers.stickers.querySelector(`[data-id="${receipt.object}"]`);
    if (node) {
      node.classList.add("refused");
      setTimeout(() => node.classList.remove("refused"), 320);
    }
  }
  if (DEV) showVerdict(payload);
}

async function reload() {
  const res = await fetch("/api/state");
  state = await res.json();
  render();
  if (DEV) await refreshReceipts();
}

// ------------------------------------------------------------ developer view

function showVerdict(payload) {
  const r = payload.receipt;
  if (!r) {
    dev.verdict.className = "verdict rejected";
    dev.verdict.textContent = `refused — ${payload.error}`;
  } else {
    dev.verdict.className = "verdict " + (r.accepted ? "accepted" : "rejected");
    dev.verdict.textContent = r.accepted
      ? `accepted — ${r.action} ${r.object || ""} (rev ${r.resultRevision})`
      : `refused — ${r.reason}; nothing changed`;
  }
  refreshReceipts();
}

async function refreshReceipts() {
  const { receipts } = await (await fetch("/api/receipts")).json();
  dev.receipts.replaceChildren();
  for (const r of receipts.slice().reverse()) {
    const li = document.createElement("li");
    const mark = document.createElement("span");
    mark.className = r.accepted ? "ok" : "no";
    mark.textContent = r.accepted ? "ACCEPT " : "REFUSE ";
    li.append(mark, document.createTextNode(
      `${r.action} ${r.object || ""} → ${r.reason} (rev ${r.resultRevision})`));
    dev.receipts.appendChild(li);
  }
}

if (DEV) dev.panel.hidden = false;
reload();
