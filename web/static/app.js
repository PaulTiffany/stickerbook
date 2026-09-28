// StickerBook front end.
//
// Child-facing navigation:
//   cover -> page gallery -> page
//                          -> page creator
//
// On a page, the sticker library floats above the world. The hotbar is the
// child's working sticker sheet: library -> sheet -> page.
//
// Two world adapters remain intentionally separate:
//   localhost       -> Python authority kernel decides
//   GitHub Pages    -> deterministic in-memory mechanical demo
//
// The public adapter contains no live agent, model call, credential, kernel,
// Python bridge, or privileged backend.

const PAGE_W = 1000;
const PAGE_H = 640;
const QUERY = new URLSearchParams(location.search);
const DEV = QUERY.get("dev") === "1";
const FORCE_MECHANICAL = QUERY.get("mechanical") === "1";
const LOCAL_HOST = ["localhost", "127.0.0.1", "::1"].includes(location.hostname);

const screens = {
  cover: document.getElementById("cover-screen"),
  gallery: document.getElementById("gallery-screen"),
  creator: document.getElementById("page-creator-screen"),
  play: document.getElementById("play-screen"),
};

const svg = document.getElementById("page");
const layers = {
  picture: document.getElementById("picture"),
  stickers: document.getElementById("stickers"),
  placement: document.getElementById("placement-layer"),
};

const coverPicture = document.getElementById("cover-picture");
const coverDecor = document.getElementById("cover-decor");
const coverTitle = document.querySelector(".cover-title");
const hotbar = document.getElementById("hotbar");
const trayZone = document.getElementById("tray-zone");
const trayItems = document.getElementById("tray-items");
const trayEmpty = document.getElementById("tray-empty");
const stickerOverlay = document.getElementById("sticker-overlay");
const stickerLibraryPanel = document.querySelector(".sticker-library-panel");
const stickerLibraryGrid = document.getElementById("sticker-library-grid");
const stickerLibraryView = document.getElementById("sticker-library-view");
const stickerMakerView = document.getElementById("sticker-maker-view");
const adultPanel = document.getElementById("adult-panel");
const voiceOrb = document.getElementById("voice-orb");
const voiceOrbState = document.getElementById("voice-orb-state");
const voiceEnable = document.getElementById("voice-enable");
const agentAdultControls = document.getElementById("agent-adult-controls");
const voicePrivacyNote = document.getElementById("voice-privacy-note");
const adultChatInput = document.getElementById("adult-chat-input");
const adultChatSend = document.getElementById("adult-chat-send");
const adultChatReply = document.getElementById("adult-chat-reply");
const status = document.getElementById("a11y-status");

const dev = {
  panel: document.getElementById("dev"),
  mode: document.getElementById("world-mode"),
  revision: document.getElementById("revision"),
  principal: document.getElementById("principal"),
  verdict: document.getElementById("verdict"),
  receipts: document.getElementById("receipts"),
};

let state = null;
let assetManifest = null;
let seq = 0;
let pendingDefinition = null;
let placementPreview = null;
let lastTap = { id: null, at: 0 };
let hotbarKinds = [];
let bookCache = null;
let pagePreviewUrl = null;
let pageUploadDraft = null;
let stickerPreviewUrl = null;
let voiceEnabled = false;
let voiceRecognition = null;
let voiceBusy = false;

const nextId = (kind) => "ui-" + kind + "-" + Date.now() + "-" + (++seq);
const copy = (value) => JSON.parse(JSON.stringify(value));

const el = (name, attrs = {}) => {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  for (const [key, value] of Object.entries(attrs)) {
    node.setAttribute(key, value);
  }
  return node;
};

async function loadAssetManifest() {
  try {
    const res = await fetch("static/assets/manifest.json", { cache: "no-store" });
    if (!res.ok) throw new Error("asset manifest: HTTP " + res.status);
    const manifest = await res.json();
    if (!manifest || ![1, 2, 3].includes(manifest.version)) {
      throw new Error("unsupported asset manifest");
    }
    assetManifest = manifest;
  } catch (error) {
    console.warn("StickerBook asset manifest unavailable; using procedural fallbacks.", error);
    assetManifest = null;
  }
}

function stickerAsset(kind) {
  return assetManifest &&
    assetManifest.stickers &&
    assetManifest.stickers[kind] || null;
}

function stickerClip(kind, requestedClip) {
  const asset = stickerAsset(kind);
  if (!asset) return null;

  // Manifest v1 compatibility: a single source behaves like an idle clip.
  if (asset.src) {
    return {
      frames: [asset.src],
      loop: false,
      motion: asset.animation || null,
    };
  }

  const clips = asset.clips || {};
  const defaultName = asset.default_clip || "idle";
  const name = requestedClip && requestedClip !== "none"
    ? requestedClip
    : defaultName;

  return clips[name] || clips[defaultName] || null;
}

function clipImage(clip) {
  if (!clip || !Array.isArray(clip.frames) || !clip.frames.length) return null;

  const image = svgImage(clip.frames[0], -72, -72, 144, 144);

  if (clip.frames.length > 1) {
    image.dataset.stickerFramePlayer = "1";
    image._stickerFrames = clip.frames.slice();
    image._stickerFrameMs = Math.max(40, Number(clip.frame_ms) || 120);
    image._stickerLoop = clip.loop !== false;
    image.dataset.stickerFrameIndex = "0";
  }

  return image;
}

let frameTickerStarted = false;

function startStickerFrameTicker() {
  if (frameTickerStarted) return;
  frameTickerStarted = true;

  const reduced = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const tick = (now) => {
    if (!reduced) {
      for (const image of document.querySelectorAll(
        'image[data-sticker-frame-player="1"]'
      )) {
        const frames = image._stickerFrames || [];
        if (frames.length < 2) continue;

        const ms = image._stickerFrameMs || 120;
        let index = Math.floor(now / ms);

        if (image._stickerLoop) {
          index %= frames.length;
        } else {
          index = Math.min(index, frames.length - 1);
        }

        if (String(index) !== image.dataset.stickerFrameIndex) {
          image.setAttribute("href", frames[index]);
          image.dataset.stickerFrameIndex = String(index);
        }
      }
    }

    requestAnimationFrame(tick);
  };

  requestAnimationFrame(tick);
}

function pageAsset(pageId) {
  return assetManifest &&
    assetManifest.pages &&
    assetManifest.pages[pageId] || null;
}

function visualViewportBox() {
  const viewport = window.visualViewport;
  const width = viewport && Number.isFinite(viewport.width)
    ? viewport.width
    : (window.innerWidth || document.documentElement.clientWidth || PAGE_W);
  const height = viewport && Number.isFinite(viewport.height)
    ? viewport.height
    : (window.innerHeight || document.documentElement.clientHeight || PAGE_H);

  return { width, height };
}

function syncViewportCssVars() {
  const { width, height } = visualViewportBox();
  document.documentElement.style.setProperty("--app-vw", width + "px");
  document.documentElement.style.setProperty("--app-vh", height + "px");
}

function portraitViewport() {
  const { width, height } = visualViewportBox();
  return height > width;
}

function coverViewportClass() {
  const { width, height } = visualViewportBox();
  const ratio = width / Math.max(height, 1);

  if (height > width) return "portrait";

  // Short/wide browser rectangles need their own composition class even
  // when they come from a desktop window rather than a phone.
  if (height <= 560 || ratio >= 2.35) return "landscape_phone";

  return "desktop";
}

