"""Existing book pages: presentation metadata comes from the static manifest."""
import json
from pathlib import Path
import farm
import governed_world

TITLE = "StickerBook"
SUBTITLE = "StickerBook"
DEFAULT_PAGE = "farm"
_MANIFEST = json.loads((Path(__file__).parent / "static/assets/manifest.json").read_text(encoding="utf-8"))
PAGES = {page_id: {"id": page_id, **metadata, "world_page": index}
         for index, (page_id, metadata) in enumerate(_MANIFEST["pages"].items(), 1)}


def page(page_id):
    return PAGES.get(page_id)


def build_world(page_id):
    metadata = page(page_id)
    if metadata is None:
        raise ValueError("unknown-page")
    if page_id == DEFAULT_PAGE:
        return farm.build_world()
    return governed_world.build_world(page=metadata["world_page"])


def page_chrome(page_id):
    if page_id == DEFAULT_PAGE:
        return farm.page_chrome()
    metadata = PAGES[page_id]
    return {"picture": {"description": metadata["summary"], "features": []},
            "tray": sorted(governed_world.ASSETS)}


def listing():
    return {"title": TITLE, "subtitle": SUBTITLE,
            "pages": [{k: metadata[k] for k in ("id", "name", "summary")}
                      for metadata in PAGES.values()],
            "coming": [{"id": "new-page", "label": "New Page"},
                       {"id": "find-pages", "label": "Find Pages"}]}
