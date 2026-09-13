from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FormField:
    id: str
    type: str
    label_ar: str
    label_en: str
    required: bool = False
    placeholder_ar: str = ""
    placeholder_en: str = ""
    default: str = ""
    choices: tuple[tuple[str, str, str], ...] = ()


@dataclass(frozen=True)
class Tool:
    id: str
    name_ar: str
    name_en: str
    description_ar: str
    description_en: str
    category: str
    category_ar: str
    category_en: str
    icon: str
    input_ext: tuple[str, ...]
    output_ext: str
    max_files: int
    local: bool = True
    batch: bool = False
    param_field: str = ""
    param_label_ar: str = ""
    param_label_en: str = ""
    param_placeholder_ar: str = ""
    param_placeholder_en: str = ""
    param_default: str = ""
    input_required: bool = True
    fields: tuple[FormField, ...] = ()
