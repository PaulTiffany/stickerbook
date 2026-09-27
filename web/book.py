"""
The book: a home for pages.

Deliberately NOT an ordered array. A page is a thing you visit, not a slide
you advance through. Pages may later be made by a child, revisited, found,
remixed, shared or grouped thematically; ordering is one optional
relationship among them, not their identity.

So there is no index, no previous, no next. A page is reached by id.

Only one page exists today. The point of this module is that the ontology
is a collection from the start, so the product is not accidentally built
around previous/next arrows and later discovered to be a linear reader.
"""

from __future__ import annotations

import farm

TITLE = "StickerBook"
SUBTITLE = "Farm Book"

# id -> page module. A page module supplies `build_world`, `page_chrome`
# and the sticker definitions its tray offers.
PAGES = {
    "farm": {
        "id": "farm",
        "name": "The Farm",
        "module": farm,
        "summary": "A barn, a pond, a tree and a fence.",
    },
}

DEFAULT_PAGE = "farm"


def page(page_id: str):
    """Look up a page. Unknown ids resolve to nothing, never to a default."""
    return PAGES.get(page_id)


def listing() -> dict:
    """What the book's home screen shows.

    `pages` is a collection. Its order here is presentation, not structure.
    """
    return {
        "title": TITLE,
        "subtitle": SUBTITLE,
        "pages": [
            {"id": p["id"], "name": p["name"], "summary": p["summary"]}
            for p in PAGES.values()
        ],
        # Named so the UI can show where these will live without pretending
        # they exist. Nothing behind them is built.
        "coming": [
            {"id": "new-page", "label": "New Page"},
            {"id": "find-pages", "label": "Find Pages"},
        ],
    }
