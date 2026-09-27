// StickerBook front end.
//
// One surface, two world adapters:
//
//   local kernel       -> the browser proposes; Python decides.
//   public mechanical  -> deterministic in-memory behavior for GitHub Pages.
//
// The public adapter deliberately contains no agent, credential, model call,
// privileged backend, or hidden authority. It only preserves the same state
// shape so the public demo and governed localhost world share one renderer.

const PAGE_W = 1000;
const PAGE_H = 640;
const QUERY = new URLSearchParams(location.search);
const DEV = QUERY.get("dev") === "1";
const FORCE_MECHANICAL = QUERY.get("mechanical") === "1";
const LOCAL_HOST = ["localhost", "127.0.0.1", "::1"].includes(location.hostname);

const svg = document.getElementById("page");
const layers = {
  picture: document.getElementById("picture"),
  stickers: document.getElementById("stickers"),
  placement: document.getElementById("placement-layer"),
};
const hotbar = document.getElementById("hotbar");
const trayItems = document.getElementById("tray-items");
const sheets = {
  book: document.getElementById("book-screen"),
  stickers: document.getElementById("sticker-screen"),
};
const status = document.getElementById("a11y-status");
const worldNote = document.getElementById("world-note");
const dev = {
  panel: document.getElementById("dev"),
  mode: document.getElementById("world-mode"),
  revision: document.getElementById("revision"),
  principal: document.getElementById("principal"),
  verdict: document.getElementById("verdict"),
  receipts: document.getElementById("receipts"),
};

let state = null;
let seq = 0;
let traySignature = "";
let pendingDefinition = null;
let placementPreview = null;
let lastTap = { id: null, at: 0 };

const nextId = (kind) => `ui-${kind}-${Date.now()}-${++seq}`;
const copy = (value) => JSON.parse(JSON.stringify(value));

const el = (name, attrs = {}) => {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  for (const [key, value] of Object.entries(attrs)) {
    node.setAttribute(key, value);
  }
  return node;
};

// --------------------------------------------------------------- adapters

const DEMO_BOOK = {
  title: "StickerBook",
  subtitle: "Farm Book",
  pages: [
    {
      id: "farm",
      name: "The Farm",
      summary: "A barn, a pond, a tree and a fence.",
    },
  ],
  coming: [
    { id: "new-page", label: "New Page" },
    { id: "find-pages", label: "Find Pages" },
  ],
};

const DEMO_SEED = {
  revision: 2,
  principal: "human:player",
  page: { id: "farm", name: "The Farm" },
  picture: {
    description: "a small farm at midday",
    features: [
      { id: "barn", x: 0.17, y: 0.30 },
      { id: "tree", x: 0.52, y: 0.20 },
      { id: "pond", x: 0.79, y: 0.60 },
      { id: "fence", x: 0.22, y: 0.78 },
    ],
  },
  definitions: [
    { id: "butterfly", animations: ["none", "flutter"] },
    { id: "cow", animations: ["none", "chew"] },
    { id: "duck", animations: ["none", "paddle"] },
    { id: "hen", animations: ["none", "peck"] },
  ],
  stickers: [
    {
      id: "cow-1",
      definition: "cow",
      x: 0.24,
      y: 0.86,
      owner: "human:player",
      mine: true,
      animation: "none",
      revision: 1,
    },
    {
      id: "butterfly-1",
      definition: "butterfly",
      x: 0.52,
      y: 0.38,
      owner: "agent:jev-visual-1",
      mine: false,
      animation: "none",
      revision: 1,
    },
  ],
};

