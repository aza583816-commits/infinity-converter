from __future__ import annotations

from dataclasses import dataclass

from core.tooling import get_tool, tool_url


@dataclass(frozen=True)
class WorkflowRecipe:
    id: str
    name_ar: str
    name_en: str
    description_ar: str
    description_en: str
    steps: tuple[str, ...]
    icon: str = "FLOW"


WORKFLOWS: dict[str, WorkflowRecipe] = {
    "office-share-ready": WorkflowRecipe(
        id="office-share-ready",
        name_ar="مستند جاهز للمشاركة",
        name_en="Share-ready document",
        description_ar="حوّل Word إلى PDF ثم اضغطه تلقائيًا في طلب واحد.",
        description_en="Convert Word to PDF and compress it automatically in one request.",
        steps=("word-to-pdf", "pdf-compress"),
        icon="DOC→PDF",
    ),
    "repair-and-compress-pdf": WorkflowRecipe(
        id="repair-and-compress-pdf",
        name_ar="إصلاح وضغط PDF",
        name_en="Repair and compress PDF",
        description_ar="أصلح بنية PDF أولًا ثم اضغط النسخة الناتجة.",
        description_en="Repair PDF structure first, then compress the repaired result.",
        steps=("pdf-repair", "pdf-compress"),
        icon="PDF✓",
    ),
    "scan-to-searchable-pdf": WorkflowRecipe(
        id="scan-to-searchable-pdf",
        name_ar="PDF ممسوح إلى ملف قابل للبحث",
        name_en="Scan to searchable PDF",
        description_ar="طبّق OCR على PDF الممسوح ثم اضغط النسخة القابلة للبحث.",
        description_en="Apply OCR to a scanned PDF, then compress the searchable result.",
        steps=("ocr-pdf-to-searchable", "pdf-compress"),
        icon="OCR",
    ),
    "web-ready-image": WorkflowRecipe(
        id="web-ready-image",
        name_ar="صورة جاهزة للويب",
        name_en="Web-ready image",
        description_ar="حوّل الصورة إلى JPG ثم اضغطها وأزل بياناتها الوصفية.",
        description_en="Convert an image to JPG, compress it, then strip metadata.",
        steps=("image-to-jpg", "image-compress", "image-strip-metadata"),
        icon="IMG",
    ),
}


def get_workflow(workflow_id: str) -> WorkflowRecipe | None:
    return WORKFLOWS.get(workflow_id)


def public_workflows() -> list[dict]:
    items: list[dict] = []
    for recipe in WORKFLOWS.values():
        step_items = []
        for tool_id in recipe.steps:
            tool = get_tool(tool_id)
            if tool is None:
                raise RuntimeError(f"Workflow {recipe.id} references missing tool {tool_id}")
            step_items.append({
                "id": tool.id,
                "name_ar": tool.name_ar,
                "name_en": tool.name_en,
                "url": tool_url(tool),
                "input_ext": list(tool.input_ext),
                "output_ext": tool.output_ext,
            })
        items.append({
            "id": recipe.id,
            "name_ar": recipe.name_ar,
            "name_en": recipe.name_en,
            "description_ar": recipe.description_ar,
            "description_en": recipe.description_en,
            "icon": recipe.icon,
            "steps": step_items,
        })
    return items


def validate_workflow_registry() -> None:
    for recipe in WORKFLOWS.values():
        if len(recipe.steps) < 2:
            raise RuntimeError(f"Workflow {recipe.id} must contain at least two steps")
        for index, tool_id in enumerate(recipe.steps):
            tool = get_tool(tool_id)
            if tool is None:
                raise RuntimeError(f"Workflow {recipe.id} references missing tool {tool_id}")
            if tool.fields or tool.param_field:
                raise RuntimeError(
                    f"Workflow {recipe.id} step {tool_id} requires interactive options and cannot run unattended"
                )
            if index == 0:
                continue
            previous = get_tool(recipe.steps[index - 1])
            assert previous is not None
            produced = (previous.output_ext or "").lower()
            accepted = {value.lower() for value in tool.input_ext}
            if produced and produced not in accepted and "*" not in accepted and ".*" not in accepted:
                raise RuntimeError(
                    f"Workflow {recipe.id} is incompatible: {previous.id} outputs {produced}, "
                    f"but {tool.id} accepts {sorted(accepted)}"
                )


validate_workflow_registry()
