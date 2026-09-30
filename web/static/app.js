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
  reference: document.getElementById("reference-layer"),
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
const stickerLibraryEmpty = document.getElementById("sticker-library-empty");
const stickerSearch = document.getElementById("sticker-search");
const stickerThemes = document.getElementById("sticker-themes");
const stickerCategories = document.getElementById("sticker-categories");
const stickerLibraryView = document.getElementById("sticker-library-view");
const stickerMakerView = document.getElementById("sticker-maker-view");
const adultPanel = document.getElementById("adult-panel");
const inferenceProviderSelect = document.getElementById("inference-provider");
const inferenceModelInput = document.getElementById("inference-model");
const inferenceApply = document.getElementById("inference-apply");
const inferenceStatus = document.getElementById("inference-status");
const childHelpPanel = document.getElementById("child-help-panel");
const childHelpButton = document.getElementById("child-help-btn");
const childHelpClose = document.getElementById("child-help-close");
const childHelpBackdrop = document.getElementById("child-help-backdrop");
const childHelpTitle = document.getElementById("child-help-title");
const childHelpIntro = document.getElementById("child-help-intro");
const childHelpTopics = document.getElementById("child-help-topics");
const adultGuideSummary = document.getElementById("adult-guide-summary");
const adultGuideSections = document.getElementById("adult-guide-sections");
const voiceOrb = document.getElementById("voice-orb");
const voiceOrbState = document.getElementById("voice-orb-state");
const conversationStatus = document.getElementById("conversation-status");
const voiceEnable = document.getElementById("voice-enable");
const agentAdultControls = document.getElementById("agent-adult-controls");
const voicePrivacyNote = document.getElementById("voice-privacy-note");
const textChatEnable = document.getElementById("text-chat-enable");
const accessibilityChat = document.getElementById("accessibility-chat");
const accessibilityChatClose = document.getElementById("accessibility-chat-close");
const accessibilityChatLog = document.getElementById("accessibility-chat-log");
const accessibilityChatInput = document.getElementById("accessibility-chat-input");
const accessibilityChatSend = document.getElementById("accessibility-chat-send");
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
let helpContent = null;
let seq = 0;
let pendingDefinition = null;
let placementPreview = null;
let lastTap = { id: null, at: 0 };
let hotbarKinds = [];
let stickerSearchQuery = "";
let stickerTheme = "all";
let stickerCategory = "all";
let pendingDeicticReference = null;
let deicticGesture = null;
let deicticReferenceSerial = 0;
let pendingPathObservation = Promise.resolve();
let bookCache = null;
let pagePreviewUrl = null;
let pageUploadDraft = null;
let stickerPreviewUrl = null;
let voiceEnabled = true;
let textChatEnabled = false;
let voiceRecognition = null;
let voiceBusy = false;
let conversationPending = false;
let conversationSerial = 0;
let adultInference = null;

const nextId = (kind) => "ui-" + kind + "-" + Date.now() + "-" + (++seq);
const copy = (value) => JSON.parse(JSON.stringify(value));

const el = (name, attrs = {}) => {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  for (const [key, value] of Object.entries(attrs)) {
    node.setAttribute(key, value);
  }
  return node;
};

async function loadHelpContent() {
  try {
    const res = await fetch("static/help.json", { cache: "no-store" });
    if (!res.ok) throw new Error("help content: HTTP " + res.status);
    const help = await res.json();
    if (!help || help.version !== 1 ||
        !help.child || !Array.isArray(help.child.topics) ||
        !help.adult || !Array.isArray(help.adult.sections)) {
      throw new Error("unsupported help schema");
    }
    helpContent = help;
  } catch (error) {
    console.warn("StickerBook help content unavailable.", error);
    helpContent = null;
  }
}

function appendHelpParagraph(parent, text) {
  const p = document.createElement("p");
  p.textContent = String(text || "");
  parent.appendChild(p);
}

function renderHelpContent() {
  if (!helpContent) {
    childHelpIntro.textContent =
      "Help is unavailable right now. You can still drag stickers, use + to find more, and drag a sticker to the bottom bar to remove it.";
    childHelpTopics.replaceChildren();
    adultGuideSummary.textContent =
      "The parent guide could not be loaded. The GitHub repository contains the technical documentation.";
    adultGuideSections.replaceChildren();
    return;
  }

  childHelpTitle.textContent = helpContent.child.title;
  childHelpIntro.textContent = helpContent.child.intro;
  childHelpTopics.replaceChildren();

  for (const topic of helpContent.child.topics) {
    const article = document.createElement("article");
    article.className = "help-topic";

    const heading = document.createElement("h3");
    heading.textContent = topic.title;

    const text = document.createElement("p");
    text.textContent = topic.text;

    article.append(heading, text);
    childHelpTopics.appendChild(article);
  }

  adultGuideSummary.textContent = helpContent.adult.summary;
  adultGuideSections.replaceChildren();

  helpContent.adult.sections.forEach((section, index) => {
    const details = document.createElement("details");
    details.className = "adult-guide-section";
    if (index === 0) details.open = true;

    const summary = document.createElement("summary");
    summary.textContent = section.title;
    details.appendChild(summary);

    for (const paragraph of section.paragraphs || []) {
      appendHelpParagraph(details, paragraph);
    }
    adultGuideSections.appendChild(details);
  });
}

function openChildHelp() {
  childHelpPanel.hidden = false;
}

function closeChildHelp() {
  childHelpPanel.hidden = true;
}

async function loadAssetManifest() {
  try {
    const res = await fetch("static/assets/manifest.json", { cache: "no-store" });
    if (!res.ok) throw new Error("asset manifest: HTTP " + res.status);
    const manifest = await res.json();
    if (!manifest || ![1, 2, 3, 4].includes(manifest.version)) {
      throw new Error("unsupported asset manifest");
    }
    assetManifest = manifest;
  } catch (error) {
    console.warn("StickerBook asset manifest unavailable; using procedural fallbacks.", error);
    assetManifest = null;
  }
}

function stickerAsset(kind) {
  if (state && state.visualAssets && state.visualAssets[kind]) return state.visualAssets[kind];
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
  const raw = clips[name] || clips[defaultName] || null;
  if (!raw) return null;

  const sprites = asset.sprites || {};
  return {
    ...raw,
    frames: (raw.frames || []).map((frame) => sprites[frame] || frame),
  };
}

function clipImage(clip) {
  if (!clip || !Array.isArray(clip.frames) || !clip.frames.length) return null;

  const image = svgImage(clip.frames[0], -72, -72, 144, 144);

  if (clip.frames.length > 1) {
    image.dataset.stickerFramePlayer = "1";
    image._stickerFrames = clip.frames.slice();
    image._stickerFrameMs = Math.max(40, Number(clip.frame_ms) || 120);
    image._stickerLoop = clip.loop !== false;
    image._stickerFrameStartedAt = performance.now();
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
        const startedAt = Number(image._stickerFrameStartedAt) || now;
        let index = Math.floor(Math.max(0, now - startedAt) / ms);

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
    { id: "bird", animations: ["none", "rest", "flight", "land"], rest_clip: "rest", scale_bounds: { min: .9, max: 1.1 } },
    { id: "butterfly", animations: ["none", "rest", "flutter", "land"], rest_clip: "rest", scale_bounds: { min: .9, max: 1.1 } },
    { id: "frog", animations: ["none", "rest", "hop", "land"], rest_clip: "rest", scale_bounds: { min: .9, max: 1.1 } },
    { id: "fish", animations: ["none", "rest", "swim", "dive"], rest_clip: "rest", scale_bounds: { min: .9, max: 1.1 } },
    { id: "flower", animations: ["none", "rest", "sway", "bloom"], rest_clip: "rest", scale_bounds: { min: .9, max: 1.1 } },
    { id: "cloud", animations: ["none", "rest", "drift", "stretch"], rest_clip: "rest", scale_bounds: { min: .9, max: 1.1 } },
    { id: "cow", animations: ["none", "rest", "chew", "look", "step"], rest_clip: "rest", scale_bounds: { min: .9, max: 1.1 } },
    { id: "duck", animations: ["none", "rest", "paddle", "dive"], rest_clip: "rest", scale_bounds: { min: .9, max: 1.1 } },
    { id: "hen", animations: ["none", "rest", "peck", "look", "flap"], rest_clip: "rest", scale_bounds: { min: .9, max: 1.1 } },
  ],
  stickers: [
    {
      id: "cow-1",
      definition: "cow",
      x: 0.24,
      y: 0.86,
      owner: "human:player",
      mine: true,
      scale: 1,
      facing: "right",
      animation: "rest",
      revision: 1,
    },
    {
      id: "butterfly-1",
      definition: "butterfly",
      x: 0.58,
      y: 0.34,
      owner: "agent:jev-visual-1",
      mine: false,
      scale: 1,
      facing: "right",
      animation: "rest",
      revision: 1,
    },
  ],
};