function createMechanicalWorld() {
  let worldState = copy(DEMO_SEED);
  let receipts = [];
  let instanceSeq = 2;

  const definition = (name) =>
    worldState.definitions.find((item) => item.id === name);

  const sticker = (id) =>
    worldState.stickers.find((item) => item.id === id);

  const pointOkay = (point) =>
    point &&
    Number.isFinite(point.x) &&
    Number.isFinite(point.y) &&
    point.x >= 0 && point.x <= 1 &&
    point.y >= 0 && point.y <= 1;

  const commit = (action, object, mutate) => {
    worldState.revision += 1;
    mutate(worldState.revision);
    const receipt = {
      accepted: true,
      action,
      object,
      reason: "mechanical-demo",
      resultRevision: worldState.revision,
    };
    receipts.push(receipt);
    receipts = receipts.slice(-24);
    return {
      ok: true,
      receipt: copy(receipt),
      state: copy(worldState),
    };
  };

  const refuse = (action, object, reason) => {
    const receipt = {
      accepted: false,
      action,
      object,
      reason,
      resultRevision: worldState.revision,
    };
    receipts.push(receipt);
    receipts = receipts.slice(-24);
    return {
      ok: true,
      receipt: copy(receipt),
      state: copy(worldState),
    };
  };

  return {
    name: "public mechanical",
    async state() {
      return copy(worldState);
    },
    async book() {
      return copy(DEMO_BOOK);
    },
    async receipts() {
      return { receipts: copy(receipts) };
    },
    async send(path, body) {
      if (path === "/api/place") {
        const def = definition(body.asset);
        if (!def || !pointOkay(body.point)) {
          return refuse("add-own-sticker", null, "invalid-demo-proposal");
        }
        const id = `${body.asset}-demo-${++instanceSeq}`;
        return commit("add-own-sticker", id, (revision) => {
          worldState.stickers.push({
            id,
            definition: body.asset,
            x: body.point.x,
            y: body.point.y,
            owner: worldState.principal,
            mine: true,
            animation: "none",
            revision,
          });
        });
      }

      if (path === "/api/propose-move") {
        const target = sticker(body.sticker);
        if (!target || !pointOkay(body.point)) {
          return refuse("move-sticker", body.sticker, "invalid-demo-proposal");
        }
        return commit("move-sticker", target.id, (revision) => {
          target.x = body.point.x;
          target.y = body.point.y;
          target.revision = revision;
        });
      }

      if (path === "/api/remove") {
        const target = sticker(body.sticker);
        if (!target) {
          return refuse("remove-own-sticker", body.sticker, "unknown-sticker");
        }
        return commit("remove-own-sticker", target.id, () => {
          worldState.stickers = worldState.stickers.filter(
            (item) => item.id !== target.id
          );
        });
      }

      if (path === "/api/animate") {
        const target = sticker(body.sticker);
        if (!target) {
          return refuse("animate-own-sticker", body.sticker, "unknown-sticker");
        }
        const def = definition(target.definition);
        const alive = (def?.animations || []).find((name) => name !== "none");
        if (!alive) {
          return refuse("animate-own-sticker", target.id, "no-animation");
        }
        return commit("animate-own-sticker", target.id, (revision) => {
          target.animation = target.animation === "none" ? alive : "none";
          target.revision = revision;
        });
      }

      return refuse("unknown", null, "not-implemented-in-public-demo");
    },
  };
}

const kernelWorld = {
  name: "local kernel",
  async state() {
    const res = await fetch("/api/state", { cache: "no-store" });
    if (!res.ok) throw new Error(`state: HTTP ${res.status}`);
    return res.json();
  },
  async book() {
    const res = await fetch("/api/book", { cache: "no-store" });
    if (!res.ok) throw new Error(`book: HTTP ${res.status}`);
    return res.json();
  },
  async receipts() {
    const res = await fetch("/api/receipts", { cache: "no-store" });
    if (!res.ok) throw new Error(`receipts: HTTP ${res.status}`);
    return res.json();
  },
  async send(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await res.json();
    if (!res.ok && !payload.receipt) {
      return payload;
    }
    return payload;
  },
};

let world = (!FORCE_MECHANICAL && LOCAL_HOST)
  ? kernelWorld
  : createMechanicalWorld();

// ---------------------------------------------------------------- picture

