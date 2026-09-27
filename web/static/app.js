// StickerBook farm renderer.
//
// This file is a PROPOSER and a RENDERER. It is not an authority.
//
// The two rules it follows:
//   1. It never decides that a move happened. It sends where the pointer
//      went, then draws whatever authoritative state comes back. A refused
//      drag simply redraws at the old slot, because that is what the kernel
//      says is true.
//   2. It reports where the pointer went. The kernel decides whether that
//      position is legal and whether this principal may move that sticker.
//
// Everything here is presentation. Anyone may tamper with it; the Python
// kernel still decides.

const PAGE_W = 1000, PAGE_H = 640;
const svg = document.getElementById("page");
const layers = {
  backdrop: document.getElementById("backdrop"),
  stickers: document.getElementById("stickers"),
};
const els = {
  revision: document.getElementById("revision"),
  principal: document.getElementById("principal"),
  verdict: document.getElementById("verdict"),
  receipts: document.getElementById("receipts"),
};

let state = null;
let drag = null;
let commandSeq = 0;

const svgEl = (name, attrs = {}) => {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
};

// ---------------------------------------------------------------- backdrop
// Passive scenery. Drawn from host-supplied positions, never interactive,
// never a target of any command.

const BACKDROP_ART = {
  barn(g) {
    g.appendChild(svgEl("rect", { x: -55, y: -35, width: 110, height: 80,
      fill: "#b4453a", stroke: "#8d332a", "stroke-width": 2, rx: 3 }));
    g.appendChild(svgEl("path", { d: "M -66 -35 L 0 -78 L 66 -35 Z",
      fill: "#8d332a" }));
    g.appendChild(svgEl("rect", { x: -17, y: 5, width: 34, height: 40,
      fill: "#f2e3cd", stroke: "#8d332a", "stroke-width": 2 }));
  },
  tree(g) {
    g.appendChild(svgEl("rect", { x: -8, y: 6, width: 16, height: 52,
      fill: "#7a5a3a", rx: 3 }));
    g.appendChild(svgEl("circle", { cx: 0, cy: -16, r: 44, fill: "#4f9a5c" }));
    g.appendChild(svgEl("circle", { cx: -26, cy: 6, r: 28, fill: "#59a866" }));
    g.appendChild(svgEl("circle", { cx: 26, cy: 4, r: 26, fill: "#458a52" }));
  },
  pond(g) {
    g.appendChild(svgEl("ellipse", { cx: 0, cy: 0, rx: 92, ry: 46,
      fill: "#6fb3d6", stroke: "#4e93b8", "stroke-width": 2 }));
    g.appendChild(svgEl("path", { d: "M -46 -8 q 22 -10 44 0", fill: "none",
      stroke: "#9ed2ea", "stroke-width": 3, "stroke-linecap": "round" }));
  },
  fence(g) {
    for (let i = -2; i <= 2; i++) {
      g.appendChild(svgEl("rect", { x: i * 34 - 5, y: -30, width: 10,
        height: 62, fill: "#c9ab7e", rx: 2 }));
    }
    for (const y of [-16, 8]) {
      g.appendChild(svgEl("rect", { x: -92, y, width: 184, height: 8,
        fill: "#dcc296", rx: 2 }));
    }
  },
};

function drawBackdrop(backdrop) {
  layers.backdrop.replaceChildren();
  for (const f of backdrop.features) {
    const g = svgEl("g", {
      transform: `translate(${f.x * PAGE_W} ${f.y * PAGE_H})`,
    });
    (BACKDROP_ART[f.id] || (() => {}))(g);
    layers.backdrop.appendChild(g);
  }
}

// ---------------------------------------------------------------- stickers

const STICKER_ART = {
  cow(g) {
    g.appendChild(svgEl("ellipse", { cx: 0, cy: 0, rx: 40, ry: 27,
      fill: "#fbfbfb", stroke: "#3a3a3a", "stroke-width": 2 }));
    g.appendChild(svgEl("ellipse", { cx: -14, cy: -6, rx: 13, ry: 10,
      fill: "#3a3a3a" }));
    g.appendChild(svgEl("ellipse", { cx: 16, cy: 8, rx: 10, ry: 8,
      fill: "#3a3a3a" }));
    g.appendChild(svgEl("circle", { cx: 34, cy: -14, r: 14, fill: "#fbfbfb",
      stroke: "#3a3a3a", "stroke-width": 2 }));
    g.appendChild(svgEl("circle", { cx: 38, cy: -16, r: 2.5, fill: "#3a3a3a" }));
    for (const dx of [-22, -6, 10, 24]) {
      g.appendChild(svgEl("rect", { x: dx, y: 22, width: 7, height: 16,
        fill: "#3a3a3a", rx: 2 }));
    }
  },
  butterfly(g) {
    g.appendChild(svgEl("ellipse", { cx: -13, cy: -8, rx: 15, ry: 19,
      fill: "#e89ac4", stroke: "#b96b98", "stroke-width": 1.5 }));
    g.appendChild(svgEl("ellipse", { cx: 13, cy: -8, rx: 15, ry: 19,
      fill: "#e89ac4", stroke: "#b96b98", "stroke-width": 1.5 }));
    g.appendChild(svgEl("ellipse", { cx: -10, cy: 12, rx: 11, ry: 13,
      fill: "#f0b7d4", stroke: "#b96b98", "stroke-width": 1.5 }));
    g.appendChild(svgEl("ellipse", { cx: 10, cy: 12, rx: 11, ry: 13,
      fill: "#f0b7d4", stroke: "#b96b98", "stroke-width": 1.5 }));
    g.appendChild(svgEl("rect", { x: -2.5, y: -20, width: 5, height: 40,
      rx: 2.5, fill: "#5a4633" }));
  },
};

