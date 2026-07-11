from __future__ import annotations

import base64
import json
import mimetypes
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    OpenAI,
    OpenAIError,
    PermissionDeniedError,
    RateLimitError,
)
from pydantic import BaseModel, ValidationError

import api_settings
import config
from schemas import (
    CreationStrategyResult,
    DocumentPlanResult,
    GraphIngestionResult,
    GraphOrganizationResult,
    KnowledgeDraftMeta,
    KnowledgeNetworkExtraction,
    KnowledgeResult,
    PerspectiveInterpretationResult,
    ReadableDocumentResult,
    RawMaterialPolishResult,
    RetrievalAnswer,
    TopicSuggestionsResult,
    WriterArticleResult,
    WriterImageSuggestionResult,
    WriterRevisionResult,
)

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
PERSPECTIVE_INTERPRETATION_PROMPT = PROMPTS_DIR / "perspective_interpretation.md"


def _read_prompt_template(path: Path, fallback: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return fallback


def _fill_template(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    return rendered


def current_setting(setting: dict[str, Any] | None = None) -> dict[str, Any]:
    return setting or api_settings.active_setting()


def ensure_credentials(setting: dict[str, Any] | None = None) -> dict[str, Any]:
    resolved = current_setting(setting)
    if resolved.get("api_key"):
        return resolved
    raise RuntimeError("当前 API 配置缺少 API Key。请在“API 设置”中补充后保存。")


def client(setting: dict[str, Any] | None = None) -> OpenAI:
    resolved = ensure_credentials(setting)
    return OpenAI(
        api_key=resolved["api_key"],
        base_url=resolved["base_url"],
        timeout=float(resolved.get("timeout") or config.LLM_TIMEOUT),
        max_retries=int(resolved.get("max_retries") or config.LLM_MAX_RETRIES),
    )


def is_anthropic_compatible(setting: dict[str, Any] | None = None) -> bool:
    resolved = current_setting(setting)
    provider = str(resolved.get("provider") or "").lower()
    base_url = str(resolved.get("base_url") or "").lower()
    return provider == "minimax" or "minimaxi.com/anthropic" in base_url


def chat_url(setting: dict[str, Any] | None = None) -> str:
    resolved = current_setting(setting)
    base = resolved["base_url"].rstrip("/")
    if is_anthropic_compatible(resolved):
        if base.endswith("/messages"):
            return base
        return base + "/messages"
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return base + "/chat/completions"
    return base + "/chat/completions"


def explain_error(exc: Exception, setting: dict[str, Any] | None = None) -> str:
    try:
        resolved = current_setting(setting)
        provider = resolved.get("provider") or "api"
        model = resolved.get("model") or "unknown"
        base_url = resolved.get("base_url") or ""
    except Exception:
        provider = "api"
        model = "unknown"
        base_url = ""
    if isinstance(exc, AuthenticationError):
        return f"{provider} 认证失败：API Key 无效，或当前 API 设置没有保存正确 Key。"
    if isinstance(exc, PermissionDeniedError):
        return f"{provider} 权限不足：当前 API Key 无权使用模型 {model}。"
    if isinstance(exc, NotFoundError):
        return f"{provider} 模型不可用：找不到模型 {model}。请检查 API 设置里的模型名称。"
    if isinstance(exc, BadRequestError):
        return f"{provider} 请求参数错误：{exc}"
    if isinstance(exc, RateLimitError):
        return f"{provider} 限流或额度不足：请检查账户额度和限速。"
    if isinstance(exc, APITimeoutError):
        return f"{provider} 请求超时。可以稍后重试，或在 API 设置里把 timeout 调大。"
    if isinstance(exc, APIConnectionError):
        return (
            f"无法连接 {provider} API。请检查网络、代理、防火墙或 Base URL（{base_url}）。"
            f"原始错误：{exc}"
        )
    if isinstance(exc, APIStatusError):
        return f"{provider} API 返回错误 {exc.status_code}：{exc.response.text}"
    if isinstance(exc, ValidationError):
        return f"{provider} 返回的 JSON 不符合应用 schema：{exc}"
    if isinstance(exc, OpenAIError):
        return f"{provider} OpenAI-compatible SDK 错误：{exc}"
    return str(exc)


def parse_json_model(
    model_type: type[BaseModel],
    messages: list[dict[str, str]],
    setting: dict[str, Any] | None = None,
) -> BaseModel:
    resolved = current_setting(setting)
    schema = model_type.model_json_schema()
    schema_hint = json.dumps(schema, ensure_ascii=False)
    system = {
        "role": "system",
        "content": (
            "You are a strict JSON generator. Output valid JSON only, with no Markdown and no explanation. "
            "The JSON must match this schema exactly. All user-facing text values must be written in Chinese.\n"
            + schema_hint
        ),
    }
    try:
        content = sdk_chat_completion([system, *messages], json_mode=True, setting=resolved)
        return _validate_json_model_response(model_type, content)
    except ValidationError as exc:
        try:
            repaired = sdk_chat_completion(
                [
                    system,
                    *messages,
                    {
                        "role": "assistant",
                        "content": str(content or "")[:12000],
                    },
                    {
                        "role": "user",
                        "content": (
                            "上一条回复不是合法 JSON，应用无法解析。请只返回一个完整、合法、可被 json.loads "
                            "解析的 JSON 对象，不要 Markdown，不要解释，不要截断。"
                            f"\n解析错误：{exc}"
                        ),
                    },
                ],
                json_mode=True,
                setting=resolved,
            )
            return _validate_json_model_response(model_type, repaired)
        except Exception as repair_exc:
            raise RuntimeError(explain_error(repair_exc, resolved)) from repair_exc
    except APIConnectionError:
        content = curl_chat_completion([system, *messages], json_mode=True, setting=resolved)
        return _validate_json_model_response(model_type, content)
    except Exception as exc:
        raise RuntimeError(explain_error(exc, resolved)) from exc


def _validate_json_model_response(model_type: type[BaseModel], content: str) -> BaseModel:
    return model_type.model_validate_json(_normalize_json_response_text(content))


def _normalize_json_response_text(content: str) -> str:
    text = str(content or "").strip()
    if not text:
        return "{}"

    text = re.sub(r"(?is)<think\b[^>]*>.*?</think>", "", text).strip()
    text = re.sub(r"(?is)^```(?:json)?\s*", "", text)
    text = re.sub(r"(?is)\s*```$", "", text).strip()

    if text.startswith("{") or text.startswith("["):
        return text

    start_positions = [pos for pos in (text.find("{"), text.find("[")) if pos >= 0]
    if not start_positions:
        return text

    start = min(start_positions)
    candidate = text[start:].strip()
    if candidate.startswith("{"):
        end = candidate.rfind("}")
        if end >= 0:
            return candidate[: end + 1]
    if candidate.startswith("["):
        end = candidate.rfind("]")
        if end >= 0:
            return candidate[: end + 1]
    return candidate


def sdk_chat_completion(
    messages: list[dict[str, str]],
    json_mode: bool = False,
    setting: dict[str, Any] | None = None,
) -> str:
    resolved = current_setting(setting)
    if is_anthropic_compatible(resolved):
        return anthropic_chat_completion(messages, json_mode=json_mode, setting=resolved)
    request: dict[str, Any] = {
        "model": resolved["model"],
        "messages": messages,
        "temperature": 0.2,
    }
    if json_mode:
        request["response_format"] = {"type": "json_object"}
    response = client(resolved).chat.completions.create(**request)
    return response.choices[0].message.content or "{}"


def anthropic_chat_completion(
    messages: list[dict[str, str]],
    json_mode: bool = False,
    setting: dict[str, Any] | None = None,
) -> str:
    resolved = ensure_credentials(setting)
    system_messages = [item.get("content", "") for item in messages if item.get("role") == "system"]
    conversation = [
        {
            "role": item.get("role") if item.get("role") in {"user", "assistant"} else "user",
            "content": item.get("content", ""),
        }
        for item in messages
        if item.get("role") != "system"
    ]
    if not conversation:
        conversation = [{"role": "user", "content": "Reply with ok."}]
    system = "\n\n".join(part for part in system_messages if part)
    if json_mode:
        system = (system + "\n\n" if system else "") + "Output valid JSON only."
    payload: dict[str, Any] = {
        "model": resolved["model"],
        "messages": conversation,
        "max_tokens": 2048,
        "temperature": 0.2,
    }
    if system:
        payload["system"] = system
    request = urllib.request.Request(
        chat_url(resolved),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-api-key": resolved["api_key"],
            "Authorization": f"Bearer {resolved['api_key']}",
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=float(resolved.get("timeout") or config.LLM_TIMEOUT)) as response:
            response_text = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        response_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"MiniMax Anthropic HTTP {exc.code}: {response_text[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"MiniMax Anthropic request failed: {exc}") from exc
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"MiniMax Anthropic returned non-JSON content: {response_text[:500]}") from exc
    if "error" in data:
        raise RuntimeError(f"MiniMax Anthropic API error: {data['error']}")
    content = data.get("content")
    if isinstance(content, list):
        texts = [item.get("text", "") for item in content if isinstance(item, dict)]
        return "\n".join(text for text in texts if text) or "{}"
    if isinstance(content, str):
        return content
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"MiniMax Anthropic response structure is unexpected: {response_text[:500]}") from exc