const PICTURE = {
  barn(g) {
    g.appendChild(el("rect", {
      x: -59, y: -31, width: 118, height: 82, rx: 4,
      fill: "#b85445", stroke: "#8f3b31", "stroke-width": 2.5,
    }));
    g.appendChild(el("path", {
      d: "M -72 -31 L 0 -82 L 72 -31 Z",
      fill: "#8e3d34", stroke: "#7f352e", "stroke-width": 2,
      "stroke-linejoin": "round",
    }));
    g.appendChild(el("rect", {
      x: -18, y: 7, width: 36, height: 44,
      fill: "#f2dfc2", stroke: "#8f3b31", "stroke-width": 2,
    }));
    g.appendChild(el("path", {
      d: "M -18 7 L 18 51 M 18 7 L -18 51",
      stroke: "#c39a72", "stroke-width": 2,
    }));
    g.appendChild(el("rect", {
      x: -42, y: -11, width: 22, height: 19,
      fill: "#cfe5ed", stroke: "#f2dfc2", "stroke-width": 3,
    }));
  },

  tree(g) {
    g.appendChild(el("rect", {
      x: -9, y: 8, width: 18, height: 56, rx: 4, fill: "#76553b",
    }));
    for (const [cx, cy, r, fill] of [
      [0, -18, 47, "#53965a"],
      [-30, 4, 30, "#65a966"],
      [31, 3, 29, "#498b50"],
      [7, 12, 32, "#5da260"],
    ]) {
      g.appendChild(el("circle", { cx, cy, r, fill }));
    }
  },

  pond(g) {
    g.appendChild(el("ellipse", {
      cx: 0, cy: 0, rx: 98, ry: 49,
      fill: "#75bad6", stroke: "#5ba0be", "stroke-width": 2.5,
    }));
    g.appendChild(el("path", {
      d: "M -59 -10 q 28 -10 56 0 M 17 14 q 22 -8 43 0",
      fill: "none", stroke: "#b7deeb", "stroke-width": 3,
      "stroke-linecap": "round", opacity: .9,
    }));
    for (const x of [-76, 79]) {
      g.appendChild(el("path", {
        d: `M ${x} 26 q -8 -26 1 -43 M ${x + 7} 24 q -2 -23 8 -37`,
        fill: "none", stroke: "#527f4a", "stroke-width": 4,
        "stroke-linecap": "round",
      }));
    }
  },

  fence(g) {
    for (let i = -2; i <= 2; i += 1) {
      g.appendChild(el("rect", {
        x: i * 36 - 5, y: -32, width: 10, height: 67,
        fill: "#c9a875", rx: 2,
      }));
    }
    for (const y of [-17, 9]) {
      g.appendChild(el("rect", {
        x: -96, y, width: 192, height: 9,
        fill: "#dfc493", rx: 3,
      }));
    }
  },
};

function cloud(x, y, scale = 1) {
  const g = el("g", {
    transform: `translate(${x} ${y}) scale(${scale})`,
    opacity: .84,
  });
  for (const [cx, cy, r] of [
    [-28, 5, 17], [-8, -4, 24], [18, 2, 20], [38, 8, 13],
  ]) {
    g.appendChild(el("circle", { cx, cy, r, fill: "#ffffff" }));
  }
  return g;
}

function drawPicture(picture) {
  layers.picture.replaceChildren();

  layers.picture.appendChild(el("rect", {
    x: 0, y: 0, width: PAGE_W, height: PAGE_H,
    fill: "url(#sky)",
  }));

  layers.picture.appendChild(cloud(230, 92, 1.05));
  layers.picture.appendChild(cloud(680, 118, .72));

  layers.picture.appendChild(el("circle", {
    cx: 878, cy: 85, r: 43, fill: "#f7d873", opacity: .94,
  }));

  layers.picture.appendChild(el("path", {
    d: "M 0 360 Q 150 275 320 350 Q 480 250 660 345 Q 825 275 1000 338 L 1000 640 L 0 640 Z",
    fill: "#b9d79b",
  }));
  layers.picture.appendChild(el("path", {
    d: "M 0 390 Q 190 335 380 395 Q 605 315 1000 388 L 1000 640 L 0 640 Z",
    fill: "url(#grass)",
  }));

  const flowers = [
    [360, 490], [410, 542], [601, 475], [685, 535], [895, 480],
    [85, 522], [126, 570], [520, 586], [760, 445],
  ];
  for (const [x, y] of flowers) {
    const g = el("g", { transform: `translate(${x} ${y})`, opacity: .82 });
    g.appendChild(el("circle", { r: 4.5, fill: "#fff4d6" }));
    g.appendChild(el("circle", { cx: -4, cy: 0, r: 2.6, fill: "#f6a9bd" }));
    g.appendChild(el("circle", { cx: 4, cy: 0, r: 2.6, fill: "#f6a9bd" }));
    g.appendChild(el("circle", { cx: 0, cy: -4, r: 2.6, fill: "#f6a9bd" }));
    layers.picture.appendChild(g);
  }

  for (const feature of picture.features || []) {
    const g = el("g", {
      transform: `translate(${feature.x * PAGE_W} ${feature.y * PAGE_H})`,
    });
    (PICTURE[feature.id] || (() => {}))(g);
    layers.picture.appendChild(g);
  }
}