const DEMO_INFERENCE = {
  selected: { provider: "off", model: "" },
  options: [
    {
      id: "off",
      label: "Off",
      description: "Disable conversational OmegaLLM for this session.",
      default_model: "",
      model_locked: true,
      sponsored: false,
      available: true,
    },
    {
      id: "asicloud",
      label: "Sponsored ASI Cloud",
      description: "Powered local mode can use sponsored MiniMax inference when configured.",
      default_model: "minimax/minimax-m3",
      model_locked: true,
      sponsored: true,
      available: false,
    },
    {
      id: "anthropic",
      label: "Anthropic",
      description: "Powered local mode can use Claude with a configured Anthropic API key.",
      default_model: "claude-opus-4-8",
      model_locked: false,
      sponsored: false,
      available: false,
    },
    {
      id: "openai",
      label: "OpenAI",
      description: "Powered local mode can use OpenAI with a configured API key.",
      default_model: "gpt-5.5",
      model_locked: false,
      sponsored: false,
      available: false,
    },
    {
      id: "openrouter",
      label: "OpenRouter",
      description: "Powered local mode can route an adult-selected model through OpenRouter.",
      default_model: "z-ai/glm-5.2",
      model_locked: false,
      sponsored: false,
      available: false,
    },
    {
      id: "asione",
      label: "ASI:One",
      description: "Powered local mode can use ASI:One with a configured API key.",
      default_model: "asi1-ultra",
      model_locked: false,
      sponsored: false,
      available: false,
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

  const syncDefinitionsFromManifest = () => {
    const stickers = assetManifest && assetManifest.stickers;
    if (!stickers) return;

    worldState.definitions = Object.entries(stickers).map(([id, asset]) => ({
      id,
      animations: ["none", ...Object.keys(asset.clips || {})],
      rest_clip: asset.default_clip || "none",
      scale_bounds: asset.scale_bounds || { min: .9, max: 1.1 },
    }));
  };

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
      syncDefinitionsFromManifest();
      return copy(worldState);
    },

    async book() {
      return copy(mechanicalBook());
    },

    async selectPage(pageId) {
      syncDefinitionsFromManifest();
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

    async inferenceSettings() {
      return copy(DEMO_INFERENCE);
    },

    async setInference() {
      return {
        ok: false,
        error: "powered-local-only",
        inference: copy(DEMO_INFERENCE),
      };
    },

    async converse(body) {
      const pointed = body && body.reference;
      return {
        ok: true,
        stub: true,
        reply: pointed
          ? "Public demo only — your temporary page reference would accompany this message to Omega in the powered local StickerBook. No model is connected here."
          : "Public demo chat only — no model is connected. A powered local StickerBook uses this same text window for Omega conversation.",
        state: copy(worldState),
      };
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
            scale: 1,
            facing: "right",
            animation: def.rest_clip || "none",
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
          const def = definition(target.definition);
          target.animation = def && def.rest_clip || "none";
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
        const rest = def && def.rest_clip || "none";
        const active = (def && def.animations || []).find(
          (name) => name !== "none" && name !== rest
        );
        if (!active) {
          return refuse("animate-own-sticker", target.id, "no-animation");
        }
        return commit("animate-own-sticker", target.id, (revision) => {
          target.animation = target.animation === rest ? active : rest;
          target.revision = revision;
        });
      }

      if (path === "/api/resize") {
        const target = sticker(body.sticker);
        const def = target && definition(target.definition);
        const bounds = def && def.scale_bounds || { min: .9, max: 1.1 };
        const scale = Number(body.scale);
        if (!target || !Number.isFinite(scale) ||
            scale < bounds.min || scale > bounds.max) {
          return refuse("resize-own-sticker", body.sticker, "scale-out-of-bounds");
        }
        return commit("resize-own-sticker", target.id, (revision) => {
          target.scale = scale;
          target.revision = revision;
        });
      }

      if (path === "/api/facing") {
        const target = sticker(body.sticker);
        if (!target || !["left", "right"].includes(body.facing)) {
          return refuse("set-sticker-facing", body.sticker, "facing-not-supported");
        }
        return commit("set-sticker-facing", target.id, (revision) => {
          target.facing = body.facing;
          target.revision = revision;
        });
      }

      return refuse("unknown", null, "not-implemented-in-public-demo");
    },
  };
}

