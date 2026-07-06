from __future__ import annotations

from pydantic import BaseModel, Field


class OcrResult(BaseModel):
    title_hint: str = Field(default="", description="A concise title inferred from the screenshot.")
    topic_hint: str = Field(default="", description="The main topic inferred from the screenshot.")
    cleaned_text: str = Field(default="", description="Cleaned OCR text from the screenshot.")


class OcrBatchResult(BaseModel):
    combined_text: str
    mode: str


class RawMaterialPolishResult(BaseModel):
    title: str = Field(default="", description="A concise, human-readable material title.")
    markdown: str = Field(default="", description="Cleaned raw-material Markdown without knowledge extraction.")


class ReadableDocumentResult(BaseModel):
    title: str = Field(default="", description="A concise title inferred from the source text.")
    note: str = Field(default="", description="Short note about source scope and cleanup assumptions.")
    markdown: str = Field(default="", description="Readable Markdown that preserves source content without knowledge extraction.")


class PerspectiveFinding(BaseModel):
    dimension: str
    interpretation: str
    evidence_refs: list[str] = Field(default_factory=list)


class PerspectiveInterpretationResult(BaseModel):
    title: str
    perspective_name: str
    tags: list[str] = Field(default_factory=list)
    summary: str = ""
    criteria: str = ""
    core_facts: list[PerspectiveFinding] = Field(default_factory=list)
    deep_analysis: list[PerspectiveFinding] = Field(default_factory=list)
    conclusion_and_actions: list[str] = Field(default_factory=list)
    findings: list[PerspectiveFinding] = Field(default_factory=list)
    writing_implications: list[str] = Field(default_factory=list)
    risks_and_limits: list[str] = Field(default_factory=list)
    risks_and_questions: list[str] = Field(default_factory=list)


class KnowledgeCluster(BaseModel):
    name: str
    domain: str
    occurrence_count: int = Field(default=1, ge=1)
    meaning: str
    key_information: list[str] = Field(default_factory=list)


class KnowledgeResult(BaseModel):
    title: str
    topic: str
    tags: list[str] = Field(default_factory=list)
    focus_question: str
    clusters: list[KnowledgeCluster] = Field(default_factory=list)
    investment_insights: str


class KnowledgeDraftMeta(BaseModel):
    title: str = Field(default="", description="A concise article-ready title for the knowledge draft.")
    note: str = Field(default="", description="A short editable note that explains source scope and review focus.")


class CreationStrategyResult(BaseModel):
    title: str
    strategy_type: str = "creation_strategy"
    applicable_scenarios: list[str] = Field(default_factory=list)
    author_style_profile: list[str] = Field(default_factory=list)
    topic_strategy: list[str] = Field(default_factory=list)
    structure_strategy: list[str] = Field(default_factory=list)
    opening_patterns: list[str] = Field(default_factory=list)
    transition_patterns: list[str] = Field(default_factory=list)
    ending_patterns: list[str] = Field(default_factory=list)
    language_style: list[str] = Field(default_factory=list)
    rhythm_and_emotion: list[str] = Field(default_factory=list)
    short_video_talk_strategy: list[str] = Field(default_factory=list)
    reusable_templates: list[str] = Field(default_factory=list)
    anti_patterns: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    usage_notes: str = ""
    summary: str = ""


class DocumentPlanSegment(BaseModel):
    id: str
    title: str
    theme: str
    file_id: int = 0
    file_name: str = ""
    page_start: int | None = None
    page_end: int | None = None
    page_ranges: str = ""
    reason: str = ""
    estimated_chars: int = 0
    selected: bool = True


class DocumentPlanResult(BaseModel):
    file_id: int = 0
    file_name: str = ""
    file_type: str = ""
    page_count: int = 0
    total_chars: int = 0
    long_document: bool = False
    summary: str = ""
    segments: list[DocumentPlanSegment] = Field(default_factory=list)


class TopicSuggestion(BaseModel):
    title: str
    angle: str
    reason: str
    reader_pain_point: str
    material_basis: str
    reference_files: list[str] = Field(default_factory=list)


class TopicSuggestionsResult(BaseModel):
    suggestions: list[TopicSuggestion] = Field(default_factory=list)


class XhsTopicSuggestion(BaseModel):
    content_pillar: str
    user_pain_point: str
    title_hook: str
    topic_angle: str
    note_format: str
    carousel_count: int = Field(default=5, ge=1, le=7)
    cover_hook: str
    slide_flow: list[str] = Field(default_factory=list)
    value_points: list[str] = Field(default_factory=list)
    material_basis: str
    reference_files: list[str] = Field(default_factory=list)
    tag_keywords: list[str] = Field(default_factory=list)
    cta: str = ""
    risk_boundary: str = ""


class XhsTopicSuggestionsResult(BaseModel):
    suggestions: list[XhsTopicSuggestion] = Field(default_factory=list)


class GraphIngestionResult(BaseModel):
    primary_category: str
    secondary_category: str
    node_name: str
    summary: str
    keywords: list[str] = Field(default_factory=list)
    relation_type: str = "关联"
    relation_description: str = ""


class ExtractedTermNode(BaseModel):
    name: str
    category: str = "信息视野拓展"
    term_type: str = "概念"
    aliases: list[str] = Field(default_factory=list)
    importance: int = Field(default=3, ge=1, le=5)
    summary: str = ""


class TermRelation(BaseModel):
    source: str
    target: str
    relation_type: str = "关联"
    evidence: str = ""
    confidence: float = Field(default=0.75, ge=0, le=1)


class KnowledgeNetworkExtraction(BaseModel):
    nodes: list[ExtractedTermNode] = Field(default_factory=list)
    relations: list[TermRelation] = Field(default_factory=list)


class GraphGroup(BaseModel):
    name: str
    category: str = "信息视野拓展"
    summary: str = ""
    child_nodes: list[str] = Field(default_factory=list)


class GraphOrganizationResult(BaseModel):
    groups: list[GraphGroup] = Field(default_factory=list)


class RetrievalAnswer(BaseModel):
    answer: str
    matched_categories: list[str] = Field(default_factory=list)
    reference_files: list[str] = Field(default_factory=list)
    follow_up_suggestions: list[str] = Field(default_factory=list)


class WriterArticleResult(BaseModel):
    title: str
    markdown: str
    cover_prompt: str
    content_image_prompts: list[str] = Field(default_factory=list)
    digest: str = ""


class WriterRevisionResult(BaseModel):
    markdown: str
    change_summary: str = ""
    cover_prompt: str = ""
    content_image_prompts: list[str] = Field(default_factory=list)


class WriterImageSuggestionResult(BaseModel):
    cover_prompt: str
    content_image_prompts: list[str] = Field(default_factory=list)
    rationale: str = ""