// --------------------------------------------------------------- stickers

const ART = {
  cow(g) {
    g.appendChild(el("ellipse", {
      cx: -2, cy: 1, rx: 43, ry: 28,
      fill: "#fffdfa", stroke: "#383632", "stroke-width": 2.5,
    }));
    g.appendChild(el("ellipse", {
      cx: -17, cy: -7, rx: 14, ry: 10, fill: "#393733",
    }));
    g.appendChild(el("ellipse", {
      cx: 16, cy: 9, rx: 11, ry: 8, fill: "#393733",
    }));
    g.appendChild(el("circle", {
      cx: 36, cy: -15, r: 15,
      fill: "#fffdfa", stroke: "#383632", "stroke-width": 2.5,
    }));
    g.appendChild(el("ellipse", {
      cx: 47, cy: -10, rx: 8, ry: 6,
      fill: "#e8b6a5", stroke: "#383632", "stroke-width": 1.6,
    }));
    g.appendChild(el("circle", { cx: 39, cy: -19, r: 2.4, fill: "#282725" }));
    for (const dx of [-27, -9, 10, 27]) {
      g.appendChild(el("rect", {
        x: dx, y: 23, width: 7, height: 18,
        rx: 2, fill: "#3a3834",
      }));
    }
  },

  butterfly(g) {
    g.appendChild(el("ellipse", {
      cx: -15, cy: -10, rx: 17, ry: 21,
      fill: "#e99bc3", stroke: "#b96393", "stroke-width": 1.8,
    }));
    g.appendChild(el("ellipse", {
      cx: 15, cy: -10, rx: 17, ry: 21,
      fill: "#e99bc3", stroke: "#b96393", "stroke-width": 1.8,
    }));
    g.appendChild(el("ellipse", {
      cx: -12, cy: 13, rx: 13, ry: 15,
      fill: "#f4bfd8", stroke: "#b96393", "stroke-width": 1.8,
    }));
    g.appendChild(el("ellipse", {
      cx: 12, cy: 13, rx: 13, ry: 15,
      fill: "#f4bfd8", stroke: "#b96393", "stroke-width": 1.8,
    }));
    g.appendChild(el("rect", {
      x: -3, y: -23, width: 6, height: 46, rx: 3, fill: "#5a4634",
    }));
    g.appendChild(el("path", {
      d: "M -2 -21 q -11 -15 -18 -9 M 2 -21 q 11 -15 18 -9",
      fill: "none", stroke: "#5a4634", "stroke-width": 1.8,
      "stroke-linecap": "round",
    }));
    for (const x of [-15, 15]) {
      g.appendChild(el("circle", { cx: x, cy: -9, r: 4, fill: "#f7d66e" }));
    }
  },

  duck(g) {
    g.appendChild(el("ellipse", {
      cx: -3, cy: 7, rx: 31, ry: 22,
      fill: "#fffdf6", stroke: "#c09a2c", "stroke-width": 2.2,
    }));
    g.appendChild(el("circle", {
      cx: 23, cy: -14, r: 15,
      fill: "#fffdf6", stroke: "#c09a2c", "stroke-width": 2.2,
    }));
    g.appendChild(el("path", {
      d: "M 35 -13 l 19 5 l -19 7 z",
      fill: "#eda43a", stroke: "#c27b24", "stroke-width": 1.2,
      "stroke-linejoin": "round",
    }));
    g.appendChild(el("circle", { cx: 27, cy: -18, r: 2.4, fill: "#34322f" }));
    g.appendChild(el("path", {
      d: "M -16 3 q 15 -12 28 2 q -14 10 -28 -2 z",
      fill: "#f0eee7", stroke: "#c09a2c", "stroke-width": 1.5,
    }));
  },

  hen(g) {
    g.appendChild(el("ellipse", {
      cx: 0, cy: 5, rx: 28, ry: 23,
      fill: "#e9c69a", stroke: "#9e7045", "stroke-width": 2.2,
    }));
    g.appendChild(el("circle", {
      cx: 18, cy: -16, r: 13,
      fill: "#e9c69a", stroke: "#9e7045", "stroke-width": 2.2,
    }));
    g.appendChild(el("path", {
      d: "M 11 -29 q 5 -9 10 0 q 5 -8 9 1 z",
      fill: "#c64d42",
    }));
    g.appendChild(el("path", {
      d: "M 29 -14 l 13 3 l -13 5 z", fill: "#eea33b",
    }));
    g.appendChild(el("circle", { cx: 22, cy: -19, r: 2.2, fill: "#34322f" }));
    g.appendChild(el("path", {
      d: "M -27 0 q -14 7 -5 18 q 12 -1 14 -11 z",
      fill: "#d5aa79", stroke: "#9e7045", "stroke-width": 1.4,
    }));
    for (const dx of [-7, 8]) {
      g.appendChild(el("rect", {
        x: dx, y: 25, width: 4, height: 12, rx: 2, fill: "#eea33b",
      }));
    }
  },
};