const kernelWorld = {
  name: "local kernel",

  async state(fast = false) {
    const res = await fetch(fast ? "/api/state?watch=1&page=" + encodeURIComponent(state.page.id) : "/api/state", { cache: "no-store" });
    if (!res.ok) throw new Error("state: HTTP " + res.status);
    return res.json();
  },

  async book() {
    const res = await fetch("/api/book", { cache: "no-store" });
    if (!res.ok) throw new Error("book: HTTP " + res.status);
    return res.json();
  },

  async selectPage(pageId) {
    return this.send("/api/select-page", { page: pageId });
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
      body: JSON.stringify({ ...body, _page: state && state.page && state.page.id }),
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

  async inferenceSettings() {
    const res = await fetch("/api/adult/inference", { cache: "no-store" });
    if (!res.ok) throw new Error("adult inference: HTTP " + res.status);
    return res.json();
  },

  async setInference(body) {
    const res = await fetch("/api/adult/inference", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...body, _page: state && state.page && state.page.id }),
    });
    return res.json();
  },

  async converse(body) {
    const res = await fetch("/api/agent/converse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...body, _page: state && state.page && state.page.id }),
    });
    return res.json();
  },

  async acknowledge(text) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3500);
    try {
      const res = await fetch("/api/agent/acknowledge", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, _page: state.page.id }), signal: controller.signal,
      });
      return res.json();
    } finally { clearTimeout(timeout); }
  },

  async observePagePath(body) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 2000);
    try {
      const res = await fetch("/api/observe-page-path", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...body, _page: state && state.page && state.page.id }),
        signal: controller.signal,
      });
      return res.json();
    } finally {
      clearTimeout(timeout);
    }
  },

  async send(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(path === "/api/select-page" ? body : { ...body, _page: state && state.page && state.page.id }),
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

function resetStickerVisualToRest(node, kind) {
  const paper = node && node.querySelector(".paper");
  if (!paper) return;

  // Animated clips may use a different frame/pose from the idle sticker.
  // Grabbing a sticker means picking up the physical sticker itself, so swap
  // the visual back to its default/rest clip before it follows the pointer.
  paper.replaceChildren();

  const clip = stickerClip(kind, null);
  const firstFrame = clip && Array.isArray(clip.frames) && clip.frames[0];
  const image = firstFrame
    ? svgImage(firstFrame, -72, -72, 144, 144)
    : null;

  if (image) {
    paper.appendChild(image);
  } else {
    (ART[kind] || ART.flower)(paper);
  }
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

// Authoritative endpoints stay in `state`; these records are presentation only.
const stickerVisuals = new Map();
let motionEpoch = 0;
const STATE_POLL_MS = 125;
const MOVE_TWEEN_MS = 250;
let pageStateWatcher = null;
let renderedBackground = null;
let renderedTray = null;

function stopPageStateWatch() {
  if (pageStateWatcher) {
    pageStateWatcher.stopped = true;
    clearTimeout(pageStateWatcher.timer);
    pageStateWatcher = null;
  }
}

function startPageStateWatch() {
  if (world !== kernelWorld || pageStateWatcher || screens.play.hidden || document.hidden) return;
  const watch = { epoch: motionEpoch, stopped: false, timer: null };
  pageStateWatcher = watch;
  const poll = async () => {
    if (watch.stopped || watch.epoch !== motionEpoch) return;
    try {
      const next = await world.state(true);
      if (!watch.stopped && watch.epoch === motionEpoch &&
          (next.revision > state.revision || JSON.stringify(next.motion) !== JSON.stringify(state.motion))) {
        applyAuthoritativeState(next, watch.epoch);
      }
    } catch (_) { /* A failed observation never invents state or a mutation. */ }
    if (!watch.stopped && watch.epoch === motionEpoch) watch.timer = setTimeout(poll, STATE_POLL_MS);
  };
  poll();
}


function setStickerPosition(visual, point) {
  visual.position = { x: point.x, y: point.y };
  const metrics = activePageMetrics();
  const scale = Number.isFinite(visual.sticker.scale) ? visual.sticker.scale : 1;
  const sx = visual.sticker.facing === "left" ? -scale : scale;
  visual.node.setAttribute("transform", "translate(" + point.x * metrics.width +
    " " + point.y * metrics.height + ") scale(" + sx + " " + scale + ")");
}

function cancelStickerTween(visual) {
  if (visual.frame != null) cancelAnimationFrame(visual.frame);
  visual.frame = null;
}

function cancelVisualMotion() {
  stopPageStateWatch();
  motionEpoch += 1;
  cancelConversationPresentation();
  for (const visual of stickerVisuals.values()) cancelStickerTween(visual);
}

function tweenSticker(visual, endpoint) {
  cancelStickerTween(visual);
  const from = { ...visual.position };
  const start = performance.now();
  const epoch = motionEpoch;
  const frame = (now) => {
    if (visual.held || epoch !== motionEpoch) return;
    const t = Math.min(1, Math.max(0, (now - start) / MOVE_TWEEN_MS));
    const eased = t; // Constant-speed interpolation; steering supplies curvature.
    setStickerPosition(visual, t === 1 ? endpoint : {
      x: from.x + (endpoint.x - from.x) * eased,
      y: from.y + (endpoint.y - from.y) * eased,
    });
    visual.frame = t < 1 ? requestAnimationFrame(frame) : null;
  };
  visual.frame = requestAnimationFrame(frame);
}

function applyAuthoritativeState(next, epoch = motionEpoch) {
  if (!next || epoch !== motionEpoch) return false;
  if (state && (next.page.id !== state.page.id || next.revision < state.revision)) return false;
  state = next;
  render();
  return true;
}

async function observePoweredRequest(request) {
  if (world !== kernelWorld) return request();
  const epoch = motionEpoch;
  let finished = false;
  let timer = null;
  const poll = async () => {
    if (finished || epoch !== motionEpoch) return;
    try {
      const next = await world.state(true);
      if (!finished && epoch === motionEpoch && next.revision > state.revision) {
        applyAuthoritativeState(next, epoch);
      }
    } catch (_) { /* The action response owns error reporting. */ }
    if (!finished && epoch === motionEpoch) timer = setTimeout(poll, STATE_POLL_MS);
  };
  if (!pageStateWatcher) poll();
  try {
    const payload = await request();
    if (payload && payload.state) applyAuthoritativeState(payload.state, epoch);
    return payload;
  } finally {
    finished = true;
    clearTimeout(timer);
  }
}

function drawStickers(stickers) {
  const ids = new Set(stickers.map((sticker) => sticker.id));
  for (const [id, visual] of stickerVisuals) {
    if (!ids.has(id)) {
      cancelStickerTween(visual);
      visual.node.remove();
      stickerVisuals.delete(id);
    }
  }
  for (const sticker of stickers) {
    let visual = stickerVisuals.get(sticker.id);
    if (!visual) {
      const node = el("g", { class: "sticker", "data-id": sticker.id, tabindex: "0", role: "button" });
      visual = { node, sticker, position: { x: sticker.x, y: sticker.y },
        endpoint: { x: sticker.x, y: sticker.y }, frame: null, held: false, artKey: null };
      stickerVisuals.set(sticker.id, visual);
      node.addEventListener("pointerdown", (event) => grabPlaced(event, visual.sticker));
      node.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          send("/api/animate", { sticker: sticker.id, command_id: nextId("anim-key") });
        }
      });
      layers.stickers.appendChild(node);
      setStickerPosition(visual, visual.position);
    }
    visual.sticker = sticker;
    visual.node.setAttribute("aria-label", sticker.definition +
      " sticker. Drag to move. Double tap to bring to life.");
    if (visual.held) continue;
    const artKey = sticker.definition + ":" + sticker.animation;
    if (visual.artKey !== artKey) {
      const art = stickerNode(sticker.definition, "sticker", true, null,
        sticker.animation && sticker.animation !== "none" ? sticker.animation : null);
      if (sticker.animation && sticker.animation !== "none") {
        art.classList.add("alive");
        const clip = stickerClip(sticker.definition, sticker.animation);
        if (clip && clip.motion) art.setAttribute("data-alive", clip.motion);
      }
      visual.node.replaceChildren(art);
      visual.artKey = artKey;
    }
    const endpoint = { x: sticker.x, y: sticker.y };
    if (endpoint.x !== visual.endpoint.x || endpoint.y !== visual.endpoint.y) {
      visual.endpoint = endpoint;
      if (world === kernelWorld) tweenSticker(visual, endpoint);
      else setStickerPosition(visual, endpoint);
    } else if (visual.frame == null) {
      setStickerPosition(visual, endpoint);
    }
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
  const metrics = activePageMetrics();
  const backgroundKey = JSON.stringify([state.page.id, state.picture, metrics.width, metrics.height]);
  if (renderedBackground !== backgroundKey) {
    drawScene(layers.picture, state.picture, "play", state.page && state.page.id);
    renderedBackground = backgroundKey;
  }
  drawStickers(state.stickers);
  if (!deicticGesture) {
    drawDeicticReference(pendingDeicticReference, false);
  }
  const trayKey = JSON.stringify([state.definitions, hotbarKinds]);
  if (renderedTray !== trayKey) {
    drawTray();
    renderedTray = JSON.stringify([state.definitions, hotbarKinds]);
  }

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
  if (name !== "play") {
    if (!screens.play.hidden && world === kernelWorld) {
      world.send('/api/pause-activities', {}).catch(() => {});
    }
    cancelVisualMotion();
    clearDeicticReference(false);
  }

  for (const [key, node] of Object.entries(screens)) {
    node.hidden = key !== name;
  }

  if (name === "gallery") {
    drawGallery();
  }

  updateConversationControls();
  if (name === 'play') startPageStateWatch();
}

async function enterPlay(pageId) {
  cancelVisualMotion();
  for (const visual of stickerVisuals.values()) visual.node.remove();
  stickerVisuals.clear();
  try {
    const result = await world.selectPage(pageId);

    if (!result || !result.ok) {
      speak(
        world.name === "public mechanical"
          ? "That page is unavailable."
          : "That page is unavailable."
      );
      return;
    }

    if (result.state) state = result.state;
    clearDeicticReference(false);
    stickerTheme = (
      assetManifest && assetManifest.pages && assetManifest.pages[pageId]
    ) ? pageId : "all";
    showScreen("play");
    render();
  } catch (error) {
    console.error(error);
    speak("That page could not be opened.");
  }
}

// --------------------------------------------------------------- input

function pagePoint(event) {
  const ctm = svg.getScreenCTM();
  if (!ctm) return null;

  return new DOMPoint(event.clientX, event.clientY)
    .matrixTransform(ctm.inverse());
}

function pageFraction(event) {
  const point = pagePoint(event);
  if (!point) return { x: .5, y: .5 };

  const metrics = activePageMetrics();
  const clamp = (value) => Math.min(Math.max(value, 0), 1);
  return {
    x: clamp(point.x / metrics.width),
    y: clamp(point.y / metrics.height),
  };
}

