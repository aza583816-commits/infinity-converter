from __future__ import annotations

from dataclasses import asdict

from core.tooling.catalog import TOOLS
from core.tooling.metadata import (
    AUDIENCE_COLLECTIONS, DEVELOPER_TOOLS, PREMIUM_TOOL_IDS, RELATED_OVERRIDES, TOOL_META,
)
from core.tooling.models import Tool


def plan_required_for_tool(tool_id: str) -> str:
    return "pro" if tool_id in PREMIUM_TOOL_IDS else "free"


def _meta_for(tool: Tool) -> dict:
    return TOOL_META[tool.id]


def get_tool(tool_id: str) -> Tool | None:
    return TOOLS.get(tool_id)


def list_tools() -> list[dict]:
    return [
        {**asdict(tool), **_meta_for(tool), "plan_required": plan_required_for_tool(tool.id)}
        for tool in sorted(TOOLS.values(), key=lambda item: _meta_for(item)["sort"])
    ]


def popular_tools(limit: int = 10) -> list[dict]:
    return [tool for tool in list_tools() if tool["popular"]][:limit]


def collection_tools(collection_id: str) -> tuple[dict, list[dict]] | None:
    collection = AUDIENCE_COLLECTIONS.get(collection_id)
    if not collection:
        return None
    by_id = {tool["id"]: tool for tool in list_tools()}
    return collection, [by_id[tool_id] for tool_id in collection["tool_ids"] if tool_id in by_id]


def get_developer_tool(tool_id: str) -> dict | None:
    return DEVELOPER_TOOLS.get(tool_id)


def tool_url(tool: Tool) -> str:
    return f"/tools/{_meta_for(tool)['slug']}"


def related_tools(tool_id: str, limit: int = 6) -> list[dict]:
    tool = TOOLS.get(tool_id)
    if not tool:
        return []
    ordered_ids = list(RELATED_OVERRIDES.get(tool_id, ()))
    for other_id, other in TOOLS.items():
        if other_id != tool_id and other.category == tool.category and other_id not in ordered_ids:
            ordered_ids.append(other_id)
    by_id = {item["id"]: item for item in list_tools()}
    return [by_id[i] for i in ordered_ids if i in by_id][:limit]


def validate_catalog() -> tuple[str, ...]:
    errors: list[str] = []
    if len(TOOLS) != len(set(TOOLS)):
        errors.append("duplicate tool id")
    slugs = [meta["slug"] for meta in TOOL_META.values()]
    if len(slugs) != len(set(slugs)):
        errors.append("duplicate tool slug")
    missing_meta = set(TOOLS) - set(TOOL_META)
    orphan_meta = set(TOOL_META) - set(TOOLS)
    if missing_meta:
        errors.append(f"missing metadata: {sorted(missing_meta)}")
    if orphan_meta:
        errors.append(f"orphan metadata: {sorted(orphan_meta)}")
    for collection_id, collection in AUDIENCE_COLLECTIONS.items():
        missing = set(collection["tool_ids"]) - set(TOOLS)
        if missing:
            errors.append(f"collection {collection_id} references missing tools: {sorted(missing)}")
    return tuple(errors)