function installStickerPaper(targetSvg, id) {
  const defs = el("defs");
  const filter = el("filter", {
    id, x: "-45%", y: "-45%", width: "190%", height: "190%",
    "color-interpolation-filters": "sRGB",
  });
  filter.appendChild(el("feMorphology", {
    in: "SourceAlpha", operator: "dilate", radius: 6, result: "expanded",
  }));
  filter.appendChild(el("feFlood", {
    "flood-color": "#d7d0c5", result: "edge-color",
  }));
  filter.appendChild(el("feComposite", {
    in: "edge-color", in2: "expanded", operator: "in", result: "edge-shape",
  }));
  filter.appendChild(el("feOffset", {
    in: "edge-shape", dy: 2.5, result: "paper-edge",
  }));
  filter.appendChild(el("feFlood", {
    "flood-color": "#fffef9", result: "paper-color",
  }));
  filter.appendChild(el("feComposite", {
    in: "paper-color", in2: "expanded", operator: "in", result: "paper",
  }));
  const merge = el("feMerge");
  merge.appendChild(el("feMergeNode", { in: "paper-edge" }));
  merge.appendChild(el("feMergeNode", { in: "paper" }));
  merge.appendChild(el("feMergeNode", { in: "SourceGraphic" }));
  filter.appendChild(merge);
  defs.appendChild(filter);
  targetSvg.appendChild(defs);
}

function stickerNode(kind, cls = "sticker", grabbable = false, filterId = "sticker-paper") {
  const g = el("g", { class: cls });

  if (grabbable) {
    g.appendChild(el("circle", {
      r: 56, fill: "transparent", class: "hit", "pointer-events": "all",
    }));
  }

  const art = el("g", { class: "art" });
  const paper = el("g", { class: "paper", filter: `url(#${filterId})` });
  (ART[kind] || (() => {}))(paper);
  art.appendChild(paper);
  g.appendChild(art);
  return g;
}

function miniature(kind) {
  const mini = el("svg", { viewBox: "-66 -66 132 132", "aria-hidden": "true" });
  const filterId = `paper-${kind}-${++seq}`;
  installStickerPaper(mini, filterId);
  mini.appendChild(stickerNode(kind, "", false, filterId));
  return mini;
}

function drawStickers(stickers) {
  layers.stickers.replaceChildren();

  for (const sticker of stickers) {
    const node = stickerNode(sticker.definition, "sticker", true);
    node.setAttribute("data-id", sticker.id);
    node.setAttribute("transform",
      `translate(${sticker.x * PAGE_W} ${sticker.y * PAGE_H})`);
    node.setAttribute("tabindex", "0");
    node.setAttribute("role", "button");
    node.setAttribute("aria-label",
      `${sticker.definition} sticker. Drag to move. Double tap to bring to life.`);

    if (sticker.animation && sticker.animation !== "none") {
      node.classList.add("alive");
      node.setAttribute("data-alive", sticker.animation);
    }

    node.addEventListener("pointerdown", (event) => grabPlaced(event, sticker));
    node.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        send("/api/animate", {
          sticker: sticker.id,
          command_id: nextId("anim-key"),
        });
      }
    });

    layers.stickers.appendChild(node);
  }
}