def curl_chat_completion(
    messages: list[dict[str, str]],
    json_mode: bool = False,
    setting: dict[str, Any] | None = None,
) -> str:
    resolved = ensure_credentials(setting)
    provider = resolved.get("provider") or "API"
    model = resolved.get("model") or "unknown"
    payload: dict[str, Any] = {
        "model": resolved["model"],
        "messages": messages,
        "temperature": 0.2,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    body = json.dumps(payload, ensure_ascii=False)
    command = [
        "curl.exe",
        "-s",
        "-S",
        "--connect-timeout",
        "20",
        "--max-time",
        str(int(float(resolved.get("timeout") or config.LLM_TIMEOUT))),
        "-w",
        "\nHTTP_STATUS:%{http_code}",
        "-X",
        "POST",
        chat_url(resolved),
        "-H",
        f"Authorization: Bearer {resolved['api_key']}",
        "-H",
        "Content-Type: application/json",
        "--data-binary",
        "@-",
    ]
    timeout_seconds = float(resolved.get("timeout") or config.LLM_TIMEOUT)
    try:
        completed = subprocess.run(
            command,
            input=body,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{provider} 模型 {model} 请求超过 {timeout_seconds:g} 秒未返回，请尝试更换模型或调大超时秒数。") from exc
    raw_output = completed.stdout or ""
    response_text, _, status_text = raw_output.rpartition("\nHTTP_STATUS:")
    status_code = status_text.strip() if status_text else "000"
    if completed.returncode != 0:
        raise RuntimeError(
            f"{provider} 模型 {model} curl 请求失败 rc={completed.returncode} status={status_code}: "
            f"{completed.stderr or response_text}"
        )
    if not status_code.startswith("2"):
        raise RuntimeError(f"{provider} 模型 {model} HTTP {status_code}: {response_text[:1000]}")
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{provider} 模型 {model} 返回了非 JSON 内容：{response_text[:500]}") from exc
    if "error" in data:
        raise RuntimeError(f"{provider} 模型 {model} API 错误：{data['error']}")
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"{provider} 模型 {model} 返回结构异常：{response_text[:500]}") from exc


def generate_knowledge(raw_text: str, setting: dict[str, Any] | None = None) -> KnowledgeResult:
    prompt = f"""
你是个人财经、宏观、投资、产业趋势学习知识库助手。请只基于下面 OCR 文本生成结构化知识簇。

硬性要求：
1. 不引入 OCR 文本之外的事实、概念、行业背景或判断。
2. 知识簇使用 atomic notes 思想，但不要拆成多个文件。
3. 每个知识簇必须可独立解释、可独立搜索。
4. 总是同时出现且无法独立解释的信息应合并。
5. 知识簇名称尽量压缩为“实体；产品/事件；关键数值/时间/地点”。
6. 标签使用 2 到 6 个中文短标签。
7. 投资启发要是外化思考，不要空泛复述。
8. 如果 OCR 文本来自多张截图，把它们视为同一轮完整知识输入，合并分析。

OCR 文本：
{raw_text}
"""
    return parse_json_model(KnowledgeResult, [{"role": "user", "content": prompt}], setting=setting)


def generate_knowledge_from_text(
    raw_text: str,
    setting: dict[str, Any] | None = None,
) -> tuple[KnowledgeResult, str]:
    return generate_knowledge(raw_text, setting=setting), raw_text


def generate_knowledge_draft_meta(
    materials: list[dict[str, str]],
    body: str,
    language: str = "zh",
    setting: dict[str, Any] | None = None,
) -> KnowledgeDraftMeta:
    compact_materials = [
        {
            "title": str(item.get("title") or "")[:120],
            "type": str(item.get("type") or "")[:40],
            "source": str(item.get("source") or "")[:200],
        }
        for item in materials[:12]
    ]
    lang_hint = "Chinese" if language == "zh" else "English"
    prompt = f"""
You are preparing an editable knowledge draft for a personal knowledge base.
Generate only metadata for the draft, not the full article body.

Requirements:
1. The title must be concise, article-ready, and based only on the provided draft body and source list.
2. The note must be a short review note that helps the user understand source scope, uncertainty, or what to check before committing.
3. Do not add external facts.
4. Output language: {lang_hint}.

Source materials:
{json.dumps(compact_materials, ensure_ascii=False)}

Draft body:
{body[:16000]}
"""
    return parse_json_model(KnowledgeDraftMeta, [{"role": "user", "content": prompt}], setting=setting)


def polish_raw_material(
    raw_text: str,
    material_type: str = "raw",
    setting: dict[str, Any] | None = None,
) -> RawMaterialPolishResult:
    prompt = f"""
你是“知识酷 Research OS”的原料清洗助手。请只做原料级整理，不做知识提炼、不生成知识簇、不补充外部事实。

任务：
1. 根据原始文本推断一个短标题，适合作为 Markdown 文件名，避免使用“截图原料”“clip”“raw”等泛名。
2. 把 OCR/转写/抓取文本整理成一篇干净可读的原文级 Markdown。
3. 可以删除明显的 OCR 噪声、重复导航、无意义乱码和残缺按钮文字。
4. 必须保留原文中可见的事实、数字、公司名、人名、时间、引用和关键表述。
5. 不要总结成观点清单，不要写“核心知识点”，不要加入材料外的信息。
6. 如果文本很短，也要尽量给出主题标题，并保留原文。

截图类材料的额外硬性要求：
1. 删除所有 OCR 包装信息，例如 [Screenshot N]、Title hint、Topic hint、Recognized text。
2. 如果多张截图来自同一篇文章，必须按文章自然阅读顺序合并。
3. 如果正文存在“1）/2）/3）/4）”等编号段落且 OCR 顺序错乱，必须按编号从小到大重排；标题、导语、总览数据放在“1）”之前。
4. 只调整截图块/编号段落的顺序，不改写原文事实和数字，不把原文提炼成知识点。

材料类型：{material_type}
原始文本：
{raw_text[:24000]}
"""
    return parse_json_model(RawMaterialPolishResult, [{"role": "user", "content": prompt}], setting=setting)


def clean_readable_document(
    raw_text: str,
    material_type: str = "raw",
    setting: dict[str, Any] | None = None,
) -> ReadableDocumentResult:
    prompt = f"""
You are a meticulous OCR and transcript cleanup editor for a personal knowledge base.
Your job is to turn extracted source text into a readable Markdown document.

Hard requirements:
1. Preserve the source's actual content, order, wording, numbers, names, and paragraph meaning as much as possible.
2. Remove only obvious UI noise, navigation labels, repeated OCR headers, page markers, OCR wrapper labels, timestamps that are not part of the main content, and duplicated junk.
3. Do not summarize into bullet-point knowledge notes.
4. Do not add external facts, explanations, opinions, or background.
5. Use headings only when the source clearly has title/sections or the text naturally implies numbered sections.
6. If the source is multiple screenshots/pages from the same article, merge them into one continuous readable document.
7. Do not preserve screenshot-style visual hard wraps inside ordinary paragraphs; rewrite them into natural Markdown paragraphs while keeping paragraph boundaries.
8. Output Chinese when the source is Chinese; otherwise keep the source language.

Material type: {material_type}

Extracted source text:
{raw_text[:30000]}
"""
    return parse_json_model(ReadableDocumentResult, [{"role": "user", "content": prompt}], setting=setting)


def interpret_from_perspective(
    material_blocks: list[dict[str, str]],
    perspective: dict[str, Any],
    setting: dict[str, Any] | None = None,
) -> PerspectiveInterpretationResult:
    source_text = []
    for index, item in enumerate(material_blocks, start=1):
        source_text.append(
            "\n".join(
                [
                    f"[S{index}: {item.get('title') or item.get('relative_path')}]",
                    f"Library: {item.get('library')}",
                    f"Path: {item.get('relative_path')}",
                    "",
                    str(item.get("text") or "")[:12000],
                ]
            )
        )
    fallback = """
You are the mining module of Knowledge Cool Research OS.

Interpret the materials only from the configured perspective and return JSON that matches the schema exactly.

Perspective name: {{perspective_name}}
Positioning: {{positioning}}
Core goal: {{core_goal}}
Stance: {{stance}}
Role: {{role}}
Target subject: {{target_subject}}
Purpose: {{purpose}}
Focus dimensions: {{focus_dimensions}}
Analysis questions: {{analysis_questions}}
Output style: {{output_style}}
Evidence rule: {{evidence_rule}}

Hard requirements:
1. Follow RTFC strictly: define the rule/standard first, stay on the target, anchor every key judgment in source facts, then give perspective-specific conclusions.
2. Use a fixed five-part output logic:
   - criteria
   - core_facts
   - deep_analysis
   - risks_and_questions
   - conclusion_and_actions
3. core_facts and deep_analysis may use evidence_refs such as S1/S2/S3 internally for traceability, but user-facing interpretation text must not include visible citation labels like "引用：S1".
4. deep_analysis must go beyond paraphrase. It should explain causal links, hidden tensions, decision tradeoffs, scenario implications, and what the material suggests but does not fully state.
5. You may add limited contextual inference, but only when it is clearly derived from the sources. Do not invent outside facts. When something is inference rather than explicit fact, say so plainly in the interpretation text.
6. risks_and_questions should capture uncertainty, missing evidence, contradictory signals, and what must be verified next.
7. conclusion_and_actions should be concrete and perspective-specific, not generic summaries.

Return JSON with this shape:
{
  "title": "string",
  "perspective_name": "string",
  "tags": ["string"],
  "summary": "short paragraph",
  "criteria": "the perspective's judging standard",
  "core_facts": [
    {"dimension": "string", "interpretation": "string", "evidence_refs": ["S1"]}
  ],
  "deep_analysis": [
    {"dimension": "string", "interpretation": "string", "evidence_refs": ["S1", "S2"]}
  ],
  "risks_and_questions": ["string"],
  "conclusion_and_actions": ["string"],
  "findings": [],
  "writing_implications": [],
  "risks_and_limits": []
}

Materials:
{{source_text}}
"""
    template = _read_prompt_template(PERSPECTIVE_INTERPRETATION_PROMPT, fallback)
    prompt = _fill_template(
        template,
        {
            "perspective_name": str(perspective.get("name", "")),
            "positioning": str(perspective.get("positioning") or perspective.get("role", "")),
            "core_goal": str(perspective.get("core_goal") or perspective.get("purpose", "")),
            "stance": str(perspective.get("stance") or perspective.get("evidence_rule", "")),
            "role": str(perspective.get("role", "")),
            "target_subject": str(perspective.get("target_subject", "")),
            "purpose": str(perspective.get("purpose", "")),
            "focus_dimensions": json.dumps(perspective.get("focus_dimensions", []), ensure_ascii=False),
            "analysis_questions": json.dumps(perspective.get("analysis_questions", []), ensure_ascii=False),
            "output_style": str(perspective.get("output_style", "")),
            "evidence_rule": str(perspective.get("evidence_rule", "")),
            "source_text": chr(10).join(source_text),
        },
    )
    return parse_json_model(PerspectiveInterpretationResult, [{"role": "user", "content": prompt}], setting=setting)


def expand_perspective_interpretation(
    material_blocks: list[dict[str, str]],
    perspective: dict[str, Any],
    current_markdown: str,
    external_sources: list[dict[str, str]],
    expansion_instruction: str = "",
    setting: dict[str, Any] | None = None,
) -> PerspectiveInterpretationResult:
    source_text = []
    for index, item in enumerate(material_blocks, start=1):
        source_text.append(
            "\n".join(
                [
                    f"[S{index}: {item.get('title') or item.get('relative_path')}]",
                    f"Library: {item.get('library')}",
                    f"Path: {item.get('relative_path')}",
                    "",
                    str(item.get("text") or "")[:9000],
                ]
            )
        )
    evidence_text = []
    for index, item in enumerate(external_sources, start=1):
        evidence_text.append(
            "\n".join(
                [
                    f"[E{index}: {item.get('title') or item.get('url')}]",
                    f"Authority: {item.get('authority') or 'supplemental'}",
                    f"URL: {item.get('url') or item.get('relative_path')}",
                    f"Search query: {item.get('query') or ''}",
                    "",
                    str(item.get("text") or "")[:7000],
                ]
            )
        )
    prompt = f"""
You are expanding a saved perspective interpretation for Knowledge Cool Research OS.

Perspective name: {perspective.get("name", "")}
Positioning: {perspective.get("positioning") or perspective.get("role", "")}
Core goal: {perspective.get("core_goal") or perspective.get("purpose", "")}
Stance: {perspective.get("stance") or perspective.get("evidence_rule", "")}
Focus dimensions: {json.dumps(perspective.get("focus_dimensions", []), ensure_ascii=False)}
Analysis questions: {json.dumps(perspective.get("analysis_questions", []), ensure_ascii=False)}
User expansion command: {expansion_instruction.strip() or "补全信息链条、加强官方或权威证据、修正不充分的论据。"}

Hard requirements:
1. Keep the original RTFC discipline: Rule, Target, Fact, Conclusion.
2. Keep the same fixed five-part output logic: criteria, core_facts, deep_analysis, risks_and_questions, conclusion_and_actions.
3. Use original material refs as S1/S2/S3 and external evidence refs as E1/E2/E3 internally for traceability. Do not put visible citation labels like "引用：S1" or "引用：E1" in user-facing interpretation text.
4. Follow the user expansion command first when choosing what to strengthen, verify, compare, or question.
5. Expand the existing interpretation by strengthening the evidence chain. Do not discard useful judgments from the current draft.
6. External sources are official-first. Treat authority=official as strongest evidence, authority=authoritative_supplement as supporting context, and authority=supplemental as weak context.
7. Clearly distinguish facts stated by sources from your inference. Do not invent facts beyond S* and E*.
8. Output Chinese user-facing text only.

Current draft to overwrite with an enhanced version:
{current_markdown[:18000]}

Original source materials:
{chr(10).join(source_text)}

External expansion evidence:
{chr(10).join(evidence_text)}

Return JSON with this shape:
{{
  "title": "string",
  "perspective_name": "string",
  "tags": ["string"],
  "summary": "short paragraph",
  "criteria": "the perspective's judging standard",
  "core_facts": [
    {{"dimension": "string", "interpretation": "string", "evidence_refs": ["S1", "E1"]}}
  ],
  "deep_analysis": [
    {{"dimension": "string", "interpretation": "string", "evidence_refs": ["S1", "E1", "E2"]}}
  ],
  "risks_and_questions": ["string"],
  "conclusion_and_actions": ["string"],
  "findings": [],
  "writing_implications": [],
  "risks_and_limits": []
}}
"""
    return parse_json_model(PerspectiveInterpretationResult, [{"role": "user", "content": prompt}], setting=setting)


def learn_creation_strategy(
    materials: list[tuple[str, str]],
    previous_strategy: str = "",
    setting: dict[str, Any] | None = None,
) -> CreationStrategyResult:
    material_blocks = []
    for index, (title, text) in enumerate(materials, start=1):
        material_blocks.append(f"【S{index}: {title}】\n{text[:12000]}")
    previous_block = previous_strategy.strip()[:12000] if previous_strategy.strip() else "无"
    prompt = f"""
你是创作策略学习助手。请只基于给定作者作品样本，学习可解释、可复用的创作策略 skill。

硬性要求：
1. 不要复述原文，不要生成仿写成品；输出的是创作策略。
2. 每条策略尽量写成可执行规则，例如“先用 X 建立冲突，再用 Y 解释原因”。
3. evidence 必须引用样本编号 S1/S2/S3 等，说明该策略来自哪些样本现象。
4. 如果样本包含文章，重点学习选题、结构、标题、论证、语言风格。
5. 如果样本包含音视频/字幕，重点学习开场钩子、话术节奏、转场、情绪推进、结尾 CTA。
6. 如果有上一版策略，请在其基础上增量完善，不要丢失仍被样本支持的策略。
7. 反例与边界要说明哪些写法“不像这个作者”或只在特定场景适用。

上一版策略：
{previous_block}

作者作品样本：
{chr(10).join(material_blocks)}
"""
    return parse_json_model(CreationStrategyResult, [{"role": "user", "content": prompt}], setting=setting)


def plan_document_knowledge(
    file_name: str,
    file_type: str,
    page_count: int,
    total_chars: int,
    page_overview: str,
    setting: dict[str, Any] | None = None,
) -> DocumentPlanResult:
    prompt = f"""
你是个人知识库的长文档拆解规划助手。请基于下面的 PDF/文件分页概览，先规划应该生成哪些独立 Markdown 知识文件，不要生成正文。

规划要求：
1. 每个 segment 应该对应一个相对完整、可独立复习的主题。
2. 不要机械按页等分；优先按目录标题、主题转折、数据/案例/结论模块拆分。
3. title 要短而明确，适合作为 Markdown 文件标题。
4. theme 说明这个知识文件主要沉淀什么。
5. page_start/page_end 必须给出，覆盖范围尽量不重叠；允许重要页被相邻主题共享，但要少用。
6. 如果内容较短，segments 可以只有 1 个。
7. summary 说明这份文档为什么需要这样拆。

文件名：{file_name}
文件类型：{file_type}
页数/分块数：{page_count}
总字数：{total_chars}

分页概览：
{page_overview}
"""
    return parse_json_model(DocumentPlanResult, [{"role": "user", "content": prompt}], setting=setting)


def image_data_url(image_path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(image_path.name)
    mime_type = mime_type or "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def recognize_screenshots_with_ai(
    image_paths: list[Path],
    setting: dict[str, Any] | None = None,
) -> str:
    resolved = current_setting(setting)
    if not image_paths:
        raise ValueError("No screenshots were provided")

    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                "请逐张识别这些截图中的主要文字内容，只输出纯文本。"
                "要求：1. 保留段落与关键数字；2. 不解释，不总结，不补充截图外信息；"
                "3. 每张截图以 [Screenshot N] 开头分段。"
            ),
        }
    ]
    for index, image_path in enumerate(image_paths, start=1):
        content.append({"type": "text", "text": f"[Screenshot {index}]"})
        content.append({"type": "image_url", "image_url": {"url": image_data_url(image_path)}})

    try:
        return sdk_chat_completion(
            [{"role": "user", "content": content}],
            json_mode=False,
            setting=resolved,
        ).strip()
    except Exception as exc:
        message = explain_error(exc, resolved)
        raise RuntimeError(
            "AI 智能解析失败。当前模型或中转站可能不支持图片输入，或者接口并非标准视觉兼容格式。"
            f"详细原因：{message}"
        ) from exc