function overPage(event) {
  const point = pagePoint(event);
  if (!point) return false;

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

function deicticPayload(reference) {
  if (!reference) return null;
  if (reference.kind === "point") {
    return { kind: "point", point: copy(reference.point) };
  }
  if (reference.kind === "box") {
    const payload = { kind: "box", box: copy(reference.box) };
    if (typeof reference.sourceEvent === "string") {
      payload.source_event = reference.sourceEvent;
    }
    return payload;
  }
  return null;
}

function drawDeicticReference(reference, drafting = false) {
  if (!layers.reference) return;
  layers.reference.replaceChildren();
  layers.reference.classList.remove("reference-fade");
  if (!reference) return;

  const metrics = activePageMetrics();
  const group = el("g", {
    class: drafting
      ? "deictic-reference deictic-reference-drafting"
      : "deictic-reference",
  });

  if (reference.kind === "point") {
    const radius = Math.max(
      14,
      Math.min(metrics.width, metrics.height) * .022
    );
    group.appendChild(el("circle", {
      cx: reference.point.x * metrics.width,
      cy: reference.point.y * metrics.height,
      r: radius,
      class: "deictic-point",
    }));
    group.appendChild(el("circle", {
      cx: reference.point.x * metrics.width,
      cy: reference.point.y * metrics.height,
      r: Math.max(3, radius * .16),
      class: "deictic-point-core",
    }));
  } else if (reference.kind === "box") {
    const x = reference.box.x1 * metrics.width;
    const y = reference.box.y1 * metrics.height;
    const width = (reference.box.x2 - reference.box.x1) * metrics.width;
    const height = (reference.box.y2 - reference.box.y1) * metrics.height;
    group.appendChild(el("rect", {
      x, y, width, height,
      rx: Math.max(8, Math.min(width, height) * .08),
      class: "deictic-box",
    }));
  }

  if (reference.path && reference.path.length > 1) {
    group.appendChild(el("polyline", {
      points: reference.path.map((p) => (p.x * metrics.width) + "," + (p.y * metrics.height)).join(" "),
      class: "deictic-path",
    }));
  }
  layers.reference.appendChild(group);
}

function setDeicticReference(reference) {
  pendingDeicticReference = reference;
  deicticReferenceSerial += 1;
  drawDeicticReference(reference, false);
  speak(
    reference.kind === "point"
      ? "Point marked for your next message"
      : "Area marked for your next message"
  );
}

function clearDeicticReference(fade = true) {
  pendingDeicticReference = null;
  deicticGesture = null;

  if (!layers.reference) return;

  if (!fade || !layers.reference.firstElementChild) {
    layers.reference.classList.remove("reference-fade");
    layers.reference.replaceChildren();
    return;
  }

  const serial = ++deicticReferenceSerial;
  layers.reference.classList.add("reference-fade");
  setTimeout(() => {
    if (serial !== deicticReferenceSerial) return;
    layers.reference.classList.remove("reference-fade");
    layers.reference.replaceChildren();
  }, 420);
}

function startDeicticGesture(event) {
  if (pendingDefinition || !stickerOverlay.hidden) return;
  if (screens.play.hidden || !overPage(event)) return;
  if (event.button !== undefined && event.button !== 0) return;

  const start = pageFraction(event);
  deicticGesture = {
    pointerId: event.pointerId,
    start,
    current: start,
    startClientX: event.clientX,
    startClientY: event.clientY,
    boxed: false,
    samples: [{ at: performance.now(), x: start.x, y: start.y }],
  };

  event.preventDefault();
  try { svg.setPointerCapture(event.pointerId); } catch (_) {}
  drawDeicticReference({ kind: "point", point: start }, true);
}

function updateDeicticGesture(event) {
  if (!deicticGesture || deicticGesture.pointerId !== event.pointerId) return;

  const point = pageFraction(event);
  deicticGesture.current = point;
  observePagePathPoint(deicticGesture, point);
  if (
    Math.hypot(
      event.clientX - deicticGesture.startClientX,
      event.clientY - deicticGesture.startClientY
    ) > 12
  ) {
    deicticGesture.boxed = true;
  }

  if (!deicticGesture.boxed) {
    drawDeicticReference(
      { kind: "point", point: deicticGesture.start },
      true
    );
    return;
  }

  const x1 = Math.min(deicticGesture.start.x, point.x);
  const y1 = Math.min(deicticGesture.start.y, point.y);
  const x2 = Math.max(deicticGesture.start.x, point.x);
  const y2 = Math.max(deicticGesture.start.y, point.y);
  drawDeicticReference(
    { kind: "box", box: { x1, y1, x2, y2 }, path: deicticGesture.samples },
    true
  );
}

function observePagePathPoint(gesture, point) {
  const samples = gesture.samples;
  samples.push({ at: performance.now(), x: point.x, y: point.y });
  const error = (a, b, c) => {
    const sx = c.x - a.x;
    const sy = c.y - a.y;
    const length = Math.hypot(sx, sy);
    if (!length) return Math.hypot(b.x - a.x, b.y - a.y);
    return Math.abs(sy * b.x - sx * b.y + c.x * a.y - c.y * a.x) / length;
  };
  while (samples.length > 64) {
    let worst = 1;
    let least = Infinity;
    for (let i = 1; i < samples.length - 1; i += 1) {
      const value = error(samples[i - 1], samples[i], samples[i + 1]);
      if (value < least) { least = value; worst = i; }
    }
    samples.splice(worst, 1);
  }
}

function recordPagePath(gesture) {
  if (world !== kernelWorld || gesture.samples.length < 2) return;
  const reference = pendingDeicticReference;
  const serial = deicticReferenceSerial;
  const first = gesture.samples[0].at;
  const last = gesture.samples[gesture.samples.length - 1].at;
  const span = Math.max(1, last - first);
  const round = (value, places) => Number(value.toFixed(places));
  const body = {
    duration_ms: Math.max(1, Math.round(span)),
    box: copy(reference.box),
    samples: gesture.samples.map((sample) => ({
      t: round(Math.min(1, Math.max(0, (sample.at - first) / span)), 3),
      x: round(sample.x, 4),
      y: round(sample.y, 4),
    })),
  };
  // Serialize page observations; the box mark is already established locally.
  pendingPathObservation = pendingPathObservation.catch(() => {}).then(
    () => world.observePagePath(body)).then((result) => {
      if (result && result.ok && typeof result.sourceEvent === "string" &&
          pendingDeicticReference === reference &&
          deicticReferenceSerial === serial) {
        reference.sourceEvent = result.sourceEvent;
      }
      return result;
    });
}

function finishDeicticGesture(event) {
  if (!deicticGesture || deicticGesture.pointerId !== event.pointerId) return;

  updateDeicticGesture(event);
  const gesture = deicticGesture;
  deicticGesture = null;
  try { svg.releasePointerCapture(event.pointerId); } catch (_) {}

  if (!gesture.boxed) {
    setDeicticReference({
      kind: "point",
      point: gesture.start,
    });
    return;
  }

  const x1 = Math.min(gesture.start.x, gesture.current.x);
  const y1 = Math.min(gesture.start.y, gesture.current.y);
  const x2 = Math.max(gesture.start.x, gesture.current.x);
  const y2 = Math.max(gesture.start.y, gesture.current.y);
  setDeicticReference({
    kind: "box",
    box: { x1, y1, x2, y2 },
    path: gesture.samples,
  });
  recordPagePath(gesture);
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
  const gestureEpoch = motionEpoch;
  const visual = stickerVisuals.get(sticker.id);
  if (visual) { cancelStickerTween(visual); visual.held = true; }
  // Ordered before release/double-tap so a late grab cannot cancel a new invitation.
  const pendingHold = world === kernelWorld
    ? world.send('/api/hold', { sticker: sticker.id }).then((result) => {
        if (result && result.state) applyAuthoritativeState(result.state, gestureEpoch);
      }).catch(() => {})
    : Promise.resolve();
  const startedAt = performance.now();
  const startX = event.clientX;
  const startY = event.clientY;
  const metricsAtGrab = activePageMetrics();
  const pointAtGrab = pagePoint(event);
  const stickerCenterAtGrab = {
    x: (visual ? visual.position.x : sticker.x) * metricsAtGrab.width,
    y: (visual ? visual.position.y : sticker.y) * metricsAtGrab.height,
  };
  const grabOffset = pointAtGrab ? {
    x: pointAtGrab.x - stickerCenterAtGrab.x,
    y: pointAtGrab.y - stickerCenterAtGrab.y,
  } : { x: 0, y: 0 };
  let moved = false;

  const definition = state && state.definitions &&
    state.definitions.find((item) => item.id === sticker.definition);
  const restClip = definition && definition.rest_clip || "none";
  if (sticker.animation && sticker.animation !== restClip) {
    resetStickerVisualToRest(node, sticker.definition);
    node.classList.remove("alive");
    node.removeAttribute("data-alive");
  }
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

  const draggedFraction = (pointerEvent) => {
    const metrics = activePageMetrics();
    const point = pagePoint(pointerEvent);
    if (!point) return { x: sticker.x, y: sticker.y };

    const clamp = (value) => Math.min(Math.max(value, 0), 1);
    return {
      x: clamp((point.x - grabOffset.x) / metrics.width),
      y: clamp((point.y - grabOffset.y) / metrics.height),
    };
  };

  // What the child physically demonstrates while dragging this sticker.
  // These are observations of input, not world mutations: only the final
  // release is proposed to the kernel, and the host binds both endpoints from
  // authoritative state.
  //
  // When the buffer fills, drop the single interior point whose removal
  // changes the path least -- perpendicular distance from the line between
  // its neighbours, the same principle the host uses. Dropping every other
  // point by index would keep coverage but could destroy a brief sharp bend
  // or hook before the host's geometry-aware pass ever sees it, and once the
  // browser throws that away the host cannot recover it.
  //
  // Points are only ever removed, never invented or moved: no smoothing, no
  // fitting, no classification. The host validates and decimates again
  // regardless.
  const DRAG_SAMPLE_CAP = 64;
  const dragSamples = [];

  const pathError = (a, b, c) => {
    const sx = c.x - a.x;
    const sy = c.y - a.y;
    const length = Math.hypot(sx, sy);
    if (length === 0) return Math.hypot(b.x - a.x, b.y - a.y);
    return Math.abs(sy * b.x - sx * b.y + c.x * a.y - c.y * a.x) / length;
  };

  const observeDrag = (point) => {
    dragSamples.push({ at: performance.now(), x: point.x, y: point.y });
    while (dragSamples.length > DRAG_SAMPLE_CAP) {
      let worst = 1;
      let worstError = Infinity;
      for (let i = 1; i < dragSamples.length - 1; i += 1) {
        const error = pathError(
          dragSamples[i - 1], dragSamples[i], dragSamples[i + 1]);
        if (error < worstError) {
          worstError = error;
          worst = i;
        }
      }
      dragSamples.splice(worst, 1);
    }
  };

  // Rounding before transmission is input compression, not interpretation,
  // and it keeps a worst-case payload inside the bridge's body limit.
  const round3 = (value) => Math.round(value * 1000) / 1000;
  const round4 = (value) => Math.round(value * 10000) / 10000;

  const dragPayload = () => {
    if (!dragSamples.length) return null;
    const first = dragSamples[0].at;
    const last = performance.now();
    const duration = Math.max(1, Math.round(last - first));
    const span = last - first || 1;
    return {
      samples: dragSamples.map((sample) => ({
        t: round3(Math.min(1, Math.max(0, (sample.at - first) / span))),
        x: round4(sample.x),
        y: round4(sample.y),
      })),
      duration_ms: duration,
    };
  };

  const onMove = (moveEvent) => {
    const distance = Math.hypot(
      moveEvent.clientX - startX,
      moveEvent.clientY - startY
    );
    if (distance > 7 && !moved) {
      moved = true;
      // Preserve where the child actually grabbed the sticker. Starting a
      // drag must not teleport the sticker center to the pointer.
      observeDrag({ x: sticker.x, y: sticker.y });
    }
    if (!moved) return;

    const point = draggedFraction(moveEvent);
    observeDrag(point);
    if (visual) setStickerPosition(visual, point);
    else node.setAttribute('transform', 'translate(' +
      point.x * activePageMetrics().width + ' ' + point.y * activePageMetrics().height + ')');
    hotbar.classList.toggle("drop-ready", overRemovalZone(moveEvent));
  };

  const releaseVisual = () => {
    if (visual) {
      visual.held = false;
      visual.artKey = null;
      const current = state.stickers.find((item) => item.id === sticker.id);
      if (current) { visual.endpoint = { x: current.x, y: current.y }; setStickerPosition(visual, visual.endpoint); }
    }
    render();
  };
  const onCancel = () => { cleanup(); releaseVisual(); };

  const onUp = async (upEvent) => {
    cleanup();
    try {
    await pendingHold;
    if (gestureEpoch !== motionEpoch) return;

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

    const releasePoint = draggedFraction(upEvent);
    const request = {
      sticker: sticker.id,
      command_id: nextId("move"),
      point: releasePoint,
    };
    const drag = dragPayload();
    if (drag) request.drag = drag;
    await send("/api/propose-move", request);
    } finally { releaseVisual(); }
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

svg.addEventListener("pointerdown", startDeicticGesture);
svg.addEventListener("pointermove", updateDeicticGesture);
svg.addEventListener("pointerup", finishDeicticGesture);
svg.addEventListener("pointercancel", (event) => {
  if (!deicticGesture || deicticGesture.pointerId !== event.pointerId) return;
  deicticGesture = null;
  drawDeicticReference(pendingDeicticReference, false);
});

svg.addEventListener("contextmenu", (event) => event.preventDefault());

// ------------------------------------------------------ sticker library

function stickerCatalogEntry(definition) {
  const asset = stickerAsset(definition.id) || {};
  const fallbackName = definition.id
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

  return {
    definition,
    id: definition.id,
    name: asset.name || fallbackName,
    category: asset.category || "other",
    themes: Array.isArray(asset.themes) ? asset.themes : [],
    tags: Array.isArray(asset.tags) ? asset.tags : [],
    aliases: Array.isArray(asset.aliases) ? asset.aliases : [],
  };
}

function stickerCatalogEntries() {
  return (state && state.definitions || []).map(stickerCatalogEntry);
}

function drawStickerThemes(entries) {
  if (!stickerThemes) return;

  const pageThemes = Object.keys(
    assetManifest && assetManifest.pages || {}
  ).filter((theme) =>
    entries.some((entry) => entry.themes.includes(theme))
  );

  if (stickerTheme !== "all" && !pageThemes.includes(stickerTheme)) {
    stickerTheme = "all";
  }

  stickerThemes.replaceChildren();

  for (const theme of ["all", ...pageThemes]) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "sticker-category sticker-theme";
    button.textContent = theme === "all"
      ? "All worlds"
      : (
          assetManifest.pages[theme] &&
          assetManifest.pages[theme].name ||
          theme
        ).replace(/^The /, "");
    button.classList.toggle("active", theme === stickerTheme);
    button.setAttribute(
      "aria-pressed",
      theme === stickerTheme ? "true" : "false"
    );
    button.addEventListener("click", () => {
      stickerTheme = theme;
      drawStickerLibrary();
    });
    stickerThemes.appendChild(button);
  }
}

function drawStickerCategories(entries) {
  if (!stickerCategories) return;

  const categories = Array.from(new Set(
    entries.map((entry) => entry.category).filter(Boolean)
  )).sort((a, b) => a.localeCompare(b));

  if (
    stickerCategory !== "all" &&
    !categories.includes(stickerCategory)
  ) {
    stickerCategory = "all";
  }

  stickerCategories.replaceChildren();

  for (const category of ["all", ...categories]) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "sticker-category";
    button.textContent = category === "all"
      ? "All"
      : category.replace(/[-_]+/g, " ").replace(
          /\b\w/g,
          (letter) => letter.toUpperCase()
        );
    button.classList.toggle("active", category === stickerCategory);
    button.setAttribute(
      "aria-pressed",
      category === stickerCategory ? "true" : "false"
    );
    button.addEventListener("click", () => {
      stickerCategory = category;
      drawStickerLibrary();
    });
    stickerCategories.appendChild(button);
  }
}

function stickerCatalogMatches(entry) {
  if (stickerTheme !== "all" && !entry.themes.includes(stickerTheme)) {
    return false;
  }

  if (stickerCategory !== "all" && entry.category !== stickerCategory) {
    return false;
  }

  const query = stickerSearchQuery.trim().toLowerCase();
  if (!query) return true;

  const haystack = [
    entry.id,
    entry.name,
    entry.category,
    ...entry.themes,
    ...entry.tags,
    ...entry.aliases,
  ].join(" ").toLowerCase();

  return query.split(/\s+/).every((term) => haystack.includes(term));
}

function drawStickerLibrary() {
  const entries = stickerCatalogEntries();
  drawStickerThemes(entries);
  const categoryEntries = stickerTheme === "all"
    ? entries
    : entries.filter((entry) => entry.themes.includes(stickerTheme));
  drawStickerCategories(categoryEntries);
  stickerLibraryGrid.replaceChildren();

  const visible = entries.filter(stickerCatalogMatches);

  for (const entry of visible) {
    const definition = entry.definition;
    const card = document.createElement("button");
    card.className = "library-sticker";
    card.type = "button";
    card.setAttribute(
      "aria-label",
      "Drag " + entry.name + " to your sticker sheet"
    );
    card.appendChild(miniature(definition.id));

    const label = document.createElement("span");
    label.textContent = entry.name;
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

  if (stickerLibraryEmpty) {
    stickerLibraryEmpty.hidden = visible.length !== 0;
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
    const epoch = motionEpoch;
    payload = path === "/api/animate"
      ? await observePoweredRequest(() => world.send(path, body))
      : await world.send(path, body);
    if (epoch !== motionEpoch) return;

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

  if (payload.state) applyAuthoritativeState(payload.state);
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

  if (payload.jev && payload.jev.result === 'playing') {
    dev.verdict.className = 'verdict accepted';
    dev.verdict.textContent = 'playing ? ' + payload.jev.goal.subject + '; each movement still requires a kernel receipt';
  } else if (!receipt) {
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

async function requestCreatorDraft(kind) {
  const isSticker = kind === "sticker";
  const requestedPage = state && state.page && state.page.id;
  const go = document.getElementById(isSticker ? "sticker-agent-go" : "page-agent-go");
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
  go.disabled = true;

  try {
    const payload = await world.creatorDraft({
      kind,
      prompt,
      animation_intent: isSticker ? "animate" : null,
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
      const draft = payload.draft;
      if (draft && draft.asset) {
        const preview = document.getElementById("sticker-agent-preview");
        preview.replaceChildren(); preview.hidden = false;
        for (const src of Object.values(draft.asset.sprites)) {
          const image = document.createElement("img");
          image.src = src; image.alt = "Animation pose"; image.width = 72; image.height = 72;
          preview.appendChild(image);
        }
        const use = document.createElement("button");
        use.type = "button"; use.textContent = "Add to my stickers";
        use.addEventListener("click", async () => {
          use.disabled = true;
          try {
            const response = await fetch("/api/creator/accept-sticker", {method: "POST",
              headers: {"Content-Type": "application/json"},
              body: JSON.stringify({_page: requestedPage, draft: draft.id})});
            const accepted = await response.json();
            if (!accepted.ok) throw new Error(accepted.error || "Draft unavailable");
            state = accepted.state; hotbarKinds.unshift(accepted.asset);
            stickerTheme = "all"; stickerCategory = "all"; stickerSearchQuery = "";
            if (stickerSearch) stickerSearch.value = "";
            render();
            backToStickerLibrary();
          } catch (error) { statusNode.textContent = "Couldn't add this draft. Please try again."; use.disabled = false; }
        });
        preview.appendChild(use);
      }
    } else {
      statusNode.textContent =
        "Draft page ready: " +
        (payload.draft && payload.draft.summary || "preview available");
      if (payload.draft && payload.draft.variants) {
        pageUploadDraft = payload.draft;
        renderPageUploadDraft();
        const preview = document.getElementById("page-agent-preview");
        preview.replaceChildren(); preview.hidden = false;
        for (const variant of Object.values(payload.draft.variants)) {
          const image = document.createElement("img");
          image.src = variant.src; image.alt = variant.filename;
          preview.appendChild(image);
          const link = document.createElement("a");
          link.href = variant.src; link.download = variant.filename;
          link.textContent = "Save " + variant.filename + " "; statusNode.appendChild(link);
        }
      }
    }
  } catch (error) {
    console.error(error);
    statusNode.textContent = "Creator agent is unavailable.";
  } finally {
    go.disabled = false;
  }
}


// ------------------------------------------------------ conversational Omega

function inferenceOption(providerId) {
  const options = adultInference && adultInference.options || [];
  return options.find((item) => item.id === providerId) || null;
}

function updateInferenceDraft() {
  if (!inferenceProviderSelect || !inferenceModelInput ||
      !inferenceApply || !inferenceStatus) return;

  const option = inferenceOption(inferenceProviderSelect.value);
  if (!option) {
    inferenceModelInput.disabled = true;
    inferenceApply.disabled = true;
    inferenceStatus.textContent = "Inference settings are unavailable.";
    return;
  }

  const off = option.id === "off";
  inferenceModelInput.disabled = off || Boolean(option.model_locked);
  inferenceApply.disabled = option.available !== true;

  if (off) {
    inferenceModelInput.value = "";
  } else if (!inferenceModelInput.value.trim()) {
    inferenceModelInput.value = option.default_model || "";
  }

  const availability = option.available
    ? (option.sponsored ? "Sponsored inference is configured." : "Provider is configured.")
    : "Not configured on this local runtime.";
  inferenceStatus.textContent = option.description + " " + availability;
}

function renderInferenceControls() {
  if (!inferenceProviderSelect || !adultInference) return;

  const selected = adultInference.selected || { provider: "off", model: "" };
  inferenceProviderSelect.replaceChildren();

  for (const item of adultInference.options || []) {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent =
      item.label +
      (item.sponsored ? " · sponsored" : "") +
      (item.available ? "" : " · not configured");
    option.disabled = item.available !== true;
    inferenceProviderSelect.appendChild(option);
  }

  const selectedOption = inferenceOption(selected.provider);
  inferenceProviderSelect.value = selectedOption ? selected.provider : "off";
  inferenceModelInput.value = selectedOption && selected.provider !== "off"
    ? (selected.model || selectedOption.default_model || "")
    : "";
  updateInferenceDraft();
}

async function refreshInferenceControls() {
  try {
    adultInference = await world.inferenceSettings();
  } catch (error) {
    console.error(error);
    adultInference = copy(DEMO_INFERENCE);
  }
  renderInferenceControls();
}

async function applyInferenceSelection() {
  if (!adultInference) await refreshInferenceControls();

  const option = inferenceOption(inferenceProviderSelect.value);
  if (!option || option.available !== true) {
    updateInferenceDraft();
    return;
  }

  const provider = option.id;
  const model = provider === "off"
    ? ""
    : inferenceModelInput.value.trim();

  inferenceApply.disabled = true;
  inferenceStatus.textContent = "Switching inference for this session…";

  try {
    const result = await world.setInference({ provider, model });
    if (result && result.inference) adultInference = result.inference;
    if (result && result.state) {
      state = result.state;
      render();
    }
    if (!result || !result.ok) {
      inferenceStatus.textContent =
        result && result.error || "Inference selection was refused.";
    }
  } catch (error) {
    console.error(error);
    inferenceStatus.textContent = "Inference selection is unavailable.";
  }

  renderInferenceControls();
  updateConversationControls();
}

function conversationCapabilities() {
  return state && state.capabilities || {};
}

function cancelConversationPresentation() {
  conversationSerial += 1;
  conversationPending = false;
  voiceBusy = false;
  const recognition = voiceRecognition;
  voiceRecognition = null;
  if (recognition) { try { recognition.abort(); } catch (_) {} }
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  setVoiceOrbState("ready");
  if (conversationStatus) conversationStatus.hidden = true;
}

function speechRecognitionConstructor() {
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

function updateConversationControls() {
  if (!voiceOrb || !agentAdultControls) return;

  const capabilities = conversationCapabilities();
  const connected = Boolean(capabilities.conversational_agent);
  const stub = world.name === "public mechanical";
  const textAvailable = connected || stub;
  const SpeechRecognitionCtor = speechRecognitionConstructor();
  const onPlaySurface = screens.play && !screens.play.hidden;

  // Keep the adult-facing options visible in the public/mechanical profile.
  // Voice still requires the powered runtime; text chat may be opened in the
  // public build so the accessibility UI itself is testable as a clear stub.
  agentAdultControls.hidden = false;

  if (!textAvailable) {
    textChatEnabled = false;
    if (textChatEnable) textChatEnable.checked = false;
  }

  if (voiceEnable) {
    voiceEnable.disabled = !connected || !SpeechRecognitionCtor;
    voiceEnable.checked = Boolean(connected && SpeechRecognitionCtor && voiceEnabled);
  }

  if (textChatEnable) {
    textChatEnable.disabled = !textAvailable;
  }

  if (accessibilityChatInput) accessibilityChatInput.disabled = !textAvailable;
  if (accessibilityChatSend) accessibilityChatSend.disabled = !textAvailable || voiceBusy;

  if (voicePrivacyNote) {
    voicePrivacyNote.textContent = stub
      ? "Voice requires the powered local Omega runtime. Text chat is available here as a mechanical stub and does not call a model."
      : !connected
        ? "Voice and text chat require the powered local conversational Omega runtime."
        : !SpeechRecognitionCtor
          ? "Voice recognition is unavailable in this browser. Text chat remains available."
          : "Voice is push-to-talk. Speech recognition may use your browser or device speech service; StickerBook sends the resulting text to the local conversational runtime.";
  }

  voiceOrb.hidden = !(
    connected &&
    voiceEnabled &&
    SpeechRecognitionCtor &&
    onPlaySurface
  );
  if (conversationStatus) conversationStatus.hidden = !(conversationPending && onPlaySurface);

  if (accessibilityChat) {
    accessibilityChat.hidden = !(
      textAvailable &&
      textChatEnabled &&
      onPlaySurface
    );
  }
}

function appendAccessibilityChatLine(speaker, text) {
  if (!accessibilityChatLog || !textChatEnabled) return;

  const line = document.createElement("div");
  line.className = "accessibility-chat-line";

  const label = document.createElement("strong");
  label.textContent = speaker + ": ";

  line.append(label, document.createTextNode(String(text || "")));
  accessibilityChatLog.appendChild(line);

  while (accessibilityChatLog.children.length > 12) {
    accessibilityChatLog.firstElementChild.remove();
  }

  accessibilityChatLog.scrollTop = accessibilityChatLog.scrollHeight;
}

function setVoiceOrbState(name) {
  if (!voiceOrb) return;
  voiceOrb.classList.remove("listening", "thinking", "speaking", "error");
  if (name && name !== "ready") voiceOrb.classList.add(name);
  if (voiceOrbState) voiceOrbState.textContent = name || "ready";
  voiceOrb.setAttribute("aria-label", name === "thinking" ? "StickerBook is thinking" :
    name === "listening" ? "Listening to you" : name === "speaking" ? "StickerBook is speaking" : "Talk to StickerBook");
  voiceOrb.setAttribute("aria-busy", String(name === "thinking"));
}

async function captureVisualContext() {
  // Observational pixels only. Render accepted endpoints, never tween frames.
  if (world.name === "public mechanical" || !state) return null;
  const snapshot = state;
  const metrics = activePageMetrics();
  const clone = svg.cloneNode(true);
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.setAttribute("width", metrics.width);
  clone.setAttribute("height", metrics.height);
  for (const id of ["reference-layer", "placement-layer"]) {
    const node = clone.querySelector("#" + id);
    if (node) node.remove();
  }
  for (const sticker of snapshot.stickers) {
    const node = Array.from(clone.querySelectorAll(".sticker")).find(n => n.dataset.id === sticker.id);
    if (!node) continue;
    const scale = Number.isFinite(sticker.scale) ? sticker.scale : 1;
    node.setAttribute("transform", "translate(" + sticker.x * metrics.width + " " +
      sticker.y * metrics.height + ") scale(" + (sticker.facing === "left" ? -scale : scale) + " " + scale + ")");
  }
  // Inline same-origin artwork so SVG rasterization cannot fetch remote URLs.
  const resources = new Map();
  for (const node of clone.querySelectorAll("image")) {
    const href = node.getAttribute("href") || node.getAttributeNS("http://www.w3.org/1999/xlink", "href");
    if (!href) continue;
    if (!resources.has(href)) {
      resources.set(href, (async () => {
        if (href.startsWith("data:image/")) return href;
        const url = new URL(href, location.href);
        if (url.origin !== location.origin) throw new Error("nonlocal-artwork");
        const response = await fetch(url.href, {signal: AbortSignal.timeout(5000)});
        if (!response.ok) throw new Error("artwork-unavailable");
        const blob = await response.blob();
        if (blob.size > 8 * 1024 * 1024) throw new Error("artwork-too-large");
        return await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result);
          reader.onerror = reject;
          reader.readAsDataURL(blob);
        });
      })());
    }
    node.setAttribute("href", await resources.get(href));
    node.removeAttributeNS("http://www.w3.org/1999/xlink", "href");
  }
  const objectURL = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(clone)], {type: "image/svg+xml"}));
  try {
    const image = new Image();
    await new Promise((resolve, reject) => { image.onload = resolve; image.onerror = reject; image.src = objectURL; });
    const canvas = document.createElement("canvas");
    const ratio = Math.min(1, 1024 / Math.max(metrics.width, metrics.height));
    canvas.width = Math.max(1, Math.round(metrics.width * ratio));
    canvas.height = Math.max(1, Math.round(metrics.height * ratio));
    const context = canvas.getContext("2d");
    context.fillStyle = "white";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    for (const quality of [.8, .6, .4]) {
      const jpeg = canvas.toDataURL("image/jpeg", quality);
      if (jpeg.length <= 180000) return {page: snapshot.page.id, revision: snapshot.revision,
        width: canvas.width, height: canvas.height, image: jpeg};
    }
    throw new Error("visual-context-too-large");
  } finally {
    URL.revokeObjectURL(objectURL);
  }
}

async function acknowledgeConversation(text, aloud, mirror, turn) {
  try {
    const payload = await world.acknowledge(text);
    if (turn !== conversationSerial || !conversationPending || !payload || payload.ok !== true || typeof payload.reply !== 'string') return;
    const reply = payload.reply.trim();
    if (!reply || reply.length > 600) return;
    if (mirror) appendAccessibilityChatLine('StickerBook', reply);
    speak(reply);
    if (aloud && voiceEnabled && 'speechSynthesis' in window) {
      const utterance = new SpeechSynthesisUtterance(reply);
      setVoiceOrbState('speaking');
      const done = () => {
        if (turn === conversationSerial && conversationPending) setVoiceOrbState('thinking');
      };
      utterance.onend = done;
      utterance.onerror = done;
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utterance);
    }
  } catch (_) { /* Optional acknowledgement never changes the goal request. */ }
}