function visualVariant(asset, orientation) {
  if (!asset) return null;

  const wanted = orientation || (portraitViewport() ? "portrait" : "landscape");
  const variants = asset.variants || {};

  if (variants[wanted] && variants[wanted].src) {
    return variants[wanted];
  }

  if (variants.landscape && variants.landscape.src) {
    return variants.landscape;
  }

  if (variants.portrait && variants.portrait.src) {
    return variants.portrait;
  }

  // Manifest v1/v2 compatibility.
  if (asset.src) {
    return {
      src: asset.src,
      width: Number(asset.width) || PAGE_W,
      height: Number(asset.height) || PAGE_H,
      thumbnail: asset.thumbnail || null,
    };
  }

  return null;
}

function coverVariant() {
  const cover = assetManifest && assetManifest.cover;
  if (!cover) return null;

  const variants = cover.variants || {};
  const wanted = coverViewportClass();

  if (variants[wanted] && variants[wanted].src) {
    return variants[wanted];
  }

  return visualVariant(cover, wanted === "portrait" ? "portrait" : "landscape");
}

function pageVariant(pageId, orientation) {
  return visualVariant(pageAsset(pageId), orientation);
}

function pageMetrics(pageId) {
  const variant = pageVariant(pageId);
  return {
    width: Number(variant && variant.width) || PAGE_W,
    height: Number(variant && variant.height) || PAGE_H,
  };
}