def design_wechat_article_html(
    markdown: str,
    design_strategy: str = "",
    setting: dict[str, Any] | None = None,
) -> str:
    resolved = current_setting(setting)
    prompt = f"""
你是微信公众号文章美编。请把下面的 Markdown 文章排版成可直接粘贴到微信公众号编辑器的完整 HTML。

美编策略：
{design_strategy.strip() or "公众号长文：克制、清晰、专业，适合科技/财经长文阅读。"}

硬性要求：
1. 只输出 HTML，不要 Markdown 代码围栏，不要解释。
2. 保留原文标题、正文层级、图片和所有事实，不新增材料外内容。
3. 图片路径必须沿用 Markdown 中的 src/path，不要改名、不要转成远程 URL。
4. 允许使用 section、h1/h2/h3、p、blockquote、ul/ol、table、strong、span、img 等常规标签。
5. 使用内联 style，适合微信公众号粘贴；整体宽度、行距、留白、重点句、引用块、分隔节奏要有明显美编效果。
6. 不要使用 script、iframe、外链 CSS、复杂动画或微信公众号不兼容标签。
7. 对重点段落可以做轻量强调，但不要把全文做成海报。

Markdown：
{markdown[:50000]}
"""
    try:
        html_text = sdk_chat_completion([{"role": "user", "content": prompt}], json_mode=False, setting=resolved).strip()
    except APIConnectionError:
        html_text = curl_chat_completion([{"role": "user", "content": prompt}], json_mode=False, setting=resolved).strip()
    except Exception as exc:
        raise RuntimeError(explain_error(exc, resolved)) from exc

    html_text = re.sub(r"^```(?:html)?\s*", "", html_text, flags=re.I).strip()
    html_text = re.sub(r"\s*```$", "", html_text).strip()
    if not html_text or "<" not in html_text:
        raise RuntimeError("API 美编没有返回可用 HTML")
    if "<html" not in html_text.lower():
        html_text = (
            "<!doctype html>\n<html lang=\"zh-CN\">\n<head><meta charset=\"utf-8\" /></head>\n"
            f"<body>\n{html_text}\n</body>\n</html>"
        )
    return html_text