async function converseWithStickerBook(text, aloud, mirrorToAccessibility = false) {
  const clean = String(text || "").trim();
  if (!clean || voiceBusy) return null;

  if (mirrorToAccessibility) {
    appendAccessibilityChatLine("You", clean);
  }

  const capabilities = conversationCapabilities();
  const connected = Boolean(capabilities.conversational_agent);
  const stub = world.name === "public mechanical";
  if (!connected && !stub) {
    const message = "No conversational Omega runtime is connected.";
    if (mirrorToAccessibility) {
      appendAccessibilityChatLine("StickerBook", message);
    }
    return null;
  }

  voiceBusy = true;
  const turn = ++conversationSerial;
  let speakingReply = false;
  conversationPending = !stub;
  if (!stub) setVoiceOrbState("thinking");
  updateConversationControls();

  const referenceSerial = deicticReferenceSerial;
  const pendingReference = pendingDeicticReference;
  let reference = null;

  try {
    await pendingPathObservation.catch(() => {});
    if (turn !== conversationSerial) return null;
    reference = deicticPayload(pendingReference);
    // Whether the child spoke or typed. The browser owns the microphone and
    // the keyboard, so it is the only thing that honestly knows. Descriptive
    // only: it carries no authority and nothing branches on it.
    const body = { text: clean, input_mode: aloud ? "voice" : "text" };
    if (reference) body.reference = reference;
    const epoch = motionEpoch;
    if (!stub) {
      try { body.visual = await captureVisualContext(); }
      catch (_) { if (DEV) dev.verdict.textContent = "Visual context unavailable; asking with structured state."; }
      if (epoch !== motionEpoch || turn !== conversationSerial) return null;
    }
    const payload = await observePoweredRequest(() => {
      const request = world.converse(body);
      if (!stub && capabilities.conversation_acknowledgement && typeof world.acknowledge === 'function') {
        void acknowledgeConversation(clean, aloud, mirrorToAccessibility, turn);
      }
      return request;
    });
    if (epoch !== motionEpoch || turn !== conversationSerial) return null;

    if (!payload || !payload.ok || typeof payload.reply !== "string") {
      const messages = {
        "omegallm-busy": "I'm still thinking. Please try again in a moment.",
        "omegallm-timeout": "That took too long. Please try again.",
        "omegallm-not-ready": "I'm getting ready. Please try again in a moment.",
        "page-changed": "The page changed. Please ask me again on this page.",
      };
      const responseMessages = {
        "inference-output-budget": "My answer ran out of room. Please try a shorter request.",
        "inference-empty-content": "I didn't get an answer that time. Please try again.",
      };
      const message = responseMessages[payload && payload.diagnostic && payload.diagnostic.reason] || messages[payload && payload.error] ||
        "I couldn't answer just now. Please try again.";
      if (DEV && payload && payload.diagnostic) {
        dev.verdict.className = "verdict rejected";
        dev.verdict.textContent = payload.diagnostic.stage + ": " +
          payload.diagnostic.reason;
      }
      if (mirrorToAccessibility) {
        appendAccessibilityChatLine("StickerBook", message);
      }
      if (aloud) setVoiceOrbState("error");
      return null;
    }

    const reply = payload.reply.trim();
    if (mirrorToAccessibility) {
      appendAccessibilityChatLine("StickerBook", reply);
    }
    speak(reply);

    if (aloud && voiceEnabled && reply && "speechSynthesis" in window) {
      speakingReply = true;
      setVoiceOrbState("speaking");
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(reply);
      utterance.onend = () => {
        if (turn !== conversationSerial) return;
        voiceBusy = false;
        setVoiceOrbState("ready");
        updateConversationControls();
      };
      utterance.onerror = () => {
        if (turn !== conversationSerial) return;
        voiceBusy = false;
        setVoiceOrbState("error");
        updateConversationControls();
      };
      window.speechSynthesis.speak(utterance);
    } else {
      voiceBusy = false;
      setVoiceOrbState("ready");
    }

    return reply;
  } catch (error) {
    console.error(error);
    if (turn !== conversationSerial) return null;
    speakingReply = false;
    voiceBusy = false;
    if (mirrorToAccessibility) {
      appendAccessibilityChatLine(
        "StickerBook",
        "Conversation runtime is unavailable."
      );
    }
    if (aloud) setVoiceOrbState("error");
    return null;
  } finally {
    if (turn === conversationSerial) {
      conversationPending = false;
      if (!speakingReply && aloud && "speechSynthesis" in window) window.speechSynthesis.cancel();
      if (!speakingReply) voiceBusy = false;
      if (voiceOrb.classList.contains("thinking")) setVoiceOrbState("ready");
      updateConversationControls();
    }
    if (reference && referenceSerial === deicticReferenceSerial) {
      clearDeicticReference(true);
    }
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
    if (voiceRecognition !== recognition) return;
    setVoiceOrbState("listening");
  };

  recognition.onresult = (event) => {
    if (voiceRecognition !== recognition || !voiceEnabled) return;
    const result = event.results && event.results[0];
    const transcript = result && result[0] && result[0].transcript;
    if (transcript) {
      converseWithStickerBook(transcript, true, textChatEnabled);
    }
  };

  recognition.onerror = () => {
    if (voiceRecognition !== recognition) return;
    voiceBusy = false;
    setVoiceOrbState("error");
  };

  recognition.onend = () => {
    if (voiceRecognition !== recognition) return;
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
  refreshInferenceControls();
});

