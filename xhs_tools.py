from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

import deepseek_client
import storage
import writer_tools
from schemas import XhsTopicSuggestionsResult


XHS_CLI = Path(r"C:\Users\Bo Yang\.codex\skills\xiaohongshu-autoclaw\scripts\cli.py")
XHS_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
XHS_IMAGE_TEXT_MODES = {
    "tutorial": "教程轮播",
    "listicle": "清单轮播",
    "pitfall": "避坑轮播",
    "comparison": "对比轮播",
    "case_study": "案例拆解",
    "single_opinion": "单图观点",
}
XHS_CAROUSEL_STRATEGY_DEFAULT_ID = "default-xhs-listicle"
XHS_CAROUSEL_STRATEGY_PRESETS = {
    "tutorial": {
        "name": "教程轮播策略",
        "description": "封面承诺 -> 步骤拆解 -> 结果/CTA",
        "slide_count": 6,
        "cover_type": "problem_promise",
        "layout_style": "balanced",
        "text_density": "medium",
        "visual_balance": "balanced",
        "slide_flow": ["封面：一个明确问题和可获得结果", "为什么现在要做：痛点和误区", "步骤1：最关键的起手动作", "步骤2-3：可执行细节和判断标准", "结果/检查清单：用户照做后的变化", "总结 CTA：收藏、评论问题或下一步行动"],
        "strategy_body": "适合教学、方法论、流程拆解。每张图只讲一个步骤，标题用动词开头，正文用短句和检查点。封面必须给出明确承诺，不要把教程写成理论文章。",
    },
    "listicle": {
        "name": "清单轮播策略",
        "description": "封面清单 -> 分项价值 -> 总结收藏",
        "slide_count": 6,
        "cover_type": "checklist",
        "layout_style": "text_first",
        "text_density": "high",
        "visual_balance": "text_heavy",
        "slide_flow": ["封面：数字清单和收藏理由", "清单总览：先给分类或判断标准", "要点1-2：每点一句价值和依据", "要点3-4：继续交付可保存信息", "对照表/总结：帮助用户快速复盘", "收藏 CTA：下次查阅或评论补充"],
        "strategy_body": "适合资料整理、工具/渠道/方法清单、避坑 checklist。要强调可收藏价值，避免堆长段落；每个分项都要有一句为什么值得记。",
    },
    "pitfall": {
        "name": "避坑轮播策略",
        "description": "痛点/误区 -> 风险解释 -> 正确做法",
        "slide_count": 5,
        "cover_type": "problem_promise",
        "layout_style": "text_first",
        "text_density": "medium",
        "visual_balance": "text_heavy",
        "slide_flow": ["封面：点名高频误区或风险", "误区1：为什么容易踩坑", "误区2：背后的真实原因", "正确做法：给出可执行替代方案", "总结 CTA：保存避坑清单"],
        "strategy_body": "适合纠偏、风险提示、常见错误。语气要像提醒朋友，不制造焦虑；所有风险判断必须回到材料依据，不能情绪化唱衰。",
    },
    "comparison": {
        "name": "对比轮播策略",
        "description": "对比对象 -> 维度拆解 -> 选择建议",
        "slide_count": 5,
        "cover_type": "before_after",
        "layout_style": "split",
        "text_density": "medium",
        "visual_balance": "balanced",
        "slide_flow": ["封面：明确对比对象和选择问题", "维度1：核心差异", "维度2：适用人群/场景", "维度3：成本、风险或收益", "结论：不同用户该怎么选"],
        "strategy_body": "适合方案选择、政策/产品/路径对比。每页固定同一对比维度，尽量用表格感或左右分栏；最后必须给条件化建议，不做绝对结论。",
    },
    "case_study": {
        "name": "案例拆解策略",
        "description": "案例背景 -> 关键动作 -> 可复用结论",
        "slide_count": 5,
        "cover_type": "hook_text",
        "layout_style": "balanced",
        "text_density": "medium",
        "visual_balance": "balanced",
        "slide_flow": ["封面：案例里最值得看的反差/结果", "背景：发生了什么和为什么重要", "关键动作：案例中的转折点", "拆解：背后的方法或机制", "可复用结论：用户能学走什么"],
        "strategy_body": "适合热点案例、公司/个人/政策动作拆解。先讲故事，再提炼方法；不要只复述新闻，要把可复用结论单独拎出来。",
    },
    "single_opinion": {
        "name": "单图观点策略",
        "description": "一个强观点 + 一个清晰理由",
        "slide_count": 1,
        "cover_type": "hook_text",
        "layout_style": "visual_first",
        "text_density": "low",
        "visual_balance": "visual_heavy",
        "slide_flow": ["单图：一个强观点、一个理由、一个行动提示"],
        "strategy_body": "适合一句话观点、轻量提醒、强钩子表达。只表达一个重点，画面干净，正文承担解释，不把长文塞进图里。",
    },
}


class XhsSlide(BaseModel):
    index: int
    role: str = ""
    title: str = ""
    body: str = ""
    visual_prompt: str = ""


class XhsDraftResult(BaseModel):
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    cover_prompt: str = ""
    content_image_prompts: list[str] = Field(default_factory=list)
    slide_plan: list[XhsSlide] = Field(default_factory=list)
    rationale: str = ""


class XhsRevisionResult(BaseModel):
    title: str = ""
    content: str
    tags: list[str] = Field(default_factory=list)
    cover_prompt: str = ""
    content_image_prompts: list[str] = Field(default_factory=list)
    slide_plan: list[XhsSlide] = Field(default_factory=list)
    change_summary: str = ""


class XhsImageSuggestionResult(BaseModel):
    cover_prompt: str = ""
    content_image_prompts: list[str] = Field(default_factory=list)
    rationale: str = ""


def xhs_dir() -> Path:
    root = storage.XHS_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def _legacy_writer_xhs_path(name: str) -> Path:
    return writer_tools.writer_dir() / name


def _migrate_legacy_tree(source: Path, target: Path) -> int:
    if not source.exists() or source.resolve() == target.resolve():
        return 0
    copied = 0
    source_files = [path for path in source.rglob("*") if path.is_file()]
    for source_path in source.rglob("*"):
        if not source_path.is_file():
            continue
        try:
            relative_path = source_path.relative_to(source)
        except ValueError:
            continue
        target_path = target / relative_path
        if target_path.exists():
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        copied += 1
    target_files = [path for path in target.rglob("*") if path.is_file()]
    if len(target_files) >= len(source_files):
        shutil.rmtree(source)
    return copied