def generate_topics(
    markdown_files: list[tuple[str, str]],
    setting: dict[str, Any] | None = None,
) -> TopicSuggestionsResult:
    materials = []
    for filename, content in markdown_files:
        materials.append(f"【参考知识文件：{filename}】\n{content}")
    joined = "\n\n---\n\n".join(materials)
    prompt = f"""
你是财经/产业趋势内容选题策划助手。请只基于用户选中的知识文件生成原创选题建议。

硬性约束：
1. 不引用未选中的历史内容。
2. 不使用固定行业模板。
3. 不引入材料之外的事实、概念或背景。
4. 相同信息不要重复纳入多个选题。
5. 生成数量由材料密度决定，宁缺毋滥。
6. 每条选题必须差异化强、有思考深度、贴合大众阅读痛点。
7. 不要复述材料，要说明为什么这个选题值得写。
8. 每条选题必须包含标题、创作切入点、选择理由、读者痛点、素材依据、参考知识文件。

选中的知识文件如下：
{joined}
"""
    return parse_json_model(TopicSuggestionsResult, [{"role": "user", "content": prompt}], setting=setting)


def generate_wechat_article(
    topic: dict[str, Any],
    markdown_files: list[tuple[str, str]],
    writing_strategy: str = "",
    setting: dict[str, Any] | None = None,
) -> WriterArticleResult:
    materials = []
    for filename, content in markdown_files:
        materials.append(f"【本地知识文件：{filename}】\n{content[:12000]}")
    joined = "\n\n---\n\n".join(materials)
    topic_json = json.dumps(topic, ensure_ascii=False)
    prompt = f"""
你是微信公众号科技/财经文章作者。请基于用户选中的本地知识文件与选题，生成一篇适合公众号发布的中文 Markdown 文章。

写作要求：
1. 核心依据必须来自所选本地知识文件；如果当前 API/模型具备联网能力，可以补充背景，但必须服务于选题，不要喧宾夺主。
2. 面向普通读者，用清晰问题意识开篇，不要堆材料，不要写成研报摘要。
3. 文章要有原创判断链：现象 -> 关键变量 -> 可能影响 -> 普通读者为什么要关心。
4. 字数建议 1800 到 3000 字；短句、自然、有节奏。
5. Markdown 只输出标题、封面图占位、正文和结尾总结；不要添加“参考资料”“图片说明”“优缺点”等额外章节。
6. 链接若出现，使用纯文本 URL，不要使用 Markdown 超链接格式。
7. 必须生成封面图提示词 cover_prompt，要求简体中文文字、少量文字、主题明确。
8. content_image_prompts 仅在文章确实需要数据对比图、结构图或流程图时给 0 到 2 条。
9. markdown 正文第一张图使用：![封面图](cover.png)
10. digest 控制在 120 个中文字符以内，适合作为公众号摘要。

项目写文策略：
{writing_strategy.strip() or "使用系统默认公众号写文策略。"}

选题：
{topic_json}

所选本地知识文件：
{joined}
"""
    return parse_json_model(WriterArticleResult, [{"role": "user", "content": prompt}], setting=setting)