childHelpButton.addEventListener("click", openChildHelp);
childHelpClose.addEventListener("click", closeChildHelp);
childHelpBackdrop.addEventListener("click", closeChildHelp);

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

if (stickerSearch) {
  stickerSearch.addEventListener("input", () => {
    stickerSearchQuery = stickerSearch.value;
    drawStickerLibrary();
  });
}

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

document.getElementById("page-agent-go").addEventListener("click", () => {
  requestCreatorDraft("page");
});

document.getElementById("sticker-agent-go").addEventListener("click", () => {
  requestCreatorDraft("sticker");
});

inferenceProviderSelect.addEventListener("change", () => {
  const option = inferenceOption(inferenceProviderSelect.value);
  inferenceModelInput.value =
    option && option.id !== "off" ? option.default_model || "" : "";
  updateInferenceDraft();
});

inferenceModelInput.addEventListener("input", updateInferenceDraft);
inferenceApply.addEventListener("click", applyInferenceSelection);

voiceEnable.addEventListener("change", () => {
  voiceEnabled = voiceEnable.checked;
  if (!voiceEnabled) {
    const recognition = voiceRecognition;
    voiceRecognition = null;
    if (recognition) { try { recognition.abort(); } catch (_) {} }
    if (!conversationPending) {
      voiceBusy = false;
      setVoiceOrbState("ready");
    }
  }
  if (!voiceEnabled && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
  updateConversationControls();
});

voiceOrb.addEventListener("click", startVoiceConversation);

textChatEnable.addEventListener("change", () => {
  textChatEnabled = textChatEnable.checked;
  updateConversationControls();

  if (textChatEnabled && !accessibilityChat.hidden) {
    if (
      world.name === "public mechanical" &&
      accessibilityChatLog &&
      !accessibilityChatLog.children.length
    ) {
      appendAccessibilityChatLine(
        "StickerBook",
        "Demo chat is active. Messages stay mechanical here; no model is connected."
      );
    }
    requestAnimationFrame(() => accessibilityChatInput.focus());
  }
});

accessibilityChatClose.addEventListener("click", () => {
  textChatEnabled = false;
  textChatEnable.checked = false;
  updateConversationControls();
});

accessibilityChatSend.addEventListener("click", () => {
  if (voiceBusy) return;
  const text = accessibilityChatInput.value;
  if (!text.trim()) return;
  accessibilityChatInput.value = "";
  converseWithStickerBook(text, false, true);
});

accessibilityChatInput.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  accessibilityChatSend.click();
});

function closeDeveloperReceipts() {
  dev.panel.hidden = true;

  const url = new URL(window.location.href);
  url.searchParams.delete("dev");
  const query = url.searchParams.toString();
  window.history.replaceState(
    {},
    "",
    url.pathname + (query ? "?" + query : "") + url.hash
  );

  showScreen("cover");
}

document.getElementById("dev-close").addEventListener(
  "click",
  closeDeveloperReceipts
);

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;

  if (!dev.panel.hidden) {
    closeDeveloperReceipts();
    return;
  }

  if (!childHelpPanel.hidden) {
    closeChildHelp();
    return;
  }

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
  await Promise.all([loadAssetManifest(), loadHelpContent()]);
  renderHelpContent();
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

// A hidden/closed page cannot keep paying for autonomous play. Observation
// leases on the host cover abrupt tab closure or a lost connection too.
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    cancelVisualMotion();
    if (world === kernelWorld) world.send('/api/pause-activities', {}).catch(() => {});
  } else if (!screens.play.hidden) {
    reload().then(startPageStateWatch).catch(() => {});
  }
});