function drawTray(definitions) {
  const signature = definitions.map((item) => item.id).join("|");
  if (signature === traySignature && trayItems.childElementCount) return;

  traySignature = signature;
  trayItems.replaceChildren();

  for (const definition of definitions) {
    const button = document.createElement("button");
    button.className = "tray-sticker";
    button.type = "button";
    button.setAttribute("role", "listitem");
    button.setAttribute("aria-label", "Add a " + definition.id);
    button.title = definition.id;
    button.appendChild(miniature(definition.id));
    button.addEventListener("pointerdown",
      (event) => grabFromTray(event, definition.id));
    trayItems.appendChild(button);
  }

  const add = document.createElement("button");
  add.className = "tray-add";
  add.type = "button";
  add.textContent = "+";
  add.setAttribute("aria-label", "Open the sticker sheet");
  add.addEventListener("click", () => openSheet("stickers"));
  trayItems.appendChild(add);
}

// ---------------------------------------------------------------- render

function render() {
  if (!state) return;

  drawPicture(state.picture);
  drawStickers(state.stickers);
  drawTray(state.definitions);

  if (worldNote) {
    const publicDemo = world.name === "public mechanical";
    worldNote.hidden = !publicDemo;
    worldNote.textContent = publicDemo
      ? "Public demo: animations are mechanical. No Omega/Jev agent runtime is connected."
      : "";
  }

  if (DEV) {
    dev.mode.textContent = world.name;
    dev.revision.textContent = state.revision;
    dev.principal.textContent = state.principal;
  }
}

function speak(message) {
  status.textContent = "";
  requestAnimationFrame(() => { status.textContent = message; });
}

// ---------------------------------------------------------------- input

function pageFraction(event) {
  const ctm = svg.getScreenCTM();
  if (!ctm) return { x: .5, y: .5 };

  const point = new DOMPoint(event.clientX, event.clientY)
    .matrixTransform(ctm.inverse());

  const clamp = (value) => Math.min(Math.max(value, 0), 1);
  return {
    x: clamp(point.x / PAGE_W),
    y: clamp(point.y / PAGE_H),
  };
}

function overPage(event) {
  const ctm = svg.getScreenCTM();
  if (!ctm) return false;
  const point = new DOMPoint(event.clientX, event.clientY)
    .matrixTransform(ctm.inverse());
  return point.x >= 0 && point.x <= PAGE_W &&
         point.y >= 0 && point.y <= PAGE_H;
}

function overTray(event) {
  const box = hotbar.getBoundingClientRect();
  return event.clientX >= box.left &&
         event.clientX <= box.right &&
         event.clientY >= box.top &&
         event.clientY <= box.bottom;
}

async function tapSticker(sticker) {
  const now = performance.now();
  const isDouble = lastTap.id === sticker.id && now - lastTap.at <= 380;

  if (!isDouble) {
    lastTap = { id: sticker.id, at: now };
    return;
  }

  lastTap = { id: null, at: 0 };
  await send("/api/animate", {
    sticker: sticker.id,
    command_id: nextId("anim"),
  });
}

function grabPlaced(event, sticker) {
  if (pendingDefinition) return;

  event.preventDefault();
  event.stopPropagation();

  const node = event.currentTarget;
  const startedAt = performance.now();
  const startX = event.clientX;
  const startY = event.clientY;
  let moved = false;

  node.classList.add("held");
  try { node.setPointerCapture(event.pointerId); } catch (_) {}

  const cleanup = () => {
    node.removeEventListener("pointermove", onMove);
    node.removeEventListener("pointerup", onUp);
    node.removeEventListener("pointercancel", onCancel);
    node.classList.remove("held");
    hotbar.classList.remove("open");
  };

  const onMove = (moveEvent) => {
    const distance = Math.hypot(
      moveEvent.clientX - startX,
      moveEvent.clientY - startY
    );
    if (distance > 7) moved = true;
    if (!moved) return;

    const point = pageFraction(moveEvent);
    node.setAttribute("transform",
      `translate(${point.x * PAGE_W} ${point.y * PAGE_H})`);
    hotbar.classList.toggle("open", overTray(moveEvent));
  };

  const onCancel = () => {
    cleanup();
    render();
  };

  const onUp = async (upEvent) => {
    cleanup();

    if (overTray(upEvent) && moved) {
      await send("/api/remove", {
        sticker: sticker.id,
        command_id: nextId("remove"),
      });
      speak(sticker.definition + " removed");
      return;
    }

    if (!moved && performance.now() - startedAt < 520) {
      render();
      await tapSticker(sticker);
      return;
    }

    await send("/api/propose-move", {
      sticker: sticker.id,
      command_id: nextId("move"),
      point: pageFraction(upEvent),
    });
  };

  node.addEventListener("pointermove", onMove);
  node.addEventListener("pointerup", onUp);
  node.addEventListener("pointercancel", onCancel);
}

