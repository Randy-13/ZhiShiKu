from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MaterialType(str, Enum):
    TEXT = "text"
    SCREENSHOT = "screenshot"
    DOCUMENT = "document"
    MEDIA = "media"
    LINK = "link"


class MaterialStatus(str, Enum):
    LOCAL = "local"
    UPLOADED = "uploaded"
    PARSED = "parsed"
    PLANNED = "planned"
    READY_FOR_LEARNING = "ready_for_learning"
    ERROR = "error"


@dataclass(frozen=True)
class MaterialItem:
    id: str
    material_type: MaterialType
    title: str
    status: MaterialStatus
    content: str = ""
    source_ref: str = ""


def infer_material_title(material_type: MaterialType, content: str, fallback: str = "Untitled material") -> str:
    cleaned = " ".join(content.strip().split())
    if cleaned:
        return cleaned[:40]
    return f"{material_type.value}: {fallback}"