def revise_wechat_article(
    current_markdown: str,
    instruction: str,
    markdown_files: list[tuple[str, str]],
    setting: dict[str, Any] | None = None,
) -> WriterRevisionResult:
    materials = []
    for filename, content in markdown_files:
        materials.append(f"【本地知识文件：{filename}】\n{content[:9000]}")
    joined = "\n\n---\n\n".join(materials)
    prompt = f"""
你是微信公众号文章编辑。请根据用户修改指令，直接改写当前 Markdown 文章。

约束：
1. 保留公众号文章语气，输出完整修改后的 Markdown，不要只输出修改片段。
2. 修改必须尊重所选本地知识文件，不要引入无依据的新事实。
3. 如果用户要求补充配图，请在 content_image_prompts 中给出新增配图提示词；封面需要重做时才给 cover_prompt。
4. 如果用户要求删减、加强、重排、改标题，都直接执行。
5. markdown 第一张图仍应是：![封面图](cover.png)

用户修改指令：
{instruction}

当前文章：
{current_markdown}

所选本地知识文件：
{joined}
"""
    return parse_json_model(WriterRevisionResult, [{"role": "user", "content": prompt}], setting=setting)


def suggest_writer_images(
    article_markdown: str,
    topic: dict[str, Any] | None = None,
    content_image_count: int = 1,
    image_style_preset: str = "",
    setting: dict[str, Any] | None = None,
) -> WriterImageSuggestionResult:
    topic_json = json.dumps(topic or {}, ensure_ascii=False)
    content_image_count = max(1, min(3, int(content_image_count or 1)))
    style_clause = image_style_preset.strip() or "未指定风格预设时，默认使用适合公众号阅读的简洁信息图风格。"
    prompt = f"""
你是微信公众号文章的视觉策划。请只生成图片建议，不要生成图片。

要求：
1. 必须给 1 条封面图提示词 cover_prompt。
2. content_image_prompts 必须一次性给出 {content_image_count} 条，不能多也不能少；每条对应一张正文图片。
3. 每条提示词要能直接交给图片模型使用，说明主体、构图、风格、文字要求。
4. 图片文字必须要求“简体中文、少量文字、准确可读”。
5. 封面图要适合公众号首图，主题明确，有吸引力，不要堆满文字。
6. 正文配图优先用于解释数据对比、结构关系、流程、关键概念或读者痛点，不要重复封面图。
7. 必须严格吸收下面的图片风格预设，把它落实到封面图和正文图的提示词里。

选题：
{topic_json}

图片风格预设：
{style_clause}

当前文章 Markdown：
{article_markdown[:14000]}
"""
    return parse_json_model(WriterImageSuggestionResult, [{"role": "user", "content": prompt}], setting=setting)