def _replace_legacy_xhs_paths(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _replace_legacy_xhs_paths(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_legacy_xhs_paths(item) for item in value]
    if isinstance(value, str):
        return (
            value.replace("writer\\xhs_projects\\", "xhs\\projects\\")
            .replace("writer/xhs_projects/", "xhs/projects/")
            .replace("writer\\xhs_profiles\\", "xhs\\profiles\\")
            .replace("writer/xhs_profiles/", "xhs/profiles/")
        )
    return value


def repair_migrated_xhs_json_paths() -> int:
    repaired = 0
    for path in xhs_dir().rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        normalized = _replace_legacy_xhs_paths(payload)
        if normalized == payload:
            continue
        path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
        repaired += 1
    return repaired


def migrate_legacy_writer_xhs_data() -> int:
    root = xhs_dir()
    copied = 0
    copied += _migrate_legacy_tree(_legacy_writer_xhs_path("xhs_projects"), root / "projects")
    copied += _migrate_legacy_tree(_legacy_writer_xhs_path("xhs_profiles"), root / "profiles")
    legacy_strategy = _legacy_writer_xhs_path("xhs_carousel_strategies.json")
    target_strategy = root / "carousel_strategies.json"
    if legacy_strategy.exists():
        target_strategy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy_strategy, target_strategy)
        legacy_strategy.unlink()
        copied += 1
    repaired = repair_migrated_xhs_json_paths()
    copied += repaired
    return copied


def xhs_projects_dir() -> Path:
    migrate_legacy_writer_xhs_data()
    root = xhs_dir() / "projects"
    root.mkdir(parents=True, exist_ok=True)
    return root


def xhs_profiles_dir() -> Path:
    migrate_legacy_writer_xhs_data()
    root = xhs_dir() / "profiles"
    root.mkdir(parents=True, exist_ok=True)
    return root


def xhs_carousel_strategies_file() -> Path:
    migrate_legacy_writer_xhs_data()
    return xhs_dir() / "carousel_strategies.json"


def _relative(path: Path) -> str:
    return storage.storage_relative(path)


def _safe_slug(value: str, fallback: str = "xhs") -> str:
    return writer_tools.safe_slug(value, fallback=fallback)


def _project_path(project_id: str) -> Path:
    return xhs_projects_dir() / project_id / "project.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(fallback or {})
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return dict(fallback or {})


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        items = re.split(r"[\n,，、]+", value)
    else:
        items = []
    cleaned: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def _tag_strategy(value: Any) -> dict[str, list[str]]:
    source = value if isinstance(value, dict) else {}
    return {
        "broad_tags": _string_list(source.get("broad_tags")),
        "niche_tags": _string_list(source.get("niche_tags")),
        "trend_tags": _string_list(source.get("trend_tags")),
        "branded_tags": _string_list(source.get("branded_tags")),
    }