function cssAssetUrl(src) {
  if (!src) return "none";
  return 'url("' + String(src)
    .replace(/\\/g, "\\\\")
    .replace(/"/g, '\\"') + '")';
}

function activePageMetrics() {
  return pageMetrics(state && state.page && state.page.id || "farm");
}

function applyActivePageViewport() {
  const metrics = activePageMetrics();
  svg.setAttribute("viewBox", "0 0 " + metrics.width + " " + metrics.height);
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  svg.style.setProperty("--page-aspect", metrics.width + " / " + metrics.height);
}

function svgImage(src, x, y, width, height) {
  return el("image", {
    href: src,
    x, y, width, height,
    preserveAspectRatio: "xMidYMid meet",
  });
}

// --------------------------------------------------------------- adapters

const DEMO_BOOK = {
  title: "StickerBook",
  subtitle: "Pages",
  pages: [
    {
      id: "farm",
      name: "The Farm",
      summary: "Barns, fields and farm animals.",
    },
  ],
  coming: [],
};

function mechanicalBook() {
  const pages = assetManifest && assetManifest.pages || {};
  const entries = Object.entries(pages);

  if (!entries.length) return copy(DEMO_BOOK);

  return {
    title: "StickerBook",
    subtitle: "Pages",
    pages: entries.map(([id, page]) => ({
      id,
      name: page.name || id.replace(/[-_]/g, " "),
      summary: page.summary || "",
    })),
    coming: [],
  };
}

const DEMO_SEED = {
  revision: 2,
  principal: "human:player",
  page: { id: "farm", name: "The Farm" },
  capabilities: {
    creator_agent: false,
    conversational_agent: false,
    page_image_creator: false,
    voice: false,
  },
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
    { id: "bird", animations: ["none", "flutter"] },
    { id: "butterfly", animations: ["none", "flutter"] },
    { id: "frog", animations: ["none", "hop"] },
    { id: "fish", animations: ["none", "swim"] },
    { id: "flower", animations: ["none", "sway"] },
    { id: "cloud", animations: ["none", "drift"] },
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
      x: 0.58,
      y: 0.34,
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
  const pageStickers = {
    farm: copy(worldState.stickers),
  };

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

  const rememberPage = () => {
    if (worldState.page && worldState.page.id) {
      pageStickers[worldState.page.id] = copy(worldState.stickers);
    }
  };

  const commit = (action, object, mutate) => {
    worldState.revision += 1;
    mutate(worldState.revision);
    rememberPage();

    const receipt = {
      accepted: true,
      action,
      object,
      reason: "mechanical-demo",
      resultRevision: worldState.revision,
    };
    receipts.push(receipt);
    receipts = receipts.slice(-24);
    return { ok: true, receipt: copy(receipt), state: copy(worldState) };
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
    return { ok: true, receipt: copy(receipt), state: copy(worldState) };
  };

  return {
    name: "public mechanical",

    async state() {
      return copy(worldState);
    },

    async book() {
      return copy(mechanicalBook());
    },

    async selectPage(pageId) {
      const page = mechanicalBook().pages.find((item) => item.id === pageId);
      if (!page) {
        return { ok: false, error: "unknown-page", state: copy(worldState) };
      }

      rememberPage();
      worldState.page = { id: page.id, name: page.name };
      worldState.stickers = copy(pageStickers[page.id] || []);
      return { ok: true, state: copy(worldState) };
    },

    async receipts() {
      return { receipts: copy(receipts) };
    },

    async creatorDraft() {
      return { ok: false, error: "creator-agent-unavailable" };
    },

    async pageImageDraft() {
      return { ok: false, error: "page-image-creator-unavailable" };
    },

    async converse() {
      return { ok: false, error: "conversational-agent-unavailable" };
    },

    async send(path, body) {
      if (path === "/api/place") {
        const def = definition(body.asset);
        if (!def || !pointOkay(body.point)) {
          return refuse("add-own-sticker", null, "invalid-demo-proposal");
        }
        const id = body.asset + "-demo-" + (++instanceSeq);
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
        const alive = (def && def.animations || []).find(
          (name) => name !== "none"
        );
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
    if (!res.ok) throw new Error("state: HTTP " + res.status);
    return res.json();
  },

  async book() {
    const res = await fetch("/api/book", { cache: "no-store" });
    if (!res.ok) throw new Error("book: HTTP " + res.status);
    return res.json();
  },

  async selectPage(pageId) {
    const current = await this.state();
    if (current.page && current.page.id === pageId) {
      return { ok: true, state: current };
    }
    return {
      ok: false,
      error: "page-not-governed",
      state: current,
    };
  },

  async receipts() {
    const res = await fetch("/api/receipts", { cache: "no-store" });
    if (!res.ok) throw new Error("receipts: HTTP " + res.status);
    return res.json();
  },

  async creatorDraft(body) {
    const res = await fetch("/api/creator/draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return res.json();
  },

  async pageImageDraft(file) {
    const res = await fetch("/api/creator/page-image", {
      method: "POST",
      headers: {
        "Content-Type": file.type,
        "X-StickerBook-Filename": encodeURIComponent(file.name || "page.png"),
      },
      body: file,
    });
    return res.json();
  },

  async converse(body) {
    const res = await fetch("/api/agent/converse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return res.json();
  },

  async send(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return res.json();
  },
};

let world = (!FORCE_MECHANICAL && LOCAL_HOST)
  ? kernelWorld
  : createMechanicalWorld();

// --------------------------------------------------------------- picture

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
    for (const item of [
      [0, -18, 47, "#53965a"],
      [-30, 4, 30, "#65a966"],
      [31, 3, 29, "#498b50"],
      [7, 12, 32, "#5da260"],
    ]) {
      g.appendChild(el("circle", {
        cx: item[0], cy: item[1], r: item[2], fill: item[3],
      }));
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
        d: "M " + x + " 26 q -8 -26 1 -43 M " + (x + 7) + " 24 q -2 -23 8 -37",
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

function cloudNode(x, y, scale, fill) {
  const g = el("g", {
    transform: "translate(" + x + " " + y + ") scale(" + scale + ")",
    opacity: .86,
  });
  for (const item of [
    [-28, 5, 17], [-8, -4, 24], [18, 2, 20], [38, 8, 13],
  ]) {
    g.appendChild(el("circle", {
      cx: item[0], cy: item[1], r: item[2], fill: fill || "#ffffff",
    }));
  }
  return g;
}

function drawScene(target, picture, mode, pageId) {
  target.replaceChildren();

  if (mode !== "cover") {
    const id = pageId || state && state.page && state.page.id || "farm";
    const variant = pageVariant(id);
    if (variant && variant.src) {
      const width = Number(variant.width) || PAGE_W;
      const height = Number(variant.height) || PAGE_H;

      if (mode === "play") {
        screens.play.style.setProperty(
          "--page-art",
          cssAssetUrl(variant.src)
        );
      }

      target.appendChild(el("image", {
        href: variant.src,
        x: 0, y: 0, width, height,
        preserveAspectRatio: "xMidYMid meet",
      }));
      return;
    }

    if (mode === "play") {
      screens.play.style.setProperty("--page-art", "none");
    }
  }

  const skyFill = mode === "cover"
    ? "url(#cover-sky)"
    : mode === "play"
      ? "url(#sky)"
      : "#bfe5f4";

  const grassFill = mode === "cover"
    ? "url(#cover-grass)"
    : mode === "play"
      ? "url(#grass)"
      : "#82b96c";

  target.appendChild(el("rect", {
    x: 0, y: 0, width: PAGE_W, height: PAGE_H, fill: skyFill,
  }));

  target.appendChild(cloudNode(210, 92, 1.05));
  target.appendChild(cloudNode(700, 112, .72));

  target.appendChild(el("circle", {
    cx: 870, cy: 84, r: 44, fill: "#f8d86f", opacity: .95,
  }));

  target.appendChild(el("path", {
    d: "M 0 365 Q 155 275 325 350 Q 495 250 665 346 Q 825 275 1000 338 L 1000 640 L 0 640 Z",
    fill: mode === "cover" ? "#b7d898" : "#b9d79b",
  }));

  target.appendChild(el("path", {
    d: "M 0 395 Q 190 335 380 397 Q 610 315 1000 390 L 1000 640 L 0 640 Z",
    fill: grassFill,
  }));

  for (const item of [
    [360, 490], [410, 542], [601, 475], [685, 535], [895, 480],
    [85, 522], [126, 570], [520, 586], [760, 445],
  ]) {
    const g = el("g", {
      transform: "translate(" + item[0] + " " + item[1] + ")",
      opacity: .82,
    });
    g.appendChild(el("circle", { r: 4.5, fill: "#fff4d6" }));
    g.appendChild(el("circle", { cx: -4, cy: 0, r: 2.6, fill: "#f6a9bd" }));
    g.appendChild(el("circle", { cx: 4, cy: 0, r: 2.6, fill: "#f6a9bd" }));
    g.appendChild(el("circle", { cx: 0, cy: -4, r: 2.6, fill: "#f6a9bd" }));
    target.appendChild(g);
  }

  for (const feature of picture.features || []) {
    const g = el("g", {
      transform: "translate(" + (feature.x * PAGE_W) + " " +
        (feature.y * PAGE_H) + ")",
    });
    (PICTURE[feature.id] || (() => {}))(g);
    target.appendChild(g);
  }
}

// --------------------------------------------------------------- sticker art

const ART = {
  bird(g) {
    g.appendChild(el("ellipse", {
      cx: 0, cy: 2, rx: 34, ry: 23,
      fill: "#2e86c6", stroke: "#185f91", "stroke-width": 2,
    }));
    g.appendChild(el("ellipse", {
      cx: 25, cy: -15, rx: 15, ry: 14,
      fill: "#4da0da", stroke: "#185f91", "stroke-width": 2,
    }));
    g.appendChild(el("ellipse", {
      cx: 12, cy: 13, rx: 23, ry: 13,
      fill: "#f4b166", opacity: .95,
    }));
    g.appendChild(el("path", {
      d: "M -7 -4 Q -50 -45 -54 -3 Q -37 17 -5 10 Z",
      fill: "#4b98d1", stroke: "#185f91", "stroke-width": 2,
    }));
    g.appendChild(el("path", {
      d: "M 38 -13 l 16 6 l -16 5 z",
      fill: "#ed8b24", stroke: "#bf6d18", "stroke-width": 1.2,
    }));
    g.appendChild(el("circle", { cx: 29, cy: -18, r: 2.5, fill: "#1c2428" }));
  },

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
      fill: "#f19a38", stroke: "#563d30", "stroke-width": 2,
    }));
    g.appendChild(el("ellipse", {
      cx: 15, cy: -10, rx: 17, ry: 21,
      fill: "#f19a38", stroke: "#563d30", "stroke-width": 2,
    }));
    g.appendChild(el("ellipse", {
      cx: -12, cy: 13, rx: 13, ry: 15,
      fill: "#f6be5e", stroke: "#563d30", "stroke-width": 2,
    }));
    g.appendChild(el("ellipse", {
      cx: 12, cy: 13, rx: 13, ry: 15,
      fill: "#f6be5e", stroke: "#563d30", "stroke-width": 2,
    }));
    g.appendChild(el("rect", {
      x: -3, y: -23, width: 6, height: 46, rx: 3, fill: "#46352b",
    }));
    g.appendChild(el("path", {
      d: "M -2 -21 q -11 -15 -18 -9 M 2 -21 q 11 -15 18 -9",
      fill: "none", stroke: "#46352b", "stroke-width": 1.8,
      "stroke-linecap": "round",
    }));
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
      d: "M 11 -29 q 5 -9 10 0 q 5 -8 9 1 z", fill: "#c64d42",
    }));
    g.appendChild(el("path", {
      d: "M 29 -14 l 13 3 l -13 5 z", fill: "#eea33b",
    }));
    g.appendChild(el("circle", { cx: 22, cy: -19, r: 2.2, fill: "#34322f" }));
  },

  frog(g) {
    g.appendChild(el("ellipse", {
      cx: 0, cy: 8, rx: 31, ry: 22,
      fill: "#7bc85c", stroke: "#407d39", "stroke-width": 2.2,
    }));
    g.appendChild(el("ellipse", {
      cx: 0, cy: -9, rx: 25, ry: 18,
      fill: "#82d264", stroke: "#407d39", "stroke-width": 2.2,
    }));
    for (const x of [-13, 13]) {
      g.appendChild(el("circle", {
        cx: x, cy: -22, r: 8, fill: "#8ddd6b",
        stroke: "#407d39", "stroke-width": 1.8,
      }));
      g.appendChild(el("circle", { cx: x, cy: -23, r: 3, fill: "#202820" }));
    }
    g.appendChild(el("path", {
      d: "M -11 -5 q 11 9 22 0",
      fill: "none", stroke: "#355f33", "stroke-width": 2,
      "stroke-linecap": "round",
    }));
    g.appendChild(el("ellipse", {
      cx: 0, cy: 10, rx: 17, ry: 11, fill: "#dff0b2",
    }));
  },

  fish(g) {
    g.appendChild(el("ellipse", {
      cx: 2, cy: 0, rx: 31, ry: 20,
      fill: "#f08a45", stroke: "#bd6031", "stroke-width": 2.2,
    }));
    g.appendChild(el("path", {
      d: "M -29 0 L -53 -20 L -50 22 Z",
      fill: "#f2a05f", stroke: "#bd6031", "stroke-width": 2,
      "stroke-linejoin": "round",
    }));
    g.appendChild(el("circle", { cx: 20, cy: -5, r: 3, fill: "#2e2d2b" }));
    g.appendChild(el("path", {
      d: "M -8 -17 q 10 -13 21 -2 M -6 17 q 10 10 18 0",
      fill: "none", stroke: "#fff4dc", "stroke-width": 3,
      "stroke-linecap": "round",
    }));
  },

  flower(g) {
    for (let i = 0; i < 8; i += 1) {
      const a = i * Math.PI / 4;
      g.appendChild(el("ellipse", {
        cx: Math.cos(a) * 18,
        cy: Math.sin(a) * 18,
        rx: 10, ry: 16,
        transform: "rotate(" + (i * 45 + 90) + " " +
          (Math.cos(a) * 18) + " " + (Math.sin(a) * 18) + ")",
        fill: "#f27c8d", stroke: "#c85669", "stroke-width": 1.3,
      }));
    }
    g.appendChild(el("circle", { r: 11, fill: "#f1c64f" }));
    g.appendChild(el("path", {
      d: "M 0 30 L 0 58 M 0 43 q -18 -10 -22 5 M 0 48 q 18 -11 23 -2",
      fill: "none", stroke: "#4b9252", "stroke-width": 5,
      "stroke-linecap": "round",
    }));
  },

  cloud(g) {
    g.appendChild(el("ellipse", {
      cx: 0, cy: 10, rx: 41, ry: 18,
      fill: "#e8f2ff", stroke: "#9bbdde", "stroke-width": 2,
    }));
    g.appendChild(el("circle", {
      cx: -20, cy: 0, r: 19, fill: "#eef6ff",
      stroke: "#9bbdde", "stroke-width": 2,
    }));
    g.appendChild(el("circle", {
      cx: 2, cy: -11, r: 25, fill: "#eef6ff",
      stroke: "#9bbdde", "stroke-width": 2,
    }));
    g.appendChild(el("circle", {
      cx: 27, cy: 2, r: 18, fill: "#eef6ff",
      stroke: "#9bbdde", "stroke-width": 2,
    }));
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

function stickerNode(kind, cls, grabbable, filterId, clipName) {
  const g = el("g", { class: cls || "sticker" });

  if (grabbable) {
    g.appendChild(el("circle", {
      r: 60, fill: "transparent", class: "hit", "pointer-events": "all",
    }));
  }

  const art = el("g", { class: "art" });
  const paper = el("g", {
    class: "paper",
    filter: "url(#" + (filterId || "sticker-paper") + ")",
  });

  const clip = stickerClip(kind, clipName);
  const image = clipImage(clip);

  if (image) {
    paper.appendChild(image);
  } else {
    (ART[kind] || ART.flower)(paper);
  }

  art.appendChild(paper);
  g.appendChild(art);
  return g;
}

function miniature(kind) {
  const mini = el("svg", { viewBox: "-72 -72 144 144", "aria-hidden": "true" });
  const filterId = "paper-" + kind + "-" + (++seq);
  installStickerPaper(mini, filterId);
  mini.appendChild(stickerNode(kind, "", false, filterId));
  return mini;
}

// ------------------------------------------------------------- cover

function drawCover() {
  const cover = assetManifest && assetManifest.cover;
  const variant = coverVariant();

  if (cover && variant && variant.src) {
    const width = Number(variant.width) || PAGE_W;
    const height = Number(variant.height) || PAGE_H;

    screens.cover.style.setProperty(
      "--cover-art",
      cssAssetUrl(variant.src)
    );

    document.getElementById("cover-scene").setAttribute(
      "viewBox",
      "0 0 " + width + " " + height
    );
    document.getElementById("cover-scene").setAttribute(
      "preserveAspectRatio",
      "xMidYMid slice"
    );

    coverPicture.replaceChildren(
      el("image", {
        href: variant.src,
        x: 0, y: 0, width, height,
        preserveAspectRatio: "xMidYMid slice",
      })
    );
    coverDecor.replaceChildren();
    if (coverTitle) coverTitle.hidden = cover.show_title === false;
    return;
  }

  if (coverTitle) coverTitle.hidden = false;
  drawScene(coverPicture, DEMO_SEED.picture, "cover");
  coverDecor.replaceChildren();

  const bird = stickerNode("bird", "cover-sticker", false, "cover-paper");
  bird.setAttribute("transform", "translate(465 295) scale(1.55) rotate(-6)");
  coverDecor.appendChild(bird);

  const frog = stickerNode("frog", "cover-sticker", false, "cover-paper");
  frog.setAttribute("transform", "translate(640 505) scale(1.1) rotate(2)");
  coverDecor.appendChild(frog);

  const butterfly = stickerNode("butterfly", "cover-sticker", false, "cover-paper");
  butterfly.setAttribute("transform", "translate(835 330) scale(.95) rotate(8)");
  coverDecor.appendChild(butterfly);
}

// ------------------------------------------------------------- gallery

function makeThumbSvg(pageId) {
  const asset = pageAsset(pageId);
  const variant = pageVariant(pageId, "landscape") || pageVariant(pageId);
  const width = Number(variant && variant.width) || PAGE_W;
  const height = Number(variant && variant.height) || PAGE_H;

  const thumb = el("svg", {
    viewBox: "0 0 " + width + " " + height,
    preserveAspectRatio: "xMidYMid slice",
    "aria-hidden": "true",
  });

  const src = variant && (
    variant.thumbnail ||
    asset && asset.thumbnail ||
    variant.src
  );

  if (src) {
    thumb.appendChild(el("image", {
      href: src,
      x: 0,
      y: 0,
      width,
      height,
      preserveAspectRatio: "xMidYMid slice",
    }));
    return thumb;
  }

  const scene = el("g");
  thumb.appendChild(scene);
  drawScene(
    scene,
    state ? state.picture : DEMO_SEED.picture,
    "thumb",
    pageId
  );
  return thumb;
}

async function drawGallery() {
  if (!bookCache) {
    try {
      bookCache = await world.book();
    } catch (error) {
      console.error(error);
      bookCache = copy(DEMO_BOOK);
    }
  }

  const gallery = document.getElementById("page-gallery");
  gallery.replaceChildren();

  for (const page of bookCache.pages || []) {
    const button = document.createElement("button");
    button.className = "page-tile";
    button.type = "button";
    button.setAttribute("aria-label", "Open " + page.name);
    button.appendChild(makeThumbSvg(page.id));

    const label = document.createElement("span");
    label.className = "page-tile-label";
    label.textContent = page.name;
    button.appendChild(label);

    button.addEventListener("click", () => {
      enterPlay(page.id);
    });

    gallery.appendChild(button);
  }

  const make = document.createElement("button");
  make.className = "page-tile new-page";
  make.type = "button";
  make.setAttribute("aria-label", "Make a new page");
  make.innerHTML =
    '<span class="new-page-inner"><span class="plus">+</span>' +
    '<strong>Make a page</strong></span>';
  make.addEventListener("click", () => showScreen("creator"));
  gallery.appendChild(make);
}

// --------------------------------------------------------------- render

function drawStickers(stickers) {
  layers.stickers.replaceChildren();

  for (const sticker of stickers) {
    const clipName = sticker.animation && sticker.animation !== "none"
      ? sticker.animation
      : null;
    const node = stickerNode(
      sticker.definition,
      "sticker",
      true,
      null,
      clipName
    );
    node.setAttribute("data-id", sticker.id);
    node.setAttribute(
      "transform",
      (() => {
        const metrics = activePageMetrics();
        return "translate(" +
          (sticker.x * metrics.width) + " " +
          (sticker.y * metrics.height) + ")";
      })()
    );
    node.setAttribute("tabindex", "0");
    node.setAttribute("role", "button");
    node.setAttribute(
      "aria-label",
      sticker.definition + " sticker. Drag to move. Double tap to bring to life."
    );

    if (sticker.animation && sticker.animation !== "none") {
      node.classList.add("alive");
      const clip = stickerClip(sticker.definition, sticker.animation);
      node.setAttribute(
        "data-alive",
        clip && clip.motion || sticker.animation
      );
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

function definitionIds() {
  return (state && state.definitions || []).map((item) => item.id);
}

function ensureHotbar() {
  const available = definitionIds();

  hotbarKinds = hotbarKinds.filter((kind) => available.includes(kind));

  if (!hotbarKinds.length) {
    const preferred = ["bird", "butterfly", "frog", "cow", "duck"];
    for (const kind of preferred) {
      if (available.includes(kind) && !hotbarKinds.includes(kind)) {
        hotbarKinds.push(kind);
      }
      if (hotbarKinds.length >= 3) break;
    }
  }

  if (!hotbarKinds.length) {
    hotbarKinds = available.slice(0, 3);
  }
}

function drawTray() {
  ensureHotbar();
  trayItems.replaceChildren();

  for (const kind of hotbarKinds) {
    const button = document.createElement("button");
    button.className = "tray-sticker";
    button.type = "button";
    button.setAttribute("role", "listitem");
    button.setAttribute("aria-label", "Place " + kind);
    button.appendChild(miniature(kind));
    button.addEventListener("pointerdown", (event) => grabFromTray(event, kind));
    trayItems.appendChild(button);
  }

  trayEmpty.hidden = hotbarKinds.length !== 0;
}

function render() {
  if (!state) return;

  applyActivePageViewport();
  drawScene(layers.picture, state.picture, "play", state.page && state.page.id);
  drawStickers(state.stickers);
  drawTray();

  if (DEV) {
    dev.mode.textContent = world.name;
    dev.revision.textContent = state.revision;
    dev.principal.textContent = state.principal;
  }

  const adultNote = document.getElementById("adult-world-note");
  adultNote.textContent = world.name === "public mechanical"
    ? "Public demo. Animations and scene changes are mechanical; no Omega/Jev runtime is connected."
    : "Local governed runtime. Browser actions are proposals; the authority kernel decides.";

  updateConversationControls();
}

function speak(message) {
  status.textContent = "";
  requestAnimationFrame(() => {
    status.textContent = message;
  });
}

// -------------------------------------------------------------- screens

function showScreen(name) {
  closeLibrary();
  clearPlacement();

  for (const [key, node] of Object.entries(screens)) {
    node.hidden = key !== name;
  }

  if (name === "gallery") {
    drawGallery();
  }

  updateConversationControls();
}

async function enterPlay(pageId) {
  try {
    const result = await world.selectPage(pageId);

    if (!result || !result.ok) {
      speak(
        world.name === "public mechanical"
          ? "That page is unavailable."
          : "That page has art, but its governed world is not connected yet."
      );
      return;
    }

    if (result.state) state = result.state;
    showScreen("play");
    render();
  } catch (error) {
    console.error(error);
    speak("That page could not be opened.");
  }
}

// --------------------------------------------------------------- input

function pageFraction(event) {
  const ctm = svg.getScreenCTM();
  if (!ctm) return { x: .5, y: .5 };

  const point = new DOMPoint(event.clientX, event.clientY)
    .matrixTransform(ctm.inverse());

  const metrics = activePageMetrics();
  const clamp = (value) => Math.min(Math.max(value, 0), 1);
  return {
    x: clamp(point.x / metrics.width),
    y: clamp(point.y / metrics.height),
  };
}

function overPage(event) {
  const ctm = svg.getScreenCTM();
  if (!ctm) return false;

  const point = new DOMPoint(event.clientX, event.clientY)
    .matrixTransform(ctm.inverse());

  const metrics = activePageMetrics();
  return point.x >= 0 && point.x <= metrics.width &&
         point.y >= 0 && point.y <= metrics.height;
}

function overTrayZone(event) {
  const box = trayZone.getBoundingClientRect();
  return event.clientX >= box.left &&
         event.clientX <= box.right &&
         event.clientY >= box.top &&
         event.clientY <= box.bottom;
}

function overRemovalZone(event) {
  const box = hotbar.getBoundingClientRect();

  // "Drag it down" is a bottom-edge gesture, not a precision drop target.
  // Once the pointer crosses the hotbar's top edge, releasing anywhere
  // farther down still means remove — including coordinates reported below
  // the bar/visual viewport while pointer capture is active.
  return event.clientY >= box.top;
}

function overLibraryPanel(event) {
  if (stickerOverlay.hidden || !stickerLibraryPanel) return false;
  const box = stickerLibraryPanel.getBoundingClientRect();
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
    trayZone.classList.remove("drop-ready");
    hotbar.classList.remove("drop-ready");
  };

  const onMove = (moveEvent) => {
    const distance = Math.hypot(
      moveEvent.clientX - startX,
      moveEvent.clientY - startY
    );
    if (distance > 7) moved = true;
    if (!moved) return;

    const point = pageFraction(moveEvent);
    node.setAttribute(
      "transform",
      (() => {
        const metrics = activePageMetrics();
        return "translate(" +
          (point.x * metrics.width) + " " +
          (point.y * metrics.height) + ")";
      })()
    );
    hotbar.classList.toggle("drop-ready", overRemovalZone(moveEvent));
  };

  const onCancel = () => {
    cleanup();
    render();
  };

  const onUp = async (upEvent) => {
    cleanup();

    if (overRemovalZone(upEvent) && moved) {
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

    // Ambient/letterbox space is not part of the governed page. A release
    // there never turns into a clamped edge move; the sticker snaps back to
    // authoritative state instead.
    if (!overPage(upEvent)) {
      render();
      speak("Keep stickers on the page");
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

function ghostFor(kind) {
  const ghost = document.createElement("div");
  ghost.id = "ghost";
  const mini = miniature(kind);
  mini.setAttribute("width", "100%");
  mini.setAttribute("height", "100%");
  ghost.appendChild(mini);
  document.body.appendChild(ghost);
  return ghost;
}

function grabFromTray(event, kind) {
  event.preventDefault();

  const button = event.currentTarget;
  try { button.setPointerCapture(event.pointerId); } catch (_) {}

  const ghost = ghostFor(kind);

  const placeGhost = (moveEvent) => {
    ghost.style.left = moveEvent.clientX + "px";
    ghost.style.top = moveEvent.clientY + "px";

    if (stickerLibraryPanel) {
      stickerLibraryPanel.classList.toggle(
        "return-ready",
        overLibraryPanel(moveEvent)
      );
    }
  };

  placeGhost(event);

  const cleanup = () => {
    button.removeEventListener("pointermove", onMove);
    button.removeEventListener("pointerup", onUp);
    button.removeEventListener("pointercancel", onCancel);
    ghost.remove();

    if (stickerLibraryPanel) {
      stickerLibraryPanel.classList.remove("return-ready");
    }
  };

  const onMove = (moveEvent) => placeGhost(moveEvent);
  const onCancel = () => cleanup();

  const onUp = async (upEvent) => {
    const returnedToLibrary = overLibraryPanel(upEvent);
    cleanup();

    if (returnedToLibrary) {
      removeFromHotbar(kind);
      return;
    }

    // While the library is open, the hotbar is in "organize my sheet" mode.
    // Do not let a drop through the overlay place a sticker on the page.
    if (!stickerOverlay.hidden) return;
    if (!overPage(upEvent)) return;

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

function addToHotbar(kind) {
  if (!definitionIds().includes(kind)) return;

  if (!hotbarKinds.includes(kind)) {
    hotbarKinds.push(kind);
    drawTray();
  }

  speak(kind + " added to your sticker sheet");
}

function removeFromHotbar(kind) {
  const index = hotbarKinds.indexOf(kind);
  if (index === -1) return;

  hotbarKinds.splice(index, 1);
  drawTray();
  speak(kind + " returned to the sticker library");
}

function grabFromLibrary(event, kind) {
  event.preventDefault();

  const card = event.currentTarget;
  const startX = event.clientX;
  const startY = event.clientY;
  let moved = false;

  try { card.setPointerCapture(event.pointerId); } catch (_) {}

  const ghost = ghostFor(kind);

  const moveGhost = (moveEvent) => {
    ghost.style.left = moveEvent.clientX + "px";
    ghost.style.top = moveEvent.clientY + "px";

    if (Math.hypot(moveEvent.clientX - startX, moveEvent.clientY - startY) > 7) {
      moved = true;
    }

    trayZone.classList.toggle("drop-ready", overTrayZone(moveEvent));
  };

  moveGhost(event);

  const cleanup = () => {
    card.removeEventListener("pointermove", onMove);
    card.removeEventListener("pointerup", onUp);
    card.removeEventListener("pointercancel", onCancel);
    trayZone.classList.remove("drop-ready");
    ghost.remove();
  };

  const onMove = (moveEvent) => moveGhost(moveEvent);
  const onCancel = () => cleanup();

  const onUp = (upEvent) => {
    const dropped = overTrayZone(upEvent);
    cleanup();

    if (dropped || !moved) {
      addToHotbar(kind);
    }
  };

  card.addEventListener("pointermove", onMove);
  card.addEventListener("pointerup", onUp);
  card.addEventListener("pointercancel", onCancel);
}

// Two-step peel + press path used by keyboard/accessibility and future tooling.
function chooseSticker(kind) {
  pendingDefinition = kind;
  closeLibrary();
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

  placementPreview.setAttribute(
    "transform",
    (() => {
        const metrics = activePageMetrics();
        return "translate(" +
          (point.x * metrics.width) + " " +
          (point.y * metrics.height) + ")";
      })()
  );
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
}, true);

svg.addEventListener("pointercancel", () => {
  if (!pendingDefinition) return;
  layers.placement.replaceChildren();
  placementPreview = null;
}, true);

svg.addEventListener("contextmenu", (event) => event.preventDefault());

// ------------------------------------------------------ sticker library

function drawStickerLibrary() {
  stickerLibraryGrid.replaceChildren();

  for (const definition of state && state.definitions || []) {
    const card = document.createElement("button");
    card.className = "library-sticker";
    card.type = "button";
    card.setAttribute(
      "aria-label",
      "Drag " + definition.id + " to your sticker sheet"
    );
    card.appendChild(miniature(definition.id));

    const label = document.createElement("span");
    label.textContent = definition.id;
    card.appendChild(label);

    card.addEventListener(
      "pointerdown",
      (event) => grabFromLibrary(event, definition.id)
    );

    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        addToHotbar(definition.id);
      }
    });

    stickerLibraryGrid.appendChild(card);
  }

  const make = document.createElement("button");
  make.className = "make-sticker-card";
  make.type = "button";
  make.innerHTML =
    '<span class="make-plus">+</span><span>make a sticker</span>';
  make.addEventListener("click", openStickerMaker);
  stickerLibraryGrid.appendChild(make);
}

function openLibrary() {
  clearPlacement();
  drawStickerLibrary();
  stickerLibraryView.hidden = false;
  stickerMakerView.hidden = true;
  stickerOverlay.hidden = false;
}

function closeLibrary() {
  stickerOverlay.hidden = true;
  stickerMakerView.hidden = true;
  stickerLibraryView.hidden = false;
  trayZone.classList.remove("drop-ready");
}

function openStickerMaker() {
  stickerLibraryView.hidden = true;
  stickerMakerView.hidden = false;
}

function backToStickerLibrary() {
  stickerMakerView.hidden = true;
  stickerLibraryView.hidden = false;
}

// ---------------------------------------------------------------- wire

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
      '[data-id="' + CSS.escape(receipt.object) + '"]'
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
  drawCover();

  if (DEV) await refreshReceipts();
}

// ------------------------------------------------------------ developer

function showVerdict(payload) {
  const receipt = payload.receipt;

  if (!receipt) {
    dev.verdict.className = "verdict rejected";
    dev.verdict.textContent = "refused — " + (payload.error || "invalid request");
  } else {
    dev.verdict.className =
      "verdict " + (receipt.accepted ? "accepted" : "rejected");
    dev.verdict.textContent = receipt.accepted
      ? "accepted — " + receipt.action + " " +
        (receipt.object || "") + " (rev " + receipt.resultRevision + ")"
      : "refused — " + receipt.reason + "; nothing changed";
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
        receipt.action + " " + (receipt.object || "") + " → " +
        receipt.reason + " (rev " + receipt.resultRevision + ")"
      )
    );

    dev.receipts.appendChild(item);
  }
}

// ------------------------------------------------------------- uploads

const PAGE_UPLOAD_TYPES = new Set([
  "image/svg+xml",
  "image/png",
  "image/jpeg",
  "image/webp",
]);

const PAGE_UPLOAD_EXTENSIONS = new Set([
  ".svg",
  ".png",
  ".jpg",
  ".jpeg",
  ".webp",
]);

function pageUploadExtension(filename) {
  const match = String(filename || "").toLowerCase().match(/\.[^.]+$/);
  return match ? match[0] : "";
}

function supportedPageUpload(file) {
  return Boolean(
    file &&
    PAGE_UPLOAD_TYPES.has(file.type) &&
    PAGE_UPLOAD_EXTENSIONS.has(pageUploadExtension(file.name))
  );
}

function setPageUploadStatus(message) {
  const node = document.getElementById("page-upload-status");
  if (node) node.textContent = message || "";
}

function previewUpload(input, preview, kind) {
  const file = input.files && input.files[0];
  if (!file || !file.type.startsWith("image/")) return;

  const previous = kind === "page" ? pagePreviewUrl : stickerPreviewUrl;
  if (previous) URL.revokeObjectURL(previous);

  const url = URL.createObjectURL(file);

  if (kind === "page") pagePreviewUrl = url;
  else stickerPreviewUrl = url;

  preview.style.backgroundImage =
    "linear-gradient(rgba(0,0,0,.08), rgba(0,0,0,.08)), url('" + url + "')";
  preview.classList.add("has-image");

  const strong = preview.querySelector("strong");
  const small = preview.querySelector("small");
  const plus = preview.querySelector(".upload-plus");

  if (plus) plus.textContent = "✓";
  if (strong) strong.textContent = file.name;
  if (small) {
    small.textContent = kind === "page"
      ? "selected page artwork"
      : "ready for future Sticker Maker";
  }
}

function pageUploadDraftVariant() {
  const variants = pageUploadDraft && pageUploadDraft.variants || {};
  return portraitViewport()
    ? (variants.portrait || variants.landscape || null)
    : (variants.landscape || variants.portrait || null);
}

function renderPageUploadDraft() {
  if (!pageUploadDraft) return;

  const preview = document.getElementById("page-upload-preview");
  const variant = pageUploadDraftVariant();
  if (!preview || !variant || !variant.src) return;

  preview.style.backgroundImage =
    "linear-gradient(rgba(0,0,0,.05), rgba(0,0,0,.05)), url('" +
    variant.src + "')";
  preview.classList.add("has-image");

  const strong = preview.querySelector("strong");
  const small = preview.querySelector("small");
  const plus = preview.querySelector(".upload-plus");

  if (plus) plus.textContent = "✓";
  if (strong) strong.textContent =
    pageUploadDraft.source_name || variant.filename || "Page";
  if (small) {
    small.textContent = portraitViewport()
      ? "portrait version · 941 × 1574"
      : "horizontal version · 1916 × 717";
  }
}

async function handlePageUpload(input) {
  const file = input.files && input.files[0];
  const preview = document.getElementById("page-upload-preview");

  pageUploadDraft = null;
  setPageUploadStatus("");

  if (!file) return;
  if (!supportedPageUpload(file)) {
    input.value = "";
    setPageUploadStatus("Use SVG, PNG, JPEG, or WebP artwork.");
    return;
  }

  previewUpload(input, preview, "page");

  if (world.name === "public mechanical") {
    setPageUploadStatus(
      "Preview only here. The public demo never sends your picture to a model."
    );
    return;
  }

  const capabilities = creatorCapabilities();
  if (!capabilities.page_image_creator) {
    setPageUploadStatus(
      "Local preview only. The page-image gateway is not connected."
    );
    return;
  }

  setPageUploadStatus(
    "Making horizontal and portrait versions with the configured image model…"
  );

  try {
    const payload = await world.pageImageDraft(file);

    if (!payload || !payload.ok || !payload.draft) {
      setPageUploadStatus(
        payload && payload.error || "Page image generation did not finish."
      );
      return;
    }

    pageUploadDraft = payload.draft;
    renderPageUploadDraft();
    setPageUploadStatus("Ready: 1916 × 717 + 941 × 1574.");
  } catch (error) {
    console.error(error);
    setPageUploadStatus("The page-image gateway is unavailable.");
  }
}

function setCreatorMode(kind, mode) {
  const prefix = kind === "page" ? "page" : "sticker";
  const upload = document.getElementById(prefix + "-upload-mode");
  const assist = document.getElementById(prefix + "-assist-mode");
  const buttons = document.querySelectorAll(
    '[data-' + prefix + '-mode]'
  );

  for (const button of buttons) {
    button.classList.toggle(
      "active",
      button.dataset[prefix + "Mode"] === mode
    );
  }

  upload.hidden = mode !== "upload";
  assist.hidden = mode !== "assist";
}

function creatorCapabilities() {
  return state && state.capabilities || {};
}

function creatorUnavailableMessage() {
  if (world.name === "public mechanical") {
    return "Agent-assisted creation is not connected on the public demo. Use Upload here, or open the powered local StickerBook.";
  }
  return "The creator-agent seam is ready, but no local creator agent is connected yet.";
}

let stickerClipIntent = "still";

async function requestCreatorDraft(kind) {
  const isSticker = kind === "sticker";
  const prompt = document.getElementById(
    isSticker ? "sticker-agent-prompt" : "page-agent-prompt"
  ).value.trim();
  const statusNode = document.getElementById(
    isSticker ? "sticker-agent-status" : "page-agent-status"
  );

  if (!prompt) {
    statusNode.textContent = isSticker
      ? "Describe the sticker you want."
      : "Describe the world you want.";
    return;
  }

  const capabilities = creatorCapabilities();
  if (!capabilities.creator_agent) {
    statusNode.textContent = creatorUnavailableMessage();
    return;
  }

  statusNode.textContent = "Making a draft…";

  try {
    const payload = await world.creatorDraft({
      kind,
      prompt,
      animation_intent: isSticker ? stickerClipIntent : null,
      asset_schema_version: 2,
      based_on_revision: state ? state.revision : null,
    });

    if (!payload || !payload.ok) {
      statusNode.textContent =
        payload && payload.error || "Creator agent did not return a draft.";
      return;
    }

    if (isSticker) {
      statusNode.textContent =
        "Draft package ready: " +
        (payload.draft && payload.draft.summary || "idle + behavior clips");
    } else {
      statusNode.textContent =
        "Draft page ready: " +
        (payload.draft && payload.draft.summary || "preview available");
    }
  } catch (error) {
    console.error(error);
    statusNode.textContent = "Creator agent is unavailable.";
  }
}


// ------------------------------------------------------ conversational Omega

function conversationCapabilities() {
  return state && state.capabilities || {};
}

function speechRecognitionConstructor() {
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

function updateConversationControls() {
  if (!voiceOrb || !agentAdultControls) return;

  const capabilities = conversationCapabilities();
  const connected = Boolean(capabilities.conversational_agent);
  const SpeechRecognitionCtor = speechRecognitionConstructor();
  const onPlaySurface = screens.play && !screens.play.hidden;

  agentAdultControls.hidden = !connected;

  if (!connected) {
    voiceEnabled = false;
    if (voiceEnable) voiceEnable.checked = false;
  }

  if (voiceEnable) {
    voiceEnable.disabled = !connected || !SpeechRecognitionCtor;
  }

  if (voicePrivacyNote) {
    voicePrivacyNote.textContent = !SpeechRecognitionCtor
      ? "Voice recognition is unavailable in this browser. The adult text fallback remains available."
      : "Voice is push-to-talk. Speech recognition may use your browser or device speech service; StickerBook sends the resulting text to the local conversational runtime.";
  }

  voiceOrb.hidden = !(
    connected &&
    voiceEnabled &&
    SpeechRecognitionCtor &&
    onPlaySurface
  );
}

function setVoiceOrbState(name) {
  if (!voiceOrb) return;
  voiceOrb.classList.remove("listening", "speaking", "error");
  if (name && name !== "ready") voiceOrb.classList.add(name);
  if (voiceOrbState) voiceOrbState.textContent = name || "ready";
}

async function converseWithStickerBook(text, aloud) {
  const clean = String(text || "").trim();
  if (!clean) return null;

  const capabilities = conversationCapabilities();
  if (!capabilities.conversational_agent) {
    if (adultChatReply) {
      adultChatReply.textContent = "No conversational Omega runtime is connected.";
    }
    return null;
  }

  voiceBusy = true;
  if (aloud) setVoiceOrbState("speaking");

  try {
    const payload = await world.converse({ text: clean });

    if (payload && payload.state) {
      state = payload.state;
      render();
    }

    if (!payload || !payload.ok || typeof payload.reply !== "string") {
      const message = payload && payload.error
        ? payload.error
        : "Conversation runtime did not return a reply.";
      if (adultChatReply) adultChatReply.textContent = message;
      if (aloud) setVoiceOrbState("error");
      return null;
    }

    const reply = payload.reply.trim();
    if (adultChatReply) adultChatReply.textContent = reply;
    speak(reply);

    if (aloud && reply && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(reply);
      utterance.onend = () => {
        voiceBusy = false;
        setVoiceOrbState("ready");
      };
      utterance.onerror = () => {
        voiceBusy = false;
        setVoiceOrbState("error");
      };
      window.speechSynthesis.speak(utterance);
    } else {
      voiceBusy = false;
      setVoiceOrbState("ready");
    }

    return reply;
  } catch (error) {
    console.error(error);
    voiceBusy = false;
    if (adultChatReply) {
      adultChatReply.textContent = "Conversation runtime is unavailable.";
    }
    if (aloud) setVoiceOrbState("error");
    return null;
  }
}

function startVoiceConversation() {
  if (!voiceEnabled || voiceBusy) return;

  const SpeechRecognitionCtor = speechRecognitionConstructor();
  if (!SpeechRecognitionCtor) {
    updateConversationControls();
    return;
  }

  if (voiceRecognition) {
    try { voiceRecognition.abort(); } catch (_) {}
  }

  const recognition = new SpeechRecognitionCtor();
  voiceRecognition = recognition;
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  if (navigator.language) recognition.lang = navigator.language;

  recognition.onstart = () => {
    setVoiceOrbState("listening");
  };

  recognition.onresult = (event) => {
    const result = event.results && event.results[0];
    const transcript = result && result[0] && result[0].transcript;
    if (transcript) {
      converseWithStickerBook(transcript, true);
    }
  };

  recognition.onerror = () => {
    voiceBusy = false;
    setVoiceOrbState("error");
  };

  recognition.onend = () => {
    voiceRecognition = null;
    if (!voiceBusy && !voiceOrb.classList.contains("error")) {
      setVoiceOrbState("ready");
    }
  };

  try {
    recognition.start();
  } catch (error) {
    console.error(error);
    setVoiceOrbState("error");
  }
}

// --------------------------------------------------------------- boot

document.getElementById("cover-enter").addEventListener("click", () => {
  showScreen("gallery");
});

document.getElementById("adult-hotspot").addEventListener("click", () => {
  adultPanel.hidden = false;
});

document.getElementById("adult-close").addEventListener("click", () => {
  adultPanel.hidden = true;
});

document.getElementById("adult-backdrop").addEventListener("click", () => {
  adultPanel.hidden = true;
});

document.getElementById("gallery-back").addEventListener("click", () => {
  showScreen("cover");
});

document.getElementById("creator-back").addEventListener("click", () => {
  showScreen("gallery");
});

document.getElementById("home-btn").addEventListener("click", () => {
  showScreen("cover");
});

document.getElementById("library-btn").addEventListener("click", openLibrary);
document.getElementById("library-close").addEventListener("click", closeLibrary);
document.getElementById("library-backdrop").addEventListener("click", closeLibrary);
document.getElementById("sticker-maker-back")
  .addEventListener("click", backToStickerLibrary);

document.getElementById("page-upload").addEventListener("change", (event) => {
  handlePageUpload(event.currentTarget);
});

document.getElementById("sticker-upload").addEventListener("change", (event) => {
  previewUpload(
    event.currentTarget,
    document.getElementById("sticker-upload-preview"),
    "sticker"
  );
});

for (const button of document.querySelectorAll("[data-page-mode]")) {
  button.addEventListener("click", () => {
    setCreatorMode("page", button.dataset.pageMode);
  });
}

for (const button of document.querySelectorAll("[data-sticker-mode]")) {
  button.addEventListener("click", () => {
    setCreatorMode("sticker", button.dataset.stickerMode);
  });
}

for (const button of document.querySelectorAll("[data-clip-intent]")) {
  button.addEventListener("click", () => {
    stickerClipIntent = button.dataset.clipIntent;
    for (const peer of document.querySelectorAll("[data-clip-intent]")) {
      peer.classList.toggle("active", peer === button);
    }
  });
}

document.getElementById("page-agent-go").addEventListener("click", () => {
  requestCreatorDraft("page");
});

document.getElementById("sticker-agent-go").addEventListener("click", () => {
  requestCreatorDraft("sticker");
});

voiceEnable.addEventListener("change", () => {
  voiceEnabled = voiceEnable.checked;
  if (!voiceEnabled && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
  updateConversationControls();
});

voiceOrb.addEventListener("click", startVoiceConversation);

adultChatSend.addEventListener("click", () => {
  const text = adultChatInput.value;
  if (!text.trim()) return;
  adultChatInput.value = "";
  converseWithStickerBook(text, false);
});

adultChatInput.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  adultChatSend.click();
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;

  if (!adultPanel.hidden) {
    adultPanel.hidden = true;
    return;
  }

  if (!stickerOverlay.hidden) {
    closeLibrary();
    return;
  }

  if (pendingDefinition) {
    clearPlacement();
    return;
  }

  if (!screens.play.hidden) {
    showScreen("cover");
  } else if (!screens.creator.hidden || !screens.gallery.hidden) {
    showScreen("cover");
  }
});

if (DEV) dev.panel.hidden = false;

async function boot() {
  await loadAssetManifest();
  startStickerFrameTicker();
  drawCover();
  showScreen("cover");

  try {
    await reload();
  } catch (error) {
    console.error(error);

    // A localhost static preview without bridge remains useful for UI work.
    // Fallback happens only during boot; never silently mid-session.
    if (world === kernelWorld) {
      world = createMechanicalWorld();
      bookCache = null;
      await reload();
    }
  }
}


let viewportChangeTimer = null;

function handleViewportChange() {
  syncViewportCssVars();
  drawCover();
  renderPageUploadDraft();

  if (state) {
    render();
  }

  if (!screens.gallery.hidden) {
    drawGallery();
  }
}

function scheduleViewportChange() {
  clearTimeout(viewportChangeTimer);
  viewportChangeTimer = setTimeout(handleViewportChange, 60);
}

if (window.matchMedia) {
  const orientationQuery = window.matchMedia("(orientation: portrait)");
  if (typeof orientationQuery.addEventListener === "function") {
    orientationQuery.addEventListener("change", scheduleViewportChange);
  } else if (typeof orientationQuery.addListener === "function") {
    orientationQuery.addListener(scheduleViewportChange);
  }
}

window.addEventListener("resize", scheduleViewportChange);
window.addEventListener("orientationchange", scheduleViewportChange);

if (window.visualViewport) {
  window.visualViewport.addEventListener("resize", scheduleViewportChange);
  window.visualViewport.addEventListener("scroll", scheduleViewportChange);
}

syncViewportCssVars();
boot();