def classify_knowledge_for_graph(
    knowledge: KnowledgeResult,
    existing_nodes: list[dict[str, Any]] | None = None,
    setting: dict[str, Any] | None = None,
) -> GraphIngestionResult:
    existing = existing_nodes or []
    compact_nodes = [
        {
            "label": item.get("label"),
            "level": item.get("level"),
            "primary_category": item.get("primary_category"),
            "secondary_category": item.get("secondary_category"),
        }
        for item in existing[:80]
    ]
    prompt = f"""
你是个人成长认知知识库的知识图谱归类助手。请只基于给定知识结果，生成一个可入网的主题节点归类。

固定六大一级类目，只能从以下名称中选择：
1. 底层思维：通用思维模型、逻辑、方法论、价值观。
2. 社会宏观认知：经济、政策、历史、社会规律与外部世界运行规则。
3. 个人核心能力：情绪、时间、决策、沟通、心态等个人成长能力。
4. 专业职业技能：职业能力、行业认知、变现能力与谋生技能。
5. 生活生存认知：健康、理财、法律、亲密关系等人生基本盘。
6. 信息视野拓展：前沿新知、科学通识、全球视野与认知更新。

要求：
- node_name 是本轮知识入网后的主题节点名，不要超过 20 个汉字。
- secondary_category 是一级类目下的二级分支，边界要清楚，不要太泛。
- summary 用 1 到 3 句话说明这个节点沉淀了什么认知。
- keywords 给 3 到 8 个可检索关键词。
- relation_type 从“支撑、解释、关联、更新、应用、包含”中选一个。
- 不要引入给定知识之外的事实。

现有节点参考：
{json.dumps(compact_nodes, ensure_ascii=False)}

知识结果：
{knowledge.model_dump_json()}
"""
    return parse_json_model(GraphIngestionResult, [{"role": "user", "content": prompt}], setting=setting)


