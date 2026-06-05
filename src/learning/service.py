from __future__ import annotations

from src.learning.entities import LearningPlan, LearningPlanSegment
from src.materials.entities import MaterialItem, MaterialType


PURPOSE_BY_TYPE: dict[MaterialType, str] = {
    MaterialType.TEXT: "Extract key ideas from manually entered text.",
    MaterialType.SCREENSHOT: "Recognize visual text and extract reusable knowledge.",
    MaterialType.DOCUMENT: "Parse document structure and plan knowledge segments.",
    MaterialType.MEDIA: "Transcribe or read subtitles before knowledge extraction.",
    MaterialType.LINK: "Resolve the link into a processable material before learning.",
}


class MaterialLearningPlanner:
    def create_plan(self, materials: tuple[MaterialItem, ...] | list[MaterialItem]) -> LearningPlan:
        items = tuple(materials)
        segments = tuple(self._segment_for(index, item) for index, item in enumerate(items, start=1))
        return LearningPlan(
            summary=f"{len(segments)} material(s) ready for learning.",
            segments=segments,
        )

    def _segment_for(self, index: int, item: MaterialItem) -> LearningPlanSegment:
        estimated_chars = len(item.content or item.source_ref or item.title)
        return LearningPlanSegment(
            id=f"learn-{index}",
            material_id=item.id,
            material_type=item.material_type,
            title=item.title,
            purpose=PURPOSE_BY_TYPE[item.material_type],
            estimated_chars=estimated_chars,
        )