function drawStickers(stickers) {
  layers.stickers.replaceChildren();
  for (const s of stickers) {
    const g = svgEl("g", {
      class: "sticker",
      "data-id": s.id,
      transform: `translate(${s.x * PAGE_W} ${s.y * PAGE_H})`,
    });
    (STICKER_ART[s.is] || (() => {}))(g);

    const name = svgEl("text", { y: 52, class: "sticker-label" });
    name.textContent = s.id;
    g.appendChild(name);

    const owner = svgEl("text", { y: 68, class: "owner-tag" });
    owner.textContent = s.mine ? "yours" : `owned by ${s.owner}`;
    g.appendChild(owner);

    g.addEventListener("pointerdown", (e) => beginDrag(e, s));
    layers.stickers.appendChild(g);
  }
}

// ------------------------------------------------------------------ render

function render() {
  if (!state) return;
  drawBackdrop(state.backdrop);
  drawStickers(state.stickers);
  els.revision.textContent = state.revision;
  els.principal.textContent = state.principal;
}

function showVerdict(receipt) {
  if (!receipt) return;
  const ok = receipt.accepted;
  els.verdict.className = "verdict " + (ok ? "accepted" : "rejected");
  els.verdict.textContent = ok
    ? `accepted — ${receipt.object} moved (revision ${receipt.resultRevision})`
    : `refused — ${receipt.reason}; nothing changed`;
}

async function refreshReceipts() {
  const r = await fetch("/api/receipts");
  const { receipts } = await r.json();
  els.receipts.replaceChildren();
  for (const rec of receipts.slice().reverse()) {
    const li = document.createElement("li");
    const mark = document.createElement("span");
    mark.className = rec.accepted ? "ok" : "no";
    mark.textContent = rec.accepted ? "ACCEPT " : "REFUSE ";
    li.appendChild(mark);
    li.appendChild(document.createTextNode(
      `${rec.action} ${rec.object || ""} → ${rec.reason} (rev ${rec.resultRevision})`));
    els.receipts.appendChild(li);
  }
}

// ------------------------------------------------------------------- drag
// Dragging moves a ghost. Authoritative position only ever changes when the
// kernel says so.

function pointerFraction(evt) {
  const box = svg.getBoundingClientRect();
  const clamp = (v) => Math.min(Math.max(v, 0), 1);
  return {
    x: clamp((evt.clientX - box.left) / box.width),
    y: clamp((evt.clientY - box.top) / box.height),
  };
}

function beginDrag(evt, sticker) {
  evt.preventDefault();
  const node = evt.currentTarget;
  drag = { id: sticker.id, node };
  node.classList.add("dragging");
  node.setPointerCapture(evt.pointerId);

  const onMove = (e) => {
    const p = pointerFraction(e);
    node.setAttribute("transform",
      `translate(${p.x * PAGE_W} ${p.y * PAGE_H})`);
  };
  const onUp = async (e) => {
    node.removeEventListener("pointermove", onMove);
    node.removeEventListener("pointerup", onUp);
    node.removeEventListener("pointercancel", onUp);
    node.classList.remove("dragging");
    node.classList.add("pending");
    await proposeMove(sticker.id, pointerFraction(e));
    drag = null;
  };
  node.addEventListener("pointermove", onMove);
  node.addEventListener("pointerup", onUp);
  node.addEventListener("pointercancel", onUp);
}

async function proposeMove(stickerId, point) {
  commandSeq += 1;
  const body = {
    sticker: stickerId,
    command_id: `ui-${Date.now()}-${commandSeq}`,
    point,                                  // where the pointer went
    based_on_revision: state ? state.revision : null,
  };
  let payload;
  try {
    const res = await fetch("/api/propose-move", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    payload = await res.json();
  } catch (err) {
    els.verdict.className = "verdict rejected";
    els.verdict.textContent = "bridge unreachable; nothing changed";
    await reload();
    return;
  }

  // Draw what the kernel says is true, whatever we proposed.
  if (payload.state) state = payload.state;
  render();
  if (payload.ok) showVerdict(payload.receipt);
  else {
    els.verdict.className = "verdict rejected";
    els.verdict.textContent = `refused — ${payload.error}; nothing changed`;
  }
  await refreshReceipts();
}

async function reload() {
  state = await (await fetch("/api/state")).json();
  render();
  await refreshReceipts();
}

reload();