def extract_knowledge_network(
    knowledge: KnowledgeResult,
    existing_nodes: list[dict[str, Any]] | None = None,
    setting: dict[str, Any] | None = None,
) -> KnowledgeNetworkExtraction:
    existing = [
        {
            "label": item.get("label"),
            "node_type": item.get("node_type"),
            "primary_category": item.get("primary_category"),
        }
        for item in (existing_nodes or [])[:120]
        if item.get("node_type") in {"term", "category"}
    ]
    prompt = f"""
你是个人成长知识库的名词入网助手。请只基于给定知识结果，抽取“有信息量、可复习、可检索”的专有名词或稳定概念节点，并给出节点之间的关系。

固定六大一级类目，只能从以下名称中选择：
底层思维、社会宏观认知、个人核心能力、专业职业技能、生活生存认知、信息视野拓展。

抽取规则：
1. 节点名只能是专有名词、实体名、产品名、事件名、技术名、行业名、市场名或稳定概念。
2. 不要把形容词、情绪词、评价词、长标题放进节点，例如“疯狂”“巨无霸”“核心逻辑”“确定性方向”都不要作为节点。
3. 遇到复合标题必须拆开，例如“美股三大巨无霸IPO AI 商业航天”应拆成“美股”“IPO”“AI”“商业航天”；如果材料出现 SpaceX、Starlink星链、Grok AI、Anthropic，也应作为同级或下层相关节点。
4. 同一实体跨材料应复用同一个节点名，例如“长鑫科技科创板IPO”和“长鑫科技与国产DRAM”都应归到“长鑫科技”，并额外抽取“IPO”“DRAM”等方面节点。
5. 节点数量可以比知识文件多。一个 Markdown 可以贡献多个节点，多个 Markdown 也可以共同连接到一个节点。
6. relations 只连接材料中确实共同出现或存在从属/支撑/应用/更新关系的节点，不要为了凑数全连接。
7. 不引入材料之外的新事实。
8. 输出每个节点前必须逐个自问并通过以下四问；任一问题答案为“否”就不要输出：
   - 它是不是一个名词，而不是句子、问题、标题或判断？
   - 它离开原文后是否仍有明确指代？
   - 它是否不是“2025年至2026年一季度业绩变化”这类指标/时间段描述？
   - 它是否不是“哪些、如何、是什么、原因、风险、变化、影响、机会”这类问题残片或泛词？

现有节点参考，可优先复用同名或近义节点：
{json.dumps(existing, ensure_ascii=False)}

知识结果：
{knowledge.model_dump_json()}
"""
    return parse_json_model(KnowledgeNetworkExtraction, [{"role": "user", "content": prompt}], setting=setting)


