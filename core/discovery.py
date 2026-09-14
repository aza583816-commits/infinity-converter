from __future__ import annotations

from typing import Any

from core.browser_tools import BROWSER_TOOLS
from core.tooling import TOOLS, _meta_for

BROWSER_PREFIX = "browser:"

_COLLECTION_LABELS = {
    "students": ("الطلاب", "Students"),
    "educators": ("المعلمون", "Educators"),
    "developers": ("المطورون", "Developers"),
    "business": ("الأعمال", "Business"),
    "creators": ("صناع المحتوى", "Creators"),
    "everyday": ("يومي", "Everyday"),
}


def unified_catalog() -> list[dict[str, Any]]:
    """Return every public Infinity tool surface with globally unique IDs.

    Server conversion tools keep their historical IDs for backwards compatibility.
    Browser-only utilities use a ``browser:`` prefix so collisions such as
    ``text-diff`` cannot make AI/discovery links ambiguous.
    """
    items: list[dict[str, Any]] = []
    for tool in TOOLS.values():
        meta = _meta_for(tool)
        items.append({
            "id": tool.id,
            "raw_id": tool.id,
            "kind": "converter",
            "url": f"/tools/{meta['slug']}",
            "name_ar": tool.name_ar,
            "name_en": tool.name_en,
            "description_ar": tool.description_ar,
            "description_en": tool.description_en,
            "category": tool.category,
            "category_ar": tool.category_ar,
            "category_en": tool.category_en,
            "icon": tool.icon,
            "input_ext": list(tool.input_ext),
            "output_ext": tool.output_ext,
            "input_required": tool.input_required,
            "batch": tool.batch,
            "keywords": meta.get("keywords", ""),
        })

    for tool in BROWSER_TOOLS:
        category_ar, category_en = _COLLECTION_LABELS.get(
            tool.collection, (tool.collection, tool.collection.title())
        )
        items.append({
            "id": f"{BROWSER_PREFIX}{tool.id}",
            "raw_id": tool.id,
            "kind": "browser",
            "url": f"/browser-tools/{tool.id}",
            "name_ar": tool.name_ar,
            "name_en": tool.name_en,
            "description_ar": tool.description_ar,
            "description_en": tool.description_en,
            "category": tool.collection,
            "category_ar": category_ar,
            "category_en": category_en,
            "icon": tool.icon,
            "input_ext": [],
            "output_ext": "browser-result",
            "input_required": False,
            "batch": False,
            "keywords": " ".join(
                [tool.id.replace("-", " "), tool.name_ar, tool.name_en, tool.description_ar, tool.description_en]
            ),
        })
    return items


def unified_index() -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in unified_catalog()}


def command_palette_catalog() -> list[dict[str, Any]]:
    """Compact unified catalog used by Quick Jump in the shared shell."""
    return [
        {
            "id": item["id"],
            "name_ar": item["name_ar"],
            "name_en": item["name_en"],
            "category_ar": item["category_ar"],
            "category_en": item["category_en"],
            "href": item["url"],
            "icon": item["icon"],
            "input_ext": item["input_ext"],
            "kind": item["kind"],
        }
        for item in unified_catalog()
    ]


def catalog_counts() -> dict[str, int]:
    return {
        "converter": len(TOOLS),
        "browser": len(BROWSER_TOOLS),
        "total": len(TOOLS) + len(BROWSER_TOOLS),
    }