function grabFromTray(event, kind) {
  event.preventDefault();

  const button = event.currentTarget;
  try { button.setPointerCapture(event.pointerId); } catch (_) {}

  const ghost = document.createElement("div");
  ghost.id = "ghost";
  const mini = miniature(kind);
  mini.setAttribute("width", "100%");
  mini.setAttribute("height", "100%");
  ghost.appendChild(mini);
  document.body.appendChild(ghost);

  const placeGhost = (moveEvent) => {
    ghost.style.left = moveEvent.clientX + "px";
    ghost.style.top = moveEvent.clientY + "px";
  };
  placeGhost(event);

  const cleanup = () => {
    button.removeEventListener("pointermove", onMove);
    button.removeEventListener("pointerup", onUp);
    button.removeEventListener("pointercancel", onCancel);
    ghost.remove();
  };

  const onMove = (moveEvent) => placeGhost(moveEvent);

  const onCancel = () => cleanup();

  const onUp = async (upEvent) => {
    cleanup();
    if (!overPage(upEvent) || overTray(upEvent)) return;

    await send("/api/place", {
      asset: kind,
      command_id: nextId("place"),
      point: pageFraction(upEvent),
    });
    speak(kind + " placed");
  };

  button.addEventListener("pointermove", onMove);
  button.addEventListener("pointerup", onUp);
  button.addEventListener("pointercancel", onCancel);
}

// Sticker-sheet selection is a two-step digital analogue of peel + press:
// choose the design, then touch the page where it belongs.
function chooseSticker(kind) {
  pendingDefinition = kind;
  closeSheets();
  svg.classList.add("placing");
  speak("Tap the page to place the " + kind);
}

function clearPlacement() {
  pendingDefinition = null;
  placementPreview = null;
  layers.placement.replaceChildren();
  svg.classList.remove("placing");
}

function showPlacementPreview(event) {
  if (!pendingDefinition) return;

  const point = pageFraction(event);
  if (!placementPreview) {
    placementPreview = stickerNode(
      pendingDefinition,
      "placement-preview",
      false
    );
    layers.placement.replaceChildren(placementPreview);
  }
  placementPreview.setAttribute("transform",
    `translate(${point.x * PAGE_W} ${point.y * PAGE_H})`);
}

svg.addEventListener("pointerdown", (event) => {
  if (!pendingDefinition) return;
  event.preventDefault();
  event.stopPropagation();
  try { svg.setPointerCapture(event.pointerId); } catch (_) {}
  showPlacementPreview(event);
}, true);

svg.addEventListener("pointermove", (event) => {
  if (!pendingDefinition) return;
  showPlacementPreview(event);
}, true);

svg.addEventListener("pointerup", async (event) => {
  if (!pendingDefinition) return;

  event.preventDefault();
  event.stopPropagation();

  const kind = pendingDefinition;
  const point = pageFraction(event);
  clearPlacement();

  await send("/api/place", {
    asset: kind,
    command_id: nextId("sheet-place"),
    point,
  });
  speak(kind + " placed");
}, true);

svg.addEventListener("pointercancel", () => {
  if (pendingDefinition) {
    layers.placement.replaceChildren();
    placementPreview = null;
  }
}, true);

svg.addEventListener("contextmenu", (event) => event.preventDefault());

// ------------------------------------------------------------------ wire

async function send(path, body) {
  body.based_on_revision = state ? state.revision : null;

  let payload;
  try {
    payload = await world.send(path, body);
  } catch (error) {
    console.error(error);
    try { await reload(); } catch (_) {}
    if (DEV) {
      dev.verdict.className = "verdict rejected";
      dev.verdict.textContent = "world unavailable";
    }
    speak("StickerBook could not reach the world");
    return;
  }

  if (payload.state) state = payload.state;
  render();

  const receipt = payload.receipt;
  if (receipt && !receipt.accepted && receipt.object) {
    const node = layers.stickers.querySelector(
      `[data-id="${CSS.escape(receipt.object)}"]`
    );
    if (node) {
      node.classList.add("refused");
      setTimeout(() => node.classList.remove("refused"), 320);
    }
  }

  if (DEV) showVerdict(payload);
}