def answer_retrieval_question(
    question: str,
    markdown_files: list[tuple[str, str]],
    setting: dict[str, Any] | None = None,
) -> RetrievalAnswer:
    joined = "\n\n---\n\n".join(
        f"【参考知识文件：{filename}】\n{content[:8000]}" for filename, content in markdown_files
    )
    prompt = f"""
你是个人成长知识库的知识拉取助手。请只基于下面检索到的本地知识文件回答用户问题，不要引入外部信息。

回答要求：
1. 如果材料较少，直接归纳回答。
2. 如果材料较多，先按主题大类总结，再给出用户可以继续追问的方向。
3. 每个判断都要能从材料中找到依据。
4. reference_files 必须列出实际用到的文件名。
5. follow_up_suggestions 给 2 到 5 个可继续追问的问题或方向。

用户问题：
{question}

检索到的本地材料：
{joined}
"""
    return parse_json_model(RetrievalAnswer, [{"role": "user", "content": prompt}], setting=setting)


def organize_graph_nodes(
    nodes: list[dict[str, Any]],
    setting: dict[str, Any] | None = None,
) -> GraphOrganizationResult:
    compact = [
        {
            "label": item.get("label"),
            "category": item.get("primary_category"),
            "keywords": item.get("keywords", [])[:6],
        }
        for item in nodes
        if item.get("node_type") == "term"
    ][:160]
    prompt = f"""
你是个人成长知识库的图谱整理助手。请只基于已有节点，把庞杂的两层节点整理成更适合学习的中间层分组。

要求：
1. 不新增外部知识，只根据节点名称和关键词归类。
2. 每个 group 是一个学习文件夹/中间层主题，名称要简洁，例如“国产半导体”“AI基础设施”“宏观周期”“资产配置”。
3. child_nodes 必须严格使用已有节点 label，不能编造。
4. 一个节点可以不归组，但不要把无关节点硬塞进同一组。
5. 分组数量由材料决定，通常 5 到 20 个。
6. category 必须从六大类目中选择：底层思维、社会宏观认知、个人核心能力、专业职业技能、生活生存认知、信息视野拓展。
7. summary 用一句话说明这个组方便复习什么。

已有节点：
{json.dumps(compact, ensure_ascii=False)}
"""
    return parse_json_model(GraphOrganizationResult, [{"role": "user", "content": prompt}], setting=setting)


def diagnose(setting: dict[str, Any] | None = None) -> dict[str, str]:
    try:
        resolved = ensure_credentials(setting)
        try:
            output = sdk_chat_completion([{"role": "user", "content": "Reply with ok."}], setting=resolved)
            transport = "python-sdk"
        except APIConnectionError:
            output = curl_chat_completion([{"role": "user", "content": "Reply with ok."}], setting=resolved)
            transport = "curl"
        return {
            "ok": "true",
            "provider": resolved.get("provider", "compatible"),
            "name": resolved.get("name", ""),
            "model": resolved["model"],
            "base_url": resolved["base_url"],
            "chat_url": chat_url(resolved),
            "transport": transport,
            "output": output,
        }
    except Exception as exc:
        try:
            resolved = current_setting(setting)
        except Exception:
            resolved = {}
        return {
            "ok": "false",
            "provider": resolved.get("provider", "api"),
            "name": resolved.get("name", ""),
            "model": resolved.get("model", ""),
            "base_url": resolved.get("base_url", ""),
            "chat_url": chat_url(resolved) if resolved.get("base_url") else "",
            "error": explain_error(exc, resolved) if resolved else str(exc),
        }
