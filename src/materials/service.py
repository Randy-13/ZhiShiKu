from __future__ import annotations

from dataclasses import dataclass, field

from src.materials.entities import MaterialItem, MaterialStatus, MaterialType, infer_material_title


@dataclass
class MaterialCollection:
    items: list[MaterialItem] = field(default_factory=list)

    def add_text(self, content: str) -> MaterialItem:
        value = content.strip()
        if not value:
            raise ValueError("Text material cannot be empty")
        return self._append(MaterialType.TEXT, content=value)

    def add_link(self, url: str) -> MaterialItem:
        value = url.strip()
        if not value:
            raise ValueError("Link material cannot be empty")
        if not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError("Link material must start with http:// or https://")
        existing = next((item for item in self.items if item.material_type == MaterialType.LINK and item.source_ref == value), None)
        if existing:
            return existing
        return self._append(MaterialType.LINK, source_ref=value, content=value)

    def add_external_ref(self, material_type: MaterialType, source_ref: str, title: str = "") -> MaterialItem:
        if material_type in {MaterialType.TEXT, MaterialType.LINK}:
            raise ValueError("Use add_text or add_link for text and link materials")
        value = source_ref.strip()
        if not value:
            raise ValueError("Material source reference cannot be empty")
        return self._append(material_type, source_ref=value, title=title or value)

    def ready_for_learning(self) -> tuple[MaterialItem, ...]:
        return tuple(item for item in self.items if item.status != MaterialStatus.ERROR)

    def _append(
        self,
        material_type: MaterialType,
        content: str = "",
        source_ref: str = "",
        title: str = "",
    ) -> MaterialItem:
        item = MaterialItem(
            id=f"{material_type.value}-{len(self.items) + 1}",
            material_type=material_type,
            title=title or infer_material_title(material_type, content or source_ref),
            content=content,
            source_ref=source_ref,
            status=MaterialStatus.LOCAL,
        )
        self.items.append(item)
        return item