async function reload() {
  state = await world.state();
  render();
  if (DEV) await refreshReceipts();
}

// ------------------------------------------------------------ developer

function showVerdict(payload) {
  const receipt = payload.receipt;

  if (!receipt) {
    dev.verdict.className = "verdict rejected";
    dev.verdict.textContent = `refused — ${payload.error || "invalid request"}`;
  } else {
    dev.verdict.className =
      "verdict " + (receipt.accepted ? "accepted" : "rejected");
    dev.verdict.textContent = receipt.accepted
      ? `accepted — ${receipt.action} ${receipt.object || ""} (rev ${receipt.resultRevision})`
      : `refused — ${receipt.reason}; nothing changed`;
  }

  refreshReceipts();
}

async function refreshReceipts() {
  const payload = await world.receipts();
  dev.receipts.replaceChildren();

  for (const receipt of (payload.receipts || []).slice().reverse()) {
    const item = document.createElement("li");
    const mark = document.createElement("span");
    mark.className = receipt.accepted ? "ok" : "no";
    mark.textContent = receipt.accepted ? "ACCEPT " : "REFUSE ";
    item.append(
      mark,
      document.createTextNode(
        `${receipt.action} ${receipt.object || ""} → ${receipt.reason} (rev ${receipt.resultRevision})`
      )
    );
    dev.receipts.appendChild(item);
  }
}

// --------------------------------------------------------------- sheets

function openSheet(which) {
  clearPlacement();

  for (const [name, node] of Object.entries(sheets)) {
    node.hidden = name !== which;
  }

  if (which === "book") drawBook();
  if (which === "stickers") drawStickerLibrary();
}

function closeSheets() {
  for (const node of Object.values(sheets)) {
    node.hidden = true;
  }
}

async function drawBook() {
  const book = await world.book();
  document.getElementById("book-title").textContent = book.title;
  document.getElementById("book-subtitle").textContent = book.subtitle;

  const list = document.getElementById("page-list");
  list.replaceChildren();

  for (const page of book.pages) {
    const card = document.createElement("button");
    card.className =
      "card" + (state?.page?.id === page.id ? " current" : "");
    card.type = "button";
    card.innerHTML = "<strong></strong><span></span>";
    card.querySelector("strong").textContent = page.name;
    card.querySelector("span").textContent = page.summary;
    card.addEventListener("click", closeSheets);
    list.appendChild(card);
  }

  const soon = document.getElementById("page-soon");
  soon.replaceChildren();

  for (const item of book.coming || []) {
    const card = document.createElement("button");
    card.className = "card soon";
    card.type = "button";
    card.disabled = true;
    card.textContent = item.label;
    soon.appendChild(card);
  }
}

function drawStickerLibrary() {
  const list = document.getElementById("sticker-list");
  list.replaceChildren();

  for (const definition of state?.definitions || []) {
    const card = document.createElement("button");
    card.className = "card sticker-card";
    card.type = "button";
    card.appendChild(miniature(definition.id));

    const label = document.createElement("span");
    label.textContent = definition.id;
    card.appendChild(label);

    card.addEventListener("click", () => chooseSticker(definition.id));
    list.appendChild(card);
  }
}

// --------------------------------------------------------------- boot

document.getElementById("menu-btn")
  .addEventListener("click", () => openSheet("book"));

for (const button of document.querySelectorAll("[data-close]")) {
  button.addEventListener("click", closeSheets);
}

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;

  if (pendingDefinition) {
    clearPlacement();
    speak("Sticker placement cancelled");
  } else {
    closeSheets();
  }
});

if (DEV) dev.panel.hidden = false;

reload().catch((error) => {
  console.error(error);

  // A localhost file/server without the Python bridge is still useful as a
  // visual preview. We fall back only during boot, never mid-session.
  if (world === kernelWorld) {
    world = createMechanicalWorld();
    reload();
  }
});