def _int_between(value: Any, default: int, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(low, min(high, number))


def default_image_text_config(topic: dict[str, Any] | None = None) -> dict[str, Any]:
    source = topic if isinstance(topic, dict) else {}
    note_format = str(source.get("note_format") or "")
    mode = "single_opinion" if "单图" in note_format else "listicle"
    if "教程" in note_format:
        mode = "tutorial"
    elif "避坑" in note_format:
        mode = "pitfall"
    elif "对比" in note_format:
        mode = "comparison"
    elif "案例" in note_format:
        mode = "case_study"
    preset = XHS_CAROUSEL_STRATEGY_PRESETS[mode]
    count = _int_between(source.get("carousel_count"), int(preset["slide_count"]), 1, 7)
    return {
        "mode": mode,
        "mode_label": XHS_IMAGE_TEXT_MODES[mode],
        "slide_count": count,
        "cover_type": preset["cover_type"],
        "layout_style": preset["layout_style"],
        "text_density": preset["text_density"],
        "visual_balance": preset["visual_balance"],
        "aspect_ratio": "3:4",
        "cover_hook": str(source.get("cover_hook") or source.get("title_hook") or "").strip(),
        "slide_flow": _string_list(source.get("slide_flow")) or list(preset["slide_flow"]),
        "notes": "",
        "strategy_body": preset["strategy_body"],
    }


def normalize_image_text_config(config: dict[str, Any] | None, topic: dict[str, Any] | None = None) -> dict[str, Any]:
    base = default_image_text_config(topic)
    source = config if isinstance(config, dict) else {}
    mode = str(source.get("mode") or base["mode"])
    if mode not in XHS_IMAGE_TEXT_MODES:
        mode = str(base["mode"])
    slide_count = _int_between(source.get("slide_count"), int(base["slide_count"]), 1, 7)
    if mode == "single_opinion":
        slide_count = 1
    return {
        "mode": mode,
        "mode_label": XHS_IMAGE_TEXT_MODES[mode],
        "slide_count": slide_count,
        "cover_type": str(source.get("cover_type") or base["cover_type"]),
        "layout_style": str(source.get("layout_style") or base["layout_style"]),
        "text_density": str(source.get("text_density") or base["text_density"]),
        "visual_balance": str(source.get("visual_balance") or base["visual_balance"]),
        "aspect_ratio": str(source.get("aspect_ratio") or base["aspect_ratio"]),
        "cover_hook": str(source.get("cover_hook") or base["cover_hook"]).strip(),
        "slide_flow": _string_list(source.get("slide_flow")) or list(base["slide_flow"]),
        "notes": str(source.get("notes") or "").strip(),
        "strategy_body": str(source.get("strategy_body") or base.get("strategy_body") or "").strip(),
        "strategy_id": str(source.get("strategy_id") or "").strip(),
        "strategy_name": str(source.get("strategy_name") or "").strip(),
    }


def _default_carousel_strategies() -> list[dict[str, Any]]:
    presets = []
    for mode, preset in XHS_CAROUSEL_STRATEGY_PRESETS.items():
        label = XHS_IMAGE_TEXT_MODES[mode]
        config = default_image_text_config({"note_format": label, "carousel_count": preset["slide_count"]})
        config["mode"] = mode
        config["mode_label"] = label
        presets.append(
            {
                "id": XHS_CAROUSEL_STRATEGY_DEFAULT_ID if mode == "listicle" else f"default-xhs-{mode}",
                "name": str(preset["name"]),
                "description": str(preset["description"]),
                "config": config,
                "readonly": True,
                "created_at": "builtin",
                "updated_at": "builtin",
            }
        )
    return presets


def _normalize_carousel_strategy(item: dict[str, Any]) -> dict[str, Any]:
    strategy_id = str(item.get("id") or "").strip() or uuid4().hex
    config = normalize_image_text_config(item.get("config") if isinstance(item.get("config"), dict) else {})
    return {
        "id": strategy_id,
        "name": str(item.get("name") or "").strip() or "未命名轮播策略",
        "description": str(item.get("description") or "").strip(),
        "config": config,
        "readonly": bool(item.get("readonly")) or strategy_id.startswith("default-xhs-"),
        "created_at": str(item.get("created_at") or datetime.now().isoformat(timespec="seconds")),
        "updated_at": str(item.get("updated_at") or datetime.now().isoformat(timespec="seconds")),
    }


def _read_custom_carousel_strategies() -> list[dict[str, Any]]:
    path = xhs_carousel_strategies_file()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    items = payload.get("items") if isinstance(payload, dict) else []
    normalized = []
    for raw in items if isinstance(items, list) else []:
        if isinstance(raw, dict):
            item = _normalize_carousel_strategy(raw)
            if item["id"].startswith("default-xhs-"):
                continue
            item["readonly"] = False
            normalized.append(item)
    return normalized


def _write_custom_carousel_strategies(items: list[dict[str, Any]]) -> None:
    xhs_carousel_strategies_file().write_text(json.dumps({"items": items}, ensure_ascii=False, indent=2), encoding="utf-8")


def list_carousel_strategies() -> dict[str, Any]:
    custom = sorted(_read_custom_carousel_strategies(), key=lambda item: item.get("updated_at", ""), reverse=True)
    return {"default_id": XHS_CAROUSEL_STRATEGY_DEFAULT_ID, "items": [*_default_carousel_strategies(), *custom]}


def save_carousel_strategy(name: str, config: dict[str, Any], strategy_id: str | None = None, description: str = "") -> dict[str, Any]:
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("轮播策略名称不能为空")
    clean_id = (strategy_id or "").strip()
    if clean_id.startswith("default-xhs-"):
        raise ValueError("默认轮播策略不能覆盖")
    now = datetime.now().isoformat(timespec="seconds")
    items = _read_custom_carousel_strategies()
    target_id = clean_id or uuid4().hex
    saved: dict[str, Any] | None = None
    for item in items:
        if item["id"] == target_id:
            item.update({"name": clean_name, "description": description.strip(), "config": normalize_image_text_config(config), "updated_at": now, "readonly": False})
            saved = item
            break
    if saved is None:
        saved = {
            "id": target_id,
            "name": clean_name,
            "description": description.strip(),
            "config": normalize_image_text_config(config),
            "readonly": False,
            "created_at": now,
            "updated_at": now,
        }
        items.append(saved)
    _write_custom_carousel_strategies(items)
    return saved


def delete_carousel_strategy(strategy_id: str) -> None:
    clean_id = strategy_id.strip()
    if clean_id.startswith("default-xhs-"):
        raise ValueError("默认轮播策略不能删除")
    items = _read_custom_carousel_strategies()
    next_items = [item for item in items if item["id"] != clean_id]
    if len(next_items) == len(items):
        raise FileNotFoundError(f"轮播策略不存在：{strategy_id}")
    _write_custom_carousel_strategies(next_items)


def _profile_path(profile_id: str) -> Path:
    return xhs_profiles_dir() / profile_id / "profile.json"


def _validate_account_profile(payload: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    base = dict(existing or {})
    base.update(payload or {})
    profile = {
        "name": str(base.get("name") or "").strip(),
        "account_name": str(base.get("account_name") or "").strip(),
        "positioning": str(base.get("positioning") or "").strip(),
        "target_audience": str(base.get("target_audience") or "").strip(),
        "audience_pain_points": _string_list(base.get("audience_pain_points")),
        "content_pillars": _string_list(base.get("content_pillars")),
        "tone": str(base.get("tone") or "").strip(),
        "value_promise": str(base.get("value_promise") or "").strip(),
        "content_formats": _string_list(base.get("content_formats")),
        "tag_strategy": _tag_strategy(base.get("tag_strategy")),
        "avoid_topics": _string_list(base.get("avoid_topics")),
        "notes": str(base.get("notes") or "").strip(),
    }
    missing = []
    for key in ("name", "positioning", "target_audience"):
        if not profile[key]:
            missing.append(key)
    if not profile["content_pillars"]:
        missing.append("content_pillars")
    if missing:
        raise ValueError("账号定位缺少必填项：" + "、".join(missing))
    return profile


def _profile_visible(profile: dict[str, Any], owner_user_id: str | None, include_ownerless: bool = True) -> bool:
    owner = str(profile.get("owner_user_id") or "")
    if owner_user_id:
        return owner == owner_user_id or (include_ownerless and not owner)
    return True


def _write_account_profile(profile: dict[str, Any]) -> dict[str, Any]:
    profile["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _write_json(_profile_path(str(profile["id"])), profile)
    return profile


def create_account_profile(payload: dict[str, Any], owner_user_id: str | None = None, workspace_id: str | None = None) -> dict[str, Any]:
    now = datetime.now().isoformat(timespec="seconds")
    profile = _validate_account_profile(payload)
    profile_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{_safe_slug(profile['name'], 'profile')}-{uuid4().hex[:6]}"
    profile.update(
        {
            "id": profile_id,
            "created_at": now,
            "updated_at": now,
            "owner_user_id": owner_user_id or "",
            "workspace_id": workspace_id or "",
        }
    )
    return _write_account_profile(profile)


def list_account_profiles(owner_user_id: str | None = None, include_ownerless: bool = True) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for profile_file in xhs_profiles_dir().glob("*/profile.json"):
        profile = _read_json(profile_file)
        if profile and _profile_visible(profile, owner_user_id, include_ownerless=include_ownerless):
            profiles.append(profile)
    return sorted(profiles, key=lambda item: str(item.get("updated_at") or ""), reverse=True)


def load_account_profile(profile_id: str, owner_user_id: str | None = None, include_ownerless: bool = True) -> dict[str, Any]:
    profile = _read_json(_profile_path(profile_id))
    if not profile or not _profile_visible(profile, owner_user_id, include_ownerless=include_ownerless):
        raise FileNotFoundError(f"账号定位不存在：{profile_id}")
    return profile


def update_account_profile(profile_id: str, payload: dict[str, Any], owner_user_id: str | None = None, include_ownerless: bool = True) -> dict[str, Any]:
    current = load_account_profile(profile_id, owner_user_id=owner_user_id, include_ownerless=include_ownerless)
    profile = _validate_account_profile(payload, existing=current)
    profile.update(
        {
            "id": current["id"],
            "created_at": current.get("created_at") or datetime.now().isoformat(timespec="seconds"),
            "owner_user_id": current.get("owner_user_id") or "",
            "workspace_id": current.get("workspace_id") or "",
        }
    )
    return _write_account_profile(profile)


def delete_account_profile(profile_id: str, owner_user_id: str | None = None, include_ownerless: bool = True) -> dict[str, Any]:
    profile = load_account_profile(profile_id, owner_user_id=owner_user_id, include_ownerless=include_ownerless)
    path = _profile_path(profile_id)
    if path.exists():
        path.unlink()
    return {"ok": True, "profile": profile}


def account_profile_prompt(profile: dict[str, Any] | None) -> str:
    if not isinstance(profile, dict) or not profile.get("id"):
        raise ValueError("请先为小红书项目选择账号定位")
    return json.dumps(
        {
            "定位名称": profile.get("name") or "",
            "账号名": profile.get("account_name") or "",
            "一句话定位": profile.get("positioning") or "",
            "目标人群": profile.get("target_audience") or "",
            "用户痛点": profile.get("audience_pain_points") or [],
            "内容支柱": profile.get("content_pillars") or [],
            "语气人设": profile.get("tone") or "",
            "核心价值承诺": profile.get("value_promise") or "",
            "常用内容形式": profile.get("content_formats") or [],
            "标签策略": profile.get("tag_strategy") or {},
            "避让边界": profile.get("avoid_topics") or [],
            "补充说明": profile.get("notes") or "",
        },
        ensure_ascii=False,
        indent=2,
    )


def _write_project(project: dict[str, Any]) -> dict[str, Any]:
    project["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _write_json(resolve_project_workspace(str(project["id"])) / "project.json", project)
    return project


def create_project(
    name: str,
    description: str = "",
    account_profile_id: str = "",
    owner_user_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    if not account_profile_id:
        raise ValueError("请先选择或新建账号定位")
    account_profile = load_account_profile(
        account_profile_id,
        owner_user_id=owner_user_id,
        include_ownerless=owner_user_id is None,
    )
    title = (name or "").strip() or "未命名小红书图文"
    project_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{_safe_slug(title, 'xhs')}-{uuid4().hex[:6]}"
    workspace = xhs_projects_dir() / project_id
    workspace.mkdir(parents=True, exist_ok=True)
    now = datetime.now().isoformat(timespec="seconds")
    project = {
        "id": project_id,
        "name": title,
        "type": "image_text",
        "description": description.strip(),
        "status": "active",
        "workspace": _relative(workspace),
        "created_at": now,
        "updated_at": now,
        "owner_user_id": owner_user_id or "",
        "workspace_id": workspace_id or "",
        "account_profile_id": account_profile_id,
        "account_profile": account_profile,
        "library_files": [],
        "topics": [],
        "topic": None,
        "image_text_config": {},
        "title": "",
        "content": "",
        "tags": [],
        "cover_prompt": "",
        "content_image_prompts": [],
        "image_suggestion_rationale": "",
        "draft_confirmed": False,
        "image_suggestions_confirmed": False,
        "slide_plan": [],
        "images": {},
        "preflight": {},
        "publish_result": {},
    }
    _write_project(project)
    return project


def list_projects(owner_user_id: str | None = None, include_ownerless: bool = True) -> list[dict[str, Any]]:
    projects: list[dict[str, Any]] = []
    for project_file in xhs_projects_dir().glob("*/project.json"):
        project = _read_json(project_file)
        owner = str(project.get("owner_user_id") or "")
        if owner_user_id and owner != owner_user_id and not (include_ownerless and not owner):
            continue
        if project:
            projects.append(project)
    return sorted(projects, key=lambda item: str(item.get("updated_at") or ""), reverse=True)


def load_project(project_id: str, owner_user_id: str | None = None, include_ownerless: bool = True) -> dict[str, Any]:
    path = _project_path(project_id)
    if not path.exists():
        raise FileNotFoundError(f"小红书项目不存在：{project_id}")
    project = _read_json(path)
    owner = str(project.get("owner_user_id") or "")
    if owner_user_id and owner != owner_user_id and not (include_ownerless and not owner):
        raise FileNotFoundError(f"小红书项目不存在：{project_id}")
    return hydrate_project(project)


def update_project(project_id: str, **updates: Any) -> dict[str, Any]:
    project = load_project(project_id)
    project.update(updates)
    return _write_project(project)


def resolve_project_workspace(project_id: str) -> Path:
    return (xhs_projects_dir() / project_id).resolve()


def resolve_xhs_file(path: str) -> Path:
    resolved = storage.resolve_root_path(path)
    if not resolved:
        raise ValueError("缺少文件路径")
    resolved = resolved.resolve()
    root = xhs_projects_dir().resolve()
    if root not in resolved.parents and resolved != root:
        raise ValueError("只能预览小红书项目目录下的文件")
    if not resolved.exists() or not resolved.is_file():
        raise FileNotFoundError(f"文件不存在：{path}")
    return resolved


def set_project_library_files(project_id: str, files: list[dict[str, Any]]) -> dict[str, Any]:
    workspace = resolve_project_workspace(project_id)
    clear_image_metadata(workspace)
    return update_project(
        project_id,
        library_files=files,
        topics=[],
        topic=None,
        image_text_config={},
        title="",
        content="",
        tags=[],
        cover_prompt="",
        content_image_prompts=[],
        image_suggestion_rationale="",
        slide_plan=[],
        images={},
        preflight={},
        publish_result={},
        status="active",
    )


def _library_materials(project: dict[str, Any]) -> list[tuple[str, str]]:
    materials: list[tuple[str, str]] = []
    for item in project.get("library_files") or []:
        if not isinstance(item, dict):
            continue
        markdown_path = str(item.get("markdown_path") or "").strip()
        path = storage.resolve_root_path(markdown_path)
        if not path or not path.exists():
            continue
        title = str(item.get("title") or path.stem)
        materials.append((title, path.read_text(encoding="utf-8")))
    if not materials:
        raise FileNotFoundError("项目还没有可读取的知识文件")
    return materials


def generate_topics(project_id: str, setting: dict[str, Any] | None = None) -> dict[str, Any]:
    project = load_project(project_id)
    profile_text = account_profile_prompt(project.get("account_profile"))
    materials = _library_materials(project)
    prompt = f"""
你是小红书图文/轮播账号的内容策划助手，不是微信公众号文章选题助手。请只基于账号定位和用户选中的本地知识文件，生成适合小红书发布的图文笔记选题 brief。

账号定位：
{profile_text}

输出要求：
1. 每个建议都必须是小红书图文/轮播笔记选题，不要输出公众号文章式的长文主题、摘要或论点。
2. 每个建议必须包含：content_pillar、user_pain_point、title_hook、topic_angle、note_format、carousel_count、cover_hook、slide_flow、value_points、material_basis、reference_files、tag_keywords、cta、risk_boundary。
3. content_pillar 要从账号的内容支柱中选择或贴近其中一个；user_pain_point 要对应目标人群的真实痛点。
4. title_hook 必须是小红书标题方向，优先使用数字承诺、好奇缺口、问题解决、前后变化等框架，控制在 20 个中文字符左右，不做标题党。
5. note_format 只能是小红书图文形式，例如：教程轮播、清单轮播、避坑轮播、对比轮播、案例拆解、单图观点；不要生成视频、直播或公众号长文。
6. carousel_count 根据内容形式给 1 到 7 张；教程、清单、避坑、对比、案例类优先 3 到 7 张。
7. cover_hook 是第一张图的封面短钩子，必须短、强、适合移动端大字展示。
8. slide_flow 用 3 到 7 个短句描述轮播结构：第 1 张封面/痛点/承诺，中间交付核心价值，最后总结或 CTA。
9. value_points 要写清这条笔记能给用户带来的可收藏价值，而不是文章摘要。
10. material_basis 和 reference_files 必须能回到本地材料；不要编造材料之外的事实。
11. tag_keywords 给 5 到 8 个标签关键词方向，组合大类、细分、场景或自有标签。
12. risk_boundary 写清哪些表达不能做，例如无来源预测、夸大结论、情绪化判断等。

本地知识文件：
{_joined_materials(materials)}
"""
    result = deepseek_client.parse_json_model(XhsTopicSuggestionsResult, [{"role": "user", "content": prompt}], setting=setting)
    suggestions = result.model_dump().get("suggestions", [])
    update_project(
        project_id,
        topics=suggestions,
        topic=None,
        image_text_config={},
        title="",
        content="",
        tags=[],
        cover_prompt="",
        content_image_prompts=[],
        image_suggestion_rationale="",
        slide_plan=[],
        images={},
        preflight={},
        publish_result={},
        status="active",
    )
    return {"suggestions": suggestions}


def select_topic(project_id: str, topic: dict[str, Any]) -> dict[str, Any]:
    if not topic:
        raise ValueError("请选择一个选题")
    return update_project(
        project_id,
        topic=topic,
        image_text_config={},
        title="",
        content="",
        tags=[],
        cover_prompt="",
        content_image_prompts=[],
        image_suggestion_rationale="",
        slide_plan=[],
        images={},
        preflight={},
        publish_result={},
        status="active",
    )


def configure_image_text(project_id: str, config: dict[str, Any]) -> dict[str, Any]:
    project = load_project(project_id)
    topic = project.get("topic")
    if not isinstance(topic, dict) or not topic:
        raise ValueError("请先选择一个选题")
    normalized = normalize_image_text_config(config, topic)
    return update_project(
        project_id,
        image_text_config=normalized,
        title="",
        content="",
        tags=[],
        cover_prompt="",
        content_image_prompts=[],
        image_suggestion_rationale="",
        slide_plan=[],
        images={},
        preflight={},
        publish_result={},
        status="active",
    )


def _topic_title(topic: dict[str, Any]) -> str:
    for key in ("title_hook", "title", "name", "topic", "headline"):
        value = topic.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "小红书图文选题"


def _joined_materials(materials: list[tuple[str, str]], limit: int = 9000) -> str:
    chunks = []
    for filename, content in materials:
        chunks.append(f"【本地知识文件：{filename}】\n{content[:limit]}")
    return "\n\n---\n\n".join(chunks)


def _clean_tags(tags: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    for tag in tags or []:
        value = re.sub(r"^[#＃]+", "", str(tag or "")).strip()
        if value and value not in cleaned:
            cleaned.append(value[:24])
    return cleaned[:8]


def generate_draft(
    project_id: str,
    topic: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    setting: dict[str, Any] | None = None,
) -> XhsDraftResult:
    project = load_project(project_id)
    selected_topic = topic or project.get("topic")
    if not isinstance(selected_topic, dict) or not selected_topic:
        raise ValueError("请先选择一个选题")
    image_text_config = normalize_image_text_config(config or project.get("image_text_config"), selected_topic)
    if config or not project.get("image_text_config"):
        update_project(project_id, image_text_config=image_text_config)
    topic_json = json.dumps(selected_topic, ensure_ascii=False)
    config_json = json.dumps(image_text_config, ensure_ascii=False)
    profile_text = account_profile_prompt(project.get("account_profile"))
    prompt = f"""
你是小红书图文内容策划和写作助手。请基于用户选择的本地知识文件与选题，生成一篇可进入发布前审校的小红书图文笔记。

硬性要求：
1. 只做小红书图文，不做视频和长文。
2. 标题不超过 20 个小红书长度单位，具体、有点击欲，但不能夸大素材没有支撑的结论。
3. 正文使用自然中文，段落短，适合手机阅读；包含开头钩子、核心内容、个人化/观点化表达、明确 CTA。
4. 标签使用 5 到 8 个，混合大类、垂类、场景和自有标签，不要堆无关热词。
5. 严格遵循图文配置里的 mode、slide_count、cover_type、layout_style、text_density、visual_balance 和 aspect_ratio。
6. 生成 1 张封面图提示词和与 slide_count 匹配的正文轮播图提示词；如果 slide_count=1，只生成封面/单图提示词。提示词要包含“简体中文、少量文字、准确可读”。
7. slide_plan 必须描述每张图的作用、标题、正文要点和视觉提示；第 1 张是封面，后续是正文轮播图。
8. 教程/清单/避坑/对比/案例类按“封面/痛点/承诺 -> 中间核心交付 -> 总结或 CTA”组织；单图观点必须一张图讲清楚，不硬拆轮播。
9. 输出必须能直接保存为本地项目产物，不要使用 Markdown 链接，不要编造素材之外的硬事实。

选题：
{topic_json}

图文配置：
{config_json}

本地知识文件：
{_joined_materials(_library_materials(project))}
"""
    prompt = f"账号定位：\n{profile_text}\n\n账号定位约束：标题、正文、封面、轮播图、标签都必须符合账号定位、目标人群、内容支柱、语气人设、价值承诺、标签策略和避让边界。\n\n{prompt}"
    result = deepseek_client.parse_json_model(XhsDraftResult, [{"role": "user", "content": prompt}], setting=setting)
    result.tags = _clean_tags(result.tags)
    result.content_image_prompts = result.content_image_prompts[:4]
    save_draft_artifacts(project_id, result)
    return result


def revise_draft(
    project_id: str,
    instruction: str,
    content: str | None = None,
    setting: dict[str, Any] | None = None,
) -> XhsRevisionResult:
    project = load_project(project_id)
    current_content = content if content is not None else str(project.get("content") or "")
    if not instruction.strip():
        raise ValueError("请输入修订要求")
    if not current_content.strip():
        raise ValueError("请先生成或填写小红书正文")
    profile_text = account_profile_prompt(project.get("account_profile"))
    prompt = f"""
你是小红书图文笔记编辑。请按照用户修订要求，直接输出完整修订后的标题、正文、标签、封面提示词、轮播图提示词和 slide_plan。

约束：
1. 继续保持小红书图文语气，标题不超过 20 个小红书长度单位。
2. 不引入没有素材依据的新事实。
3. tags 维持 5 到 8 个；slide_plan 第 1 张为封面。

用户修订要求：
{instruction}

当前标题：
{project.get("title") or project.get("name") or ""}

当前正文：
{current_content}

当前标签：
{json.dumps(project.get("tags") or [], ensure_ascii=False)}
"""
    prompt = f"账号定位：\n{profile_text}\n\n修订约束：修订后的标题、正文、封面、轮播图、标签都必须继续符合账号定位、目标人群、内容支柱、语气人设、价值承诺、标签策略和避让边界。\n\n{prompt}"
    result = deepseek_client.parse_json_model(XhsRevisionResult, [{"role": "user", "content": prompt}], setting=setting)
    result.tags = _clean_tags(result.tags)
    result.content_image_prompts = result.content_image_prompts[:4]
    draft = XhsDraftResult(
        title=result.title or str(project.get("title") or project.get("name") or ""),
        content=result.content,
        tags=result.tags,
        cover_prompt=result.cover_prompt or str(project.get("cover_prompt") or ""),
        content_image_prompts=result.content_image_prompts or list(project.get("content_image_prompts") or []),
        slide_plan=result.slide_plan,
        rationale=result.change_summary,
    )
    save_draft_artifacts(project_id, draft)
    return result


def save_draft_artifacts(project_id: str, result: XhsDraftResult) -> dict[str, Any]:
    workspace = resolve_project_workspace(project_id)
    title = shorten_title(result.title)
    tags = _clean_tags(result.tags)
    content = normalize_content_with_tags(result.content, tags)
    (workspace / "note.md").write_text(content, encoding="utf-8")
    (workspace / "title.txt").write_text(title, encoding="utf-8")
    (workspace / "content.txt").write_text(content, encoding="utf-8")
    _write_json(workspace / "tags.json", {"items": tags})
    _write_json(workspace / "slide_plan.json", {"items": [item.model_dump() for item in result.slide_plan]})
    return update_project(
        project_id,
        name=title or load_project(project_id).get("name"),
        title=title,
        content=content,
        tags=tags,
        cover_prompt=result.cover_prompt,
        content_image_prompts=result.content_image_prompts[:4],
        image_suggestion_rationale="",
        draft_confirmed=False,
        image_suggestions_confirmed=False,
        slide_plan=[item.model_dump() for item in result.slide_plan],
        images={},
        preflight={},
        publish_result={},
        status="active",
    )


def suggest_images(project_id: str, setting: dict[str, Any] | None = None) -> XhsImageSuggestionResult:
    project = load_project(project_id)
    if not str(project.get("content") or "").strip():
        raise ValueError("请先生成小红书图文草稿")
    if not project.get("draft_confirmed"):
        raise ValueError("请先确认图文草稿，再生成配图建议")
    topic = project.get("topic") if isinstance(project.get("topic"), dict) else None
    image_text_config = normalize_image_text_config(project.get("image_text_config"), topic)
    slide_count = _int_between(image_text_config.get("slide_count"), 5, 1, 7)
    prompt = f"""
你是小红书图文配图策划助手。请根据已确认的图文配置、正文内容和 slide_plan，生成封面图与轮播图的配图提示词建议。

硬性要求：
1. 这里只生成配图建议提示词，不生成正文，不改变选题。
2. cover_prompt 对应第 1 张图，必须包含封面钩子、主体、构图、移动端大字可读要求。
3. content_image_prompts 必须与图文配置 slide_count 匹配；如果 slide_count=1，则 content_image_prompts 为空。
4. 每张图只表达一个重点，文字少、层级清楚、适合 3:4 小红书竖图。
5. 提示词必须包含“简体中文、少量文字、准确可读、不要乱码”。
6. 根据策略正文安排封面、主体图、总结/CTA 图，不要把正文长段落直接贴到图片上。
7. rationale 说明为什么这样安排配图。

图文配置：
{json.dumps(image_text_config, ensure_ascii=False)}

选题：
{json.dumps(project.get("topic") or {}, ensure_ascii=False)}

slide_plan：
{json.dumps(project.get("slide_plan") or [], ensure_ascii=False)}

标题：
{project.get("title") or ""}

正文：
{project.get("content") or ""}
"""
    result = deepseek_client.parse_json_model(XhsImageSuggestionResult, [{"role": "user", "content": prompt}], setting=setting)
    result.content_image_prompts = (result.content_image_prompts or [])[: max(0, slide_count - 1)]
    clear_image_metadata(resolve_project_workspace(project_id))
    update_project(
        project_id,
        cover_prompt=result.cover_prompt,
        content_image_prompts=result.content_image_prompts,
        image_suggestion_rationale=result.rationale,
        image_suggestions_confirmed=False,
        images={},
        preflight={},
        publish_result={},
        status="active",
    )
    return result


def confirm_draft(project_id: str) -> dict[str, Any]:
    project = load_project(project_id)
    if not str(project.get("content") or "").strip():
        raise ValueError("请先生成或填写小红书图文草稿")
    clear_image_metadata(resolve_project_workspace(project_id))
    return update_project(
        project_id,
        draft_confirmed=True,
        image_suggestions_confirmed=False,
        images={},
        preflight={},
        publish_result={},
        status="active",
    )


def confirm_image_suggestions(project_id: str) -> dict[str, Any]:
    project = load_project(project_id)
    cover_prompt = str(project.get("cover_prompt") or "").strip()
    content_prompts = [str(item).strip() for item in project.get("content_image_prompts") or [] if str(item).strip()]
    rationale = str(project.get("image_suggestion_rationale") or "").strip()
    if not cover_prompt and not content_prompts and not rationale:
        raise ValueError("请先生成配图建议，再确认")
    return update_project(
        project_id,
        image_suggestions_confirmed=True,
        images={},
        preflight={},
        publish_result={},
        status="active",
    )


def normalize_content_with_tags(content: str, tags: list[str]) -> str:
    text = re.sub(r"(?:^|\n)\s*(?:[#＃][^\n#＃\s]+(?:\s+|$))+$", "", content or "").strip()
    if tags:
        text = f"{text}\n\n" + " ".join(f"#{tag}" for tag in tags)
    return text.strip() + "\n"


def xhs_title_units(value: str) -> float:
    total = 0.0
    for char in value or "":
        total += 0.5 if ord(char) < 128 else 1.0
    return total


def shorten_title(value: str, max_units: float = 20) -> str:
    text = re.sub(r"\s+", " ", (value or "").strip())
    if xhs_title_units(text) <= max_units:
        return text
    result = []
    total = 0.0
    for char in text:
        weight = 0.5 if ord(char) < 128 else 1.0
        if total + weight > max_units:
            break
        result.append(char)
        total += weight
    return "".join(result).rstrip("，,。.!！?？、:：- ")


def _image_metadata_path(workspace: Path) -> Path:
    return workspace / "image_metadata.json"


def clear_image_metadata(workspace: Path) -> None:
    path = _image_metadata_path(workspace)
    if path.exists():
        path.unlink()


def load_image_metadata(workspace: Path) -> dict[str, Any]:
    return writer_tools.load_writer_image_metadata(workspace)


def images_need_retry(project: dict[str, Any]) -> bool:
    images = project.get("images")
    if not isinstance(images, dict):
        return False
    errors = images.get("errors") if isinstance(images.get("errors"), list) else []
    if not errors:
        return False
    cover_prompt = str(project.get("cover_prompt") or "").strip()
    cover_missing = cover_prompt and not (isinstance(images.get("cover"), dict) and images["cover"].get("path"))
    if cover_missing:
        return True
    expected_content_count = len([str(item).strip() for item in project.get("content_image_prompts") or [] if str(item).strip()])
    content_images = images.get("content_images") if isinstance(images.get("content_images"), list) else []
    existing_indexes = {
        int(item.get("index") or 0)
        for item in content_images
        if isinstance(item, dict) and item.get("path")
    }
    content_missing = any(index not in existing_indexes for index in range(1, expected_content_count + 1))
    if content_missing:
        return True
    return any(
        isinstance(error, dict)
        and (
            (error.get("kind") == "cover" and cover_missing)
            or (error.get("kind") == "content" and int(error.get("index") or 0) not in existing_indexes)
        )
        for error in errors
    )


def _has_generated_image(metadata: dict[str, Any], kind: str, index: int | None = None) -> bool:
    if kind == "cover":
        return isinstance(metadata.get("cover"), dict) and bool(metadata["cover"].get("path"))
    if kind == "content":
        return any(
            isinstance(item, dict) and int(item.get("index") or 0) == int(index or 0) and item.get("path")
            for item in metadata.get("content_images") or []
        )
    return False


def _prune_resolved_image_errors(workspace: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    errors = metadata.get("errors") if isinstance(metadata.get("errors"), list) else []
    remaining = [
        error
        for error in errors
        if not (
            isinstance(error, dict)
            and _has_generated_image(metadata, str(error.get("kind") or ""), int(error.get("index") or 0) or None)
        )
    ]
    if len(remaining) == len(errors):
        return metadata
    metadata["errors"] = remaining
    return writer_tools._write_writer_image_metadata(workspace, metadata)


def generate_image_item(
    project_id: str,
    kind: str,
    prompt: str,
    index: int | None = None,
    aspect_ratio: str | None = None,
) -> dict[str, Any]:
    workspace = resolve_project_workspace(project_id)
    metadata = writer_tools.generate_writer_image_item(
        workspace,
        kind,
        prompt,
        index=index,
        aspect_ratio=aspect_ratio or "3:4",
    )
    metadata = _prune_resolved_image_errors(workspace, metadata)
    update_project(project_id, images=metadata, preflight={}, publish_result={}, status="active")
    return metadata


def generate_images(
    project_id: str,
    cover_prompt: str | None = None,
    content_image_prompts: list[str] | None = None,
    cover_aspect_ratio: str | None = "3:4",
    content_aspect_ratio: str | None = "3:4",
) -> dict[str, Any]:
    workspace = resolve_project_workspace(project_id)
    project = load_project(project_id)
    if not project.get("image_suggestions_confirmed"):
        raise ValueError("请先确认配图建议，再生成图片")
    resolved_cover_prompt = str(cover_prompt or project.get("cover_prompt") or "").strip()
    resolved_content_prompts = [
        str(item).strip()
        for item in (content_image_prompts or project.get("content_image_prompts") or [])
        if str(item).strip()
    ]
    if not resolved_cover_prompt and not resolved_content_prompts:
        raise ValueError("请先生成或填写小红书配图提示词")
    metadata = writer_tools.generate_writer_images(
        workspace,
        cover_prompt=resolved_cover_prompt or None,
        content_prompts=resolved_content_prompts,
        cover_aspect_ratio=cover_aspect_ratio or "3:4",
        content_aspect_ratio=content_aspect_ratio or "3:4",
    )
    metadata = _prune_resolved_image_errors(workspace, metadata)
    update_project(project_id, images=metadata, preflight={}, publish_result={}, status="active")
    return metadata


def ordered_image_paths(project: dict[str, Any]) -> list[Path]:
    workspace = resolve_project_workspace(str(project["id"]))
    metadata = load_image_metadata(workspace)
    paths: list[Path] = []
    cover = metadata.get("cover") or {}
    if cover.get("path"):
        cover_path = storage.resolve_root_path(cover["path"])
        if cover_path and cover_path.exists():
            paths.append(cover_path.resolve())
    for item in sorted(metadata.get("content_images") or [], key=lambda row: int(row.get("index") or 0)):
        image_path = storage.resolve_root_path(item.get("path"))
        if image_path and image_path.exists():
            paths.append(image_path.resolve())
    return paths


def publish_content_preflight(project_id: str) -> dict[str, Any]:
    project = load_project(project_id)
    workspace = resolve_project_workspace(project_id)
    title = shorten_title(str(project.get("title") or project.get("name") or ""))
    content = str(project.get("content") or "").strip()
    images = ordered_image_paths(project)
    checks = [
        {"key": "title", "label": "标题", "ok": bool(title) and xhs_title_units(title) <= 20, "detail": f"{xhs_title_units(title):.1f}/20"},
        {"key": "content", "label": "正文", "ok": bool(content), "detail": f"{len(content)} 字"},
        {"key": "images", "label": "图片", "ok": bool(images), "detail": f"{len(images)} 张"},
    ]
    for image in images:
        checks.append(
            {
                "key": f"image:{image.name}",
                "label": image.name,
                "ok": image.exists() and image.suffix.lower() in XHS_IMAGE_EXTENSIONS,
                "detail": str(image),
            }
        )
    result = {
        "ok": all(item["ok"] for item in checks),
        "checks": checks,
        "blocking": [item for item in checks if not item["ok"]],
        "title": title,
        "content_path": _relative(workspace / "content.txt"),
        "title_path": _relative(workspace / "title.txt"),
        "image_paths": [str(path) for path in images],
        "tags": list(project.get("tags") or []),
        "login": {"skipped": True, "ok": True, "message": "导出包不需要检查本机小红书登录"},
        "mode": "export",
    }
    _write_json(workspace / "publish_preflight.json", result)
    update_project(project_id, title=title, preflight=result)
    return result


def hydrate_project(project: dict[str, Any]) -> dict[str, Any]:
    workspace = storage.resolve_root_path(project.get("workspace")) or resolve_project_workspace(str(project["id"]))
    if (workspace / "note.md").exists():
        project["content"] = (workspace / "note.md").read_text(encoding="utf-8")
    tags = _read_json(workspace / "tags.json", {"items": project.get("tags") or []})
    project["tags"] = tags.get("items") if isinstance(tags.get("items"), list) else project.get("tags") or []
    slide_plan = _read_json(workspace / "slide_plan.json", {"items": project.get("slide_plan") or []})
    project["slide_plan"] = slide_plan.get("items") if isinstance(slide_plan.get("items"), list) else []
    if (workspace / "image_metadata.json").exists():
        project["images"] = load_image_metadata(workspace)
    for key, filename in (("preflight", "publish_preflight.json"), ("publish_result", "publish_result.json")):
        path = workspace / filename
        if path.exists():
            project[key] = _read_json(path)
    export_path = workspace / "export_package.json"
    if export_path.exists():
        project["export_package"] = _read_json(export_path)
    return project


def project_step(project: dict[str, Any]) -> str:
    if str(project.get("status") or "") == "published":
        return "published"
    if project.get("publish_result", {}).get("filled"):
        return "publish_ready"
    if project.get("preflight"):
        return "publish_check"
    if ordered_image_paths(project):
        return "images"
    if str(project.get("content") or "").strip() and project.get("draft_confirmed"):
        return "images"
    if str(project.get("content") or "").strip():
        return "draft"
    if project.get("topic"):
        if project.get("image_text_config"):
            return "topic_configured"
        return "topic"
    if project.get("topics"):
        return "topics"
    if project.get("library_files"):
        return "knowledge_confirmed"
    return "created"


def next_action(project: dict[str, Any], step: str | None = None) -> str:
    current = step or project_step(project)
    if current == "draft":
        return "confirm_draft"
    if current == "images":
        if project.get("image_suggestions_confirmed") and images_need_retry(project):
            return "retry_failed_images"
        if ordered_image_paths(project):
            return "run_preflight"
        if not str(project.get("image_suggestion_rationale") or "").strip():
            return "suggest_images"
        if not project.get("image_suggestions_confirmed"):
            return "confirm_image_suggestions"
        return "generate_images"
    if current == "publish_check":
        return "fill_publish" if project.get("preflight", {}).get("ok") else "run_preflight"
    return {
        "created": "confirm_knowledge",
        "knowledge_confirmed": "generate_topics",
        "topics": "select_topic",
        "topic": "configure_image_text",
        "topic_configured": "generate_draft",
        "draft": "confirm_draft",
        "images": "suggest_images",
        "publish_check": "run_preflight",
        "publish_ready": "confirm_publish",
        "published": "done",
    }.get(current, "continue")


def _run_xhs_cli(args: list[str], timeout: float = 180) -> dict[str, Any]:
    if not XHS_CLI.exists():
        return {"ok": False, "error": f"小红书 CLI 不存在：{XHS_CLI}", "returncode": 127}
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        [sys.executable, str(XHS_CLI), *args],
        cwd=str(XHS_CLI.parent.parent),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
        check=False,
        env=env,
    )
    raw = (completed.stdout or "").strip()
    payload: dict[str, Any]
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        payload = {"raw": raw}
    payload.setdefault("ok", completed.returncode == 0)
    payload["returncode"] = completed.returncode
    payload["stderr"] = completed.stderr
    payload["command"] = [str(sys.executable), str(XHS_CLI), *args]
    return payload


def login_status() -> dict[str, Any]:
    return _run_xhs_cli(["check-login"], timeout=60)


def publish_preflight(project_id: str, check_login: bool = True) -> dict[str, Any]:
    project = load_project(project_id)
    workspace = resolve_project_workspace(project_id)
    title = shorten_title(str(project.get("title") or project.get("name") or ""))
    content = str(project.get("content") or "").strip()
    images = ordered_image_paths(project)
    login = login_status() if check_login else {"logged_in": True, "ok": True, "skipped": True}
    checks = [
        {"key": "title", "label": "标题", "ok": bool(title) and xhs_title_units(title) <= 20, "detail": f"{xhs_title_units(title):.1f}/20"},
        {"key": "content", "label": "正文", "ok": bool(content), "detail": f"{len(content)} 字"},
        {"key": "images", "label": "图片", "ok": bool(images), "detail": f"{len(images)} 张"},
        {"key": "login", "label": "小红书登录", "ok": bool(login.get("logged_in") or login.get("ok") and login.get("skipped")), "detail": str(login.get("message") or login.get("error") or "")},
    ]
    for image in images:
        checks.append(
            {
                "key": f"image:{image.name}",
                "label": image.name,
                "ok": image.exists() and image.suffix.lower() in XHS_IMAGE_EXTENSIONS,
                "detail": str(image),
            }
        )
    result = {
        "ok": all(item["ok"] for item in checks),
        "checks": checks,
        "blocking": [item for item in checks if not item["ok"]],
        "title": title,
        "content_path": _relative(workspace / "content.txt"),
        "title_path": _relative(workspace / "title.txt"),
        "image_paths": [str(path) for path in images],
        "tags": list(project.get("tags") or []),
        "login": login,
    }
    _write_json(workspace / "publish_preflight.json", result)
    update_project(project_id, title=title, preflight=result)
    return result


def export_publish_package(project_id: str) -> dict[str, Any]:
    project = load_project(project_id)
    workspace = resolve_project_workspace(project_id)
    preflight = publish_content_preflight(project_id)
    if not preflight["ok"]:
        raise ValueError("小红书图文导出检查未通过")
    project = load_project(project_id)
    title_path, content_path = _ensure_publish_files(project)
    tags = _clean_tags(project.get("tags") or [])
    images = ordered_image_paths(project)
    export_dir = workspace / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    package_path = export_dir / f"xhs_publish_package_{stamp}.zip"
    image_entries: list[dict[str, Any]] = []
    guide = [
        "# 小红书图文发布说明",
        "",
        "1. 解压本压缩包。",
        "2. 打开小红书发布页，按 `images/` 文件名顺序上传图片。",
        "3. 将 `title.txt` 粘贴为标题。",
        "4. 将 `content.txt` 粘贴为正文；如需单独添加标签，可参考 `tags.txt`。",
        "5. 发布前在小红书页面再次确认图片顺序、标题长度和正文格式。",
        "",
        "云端不会代替你登录或发布小红书，避免账号安全和平台风控风险。",
    ]
    manifest = {
        "project_id": project_id,
        "title": str(project.get("title") or project.get("name") or ""),
        "tags": tags,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "preflight": {
            "ok": preflight.get("ok"),
            "blocking": preflight.get("blocking") or [],
            "mode": preflight.get("mode") or "export",
        },
        "images": image_entries,
    }
    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(title_path, "title.txt")
        archive.write(content_path, "content.txt")
        archive.writestr("tags.txt", "\n".join(tags) + ("\n" if tags else ""))
        archive.writestr("publish_guide.md", "\n".join(guide) + "\n")
        for index, image in enumerate(images, start=1):
            arcname = f"images/{index:02d}{image.suffix.lower()}"
            archive.write(image, arcname)
            image_entries.append({"index": index, "filename": arcname, "source_path": str(image)})
        manifest["images"] = image_entries
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    result = {
        "ok": True,
        "package_path": _relative(package_path),
        "filename": package_path.name,
        "title": manifest["title"],
        "image_count": len(images),
        "tags": tags,
        "manifest": manifest,
        "guide": guide,
    }
    _write_json(workspace / "export_package.json", result)
    update_project(project_id, export_package=result, preflight=preflight)
    return result


def _ensure_publish_files(project: dict[str, Any]) -> tuple[Path, Path]:
    workspace = resolve_project_workspace(str(project["id"]))
    title = shorten_title(str(project.get("title") or project.get("name") or ""))
    content = normalize_content_with_tags(str(project.get("content") or ""), _clean_tags(project.get("tags") or []))
    title_path = workspace / "title.txt"
    content_path = workspace / "content.txt"
    title_path.write_text(title, encoding="utf-8")
    content_path.write_text(content, encoding="utf-8")
    return title_path, content_path


def fill_publish(project_id: str) -> dict[str, Any]:
    preflight = publish_preflight(project_id)
    if not preflight["ok"]:
        raise RuntimeError("发布预检未通过")
    project = load_project(project_id)
    title_path, content_path = _ensure_publish_files(project)
    args = [
        "fill-publish",
        "--title-file",
        str(title_path.resolve()),
        "--content-file",
        str(content_path.resolve()),
        "--images",
        *preflight["image_paths"],
    ]
    tags = _clean_tags(project.get("tags") or [])
    if tags:
        args.extend(["--tags", *tags])
    result = _run_xhs_cli(args, timeout=300)
    result["filled"] = bool(result.get("ok"))
    result["title_path"] = str(title_path.resolve())
    result["content_path"] = str(content_path.resolve())
    result["image_paths"] = preflight["image_paths"]
    workspace = resolve_project_workspace(project_id)
    _write_json(workspace / "publish_result.json", result)
    update_project(project_id, publish_result=result, status="active")
    if not result.get("ok"):
        raise RuntimeError(str(result.get("error") or result.get("stderr") or "填入小红书发布页失败"))
    return result


def confirm_publish(project_id: str) -> dict[str, Any]:
    result = _run_xhs_cli(["click-publish"], timeout=180)
    workspace = resolve_project_workspace(project_id)
    result["confirmed_publish"] = bool(result.get("ok"))
    _write_json(workspace / "publish_result.json", result)
    update_project(project_id, publish_result=result, status="published" if result.get("ok") else "active")
    if not result.get("ok"):
        raise RuntimeError(str(result.get("error") or result.get("stderr") or "小红书发布失败"))
    return result


def save_publish_draft(project_id: str) -> dict[str, Any]:
    result = _run_xhs_cli(["save-draft"], timeout=120)
    workspace = resolve_project_workspace(project_id)
    result["saved_draft"] = bool(result.get("ok"))
    _write_json(workspace / "publish_result.json", result)
    update_project(project_id, publish_result=result, status="active")
    if not result.get("ok"):
        raise RuntimeError(str(result.get("error") or result.get("stderr") or "保存小红书草稿失败"))
    return result
