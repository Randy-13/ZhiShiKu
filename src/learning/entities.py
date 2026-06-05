from __future__ import annotations

from dataclasses import dataclass

from src.materials.entities import MaterialType


@dataclass(frozen=True)
class LearningPlanSegment:
    id: str
    material_id: str
    material_type: MaterialType
    title: str
    purpose: str
    estimated_chars: int
    selected: bool = True


@dataclass(frozen=True)
class LearningPlan:
    summary: str
    segments: tuple[LearningPlanSegment, ...]

    @property
    def selected_segments(self) -> tuple[LearningPlanSegment, ...]:
        return tuple(segment for segment in self.segments if segment.selected)
