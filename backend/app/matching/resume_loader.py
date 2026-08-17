"""读取 3.2 产出的结构化简历，并适配为 3.3 的领域模型。"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import ValidationError

from app.matching.models import (
    ResumeEducationProfile,
    ResumeProfile,
    ResumeProjectProfile,
    ResumeSkillProfile,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESUME_DIR = REPO_ROOT / "data" / "processed" / "resumes"
_SECTION_NAMES = {"基本信息", "相关技能", "技能", "个人信息", "教育经历", "工作经历"}


def load_processed_resumes(resume_dir: Path | None = None) -> dict[str, ResumeProfile]:
    """加载目录中的单对象或数组 JSON，跳过不合法文件但不阻断服务启动。"""
    directory = resume_dir or DEFAULT_RESUME_DIR
    if not directory.exists():
        return {}

    resumes: dict[str, ResumeProfile] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Skip unreadable resume file {}: {}", path.name, exc)
            continue

        records: Iterable[Any] = payload if isinstance(payload, list) else [payload]
        for index, record in enumerate(records, start=1):
            if not isinstance(record, dict):
                logger.warning("Skip invalid resume record in {} at index {}", path.name, index)
                continue
            try:
                profile = ResumeProfile.model_validate(
                    _normalize_resume_payload(record, fallback_id=f"{path.stem}-{index}")
                )
            except ValidationError as exc:
                logger.warning("Skip invalid resume record in {}: {}", path.name, exc.errors()[0]["msg"])
                continue
            if profile.id in resumes:
                logger.warning("Duplicate resume id {}, keep the first record", profile.id)
                continue
            resumes[profile.id] = profile
    return resumes


def display_resume_name(resume: ResumeProfile) -> str:
    """给前端提供稳定、不会暴露联系方式的候选人显示名。"""
    name = " ".join(resume.name.split())
    if not name or name in _SECTION_NAMES or _looks_like_contact_text(name):
        return f"候选人 {resume.id.removeprefix('resume-')}"
    return name[:40]


def _normalize_resume_payload(payload: dict[str, Any], fallback_id: str) -> dict[str, Any]:
    """将 3.2 允许出现的 null 字段转换为 3.3 领域模型的默认值。"""
    return {
        "id": _text(payload.get("id")) or fallback_id,
        "name": _text(payload.get("name")),
        "education": [
            {"school": _text(item.get("school")), "degree": _text(item.get("degree")), "major": _text(item.get("major"))}
            for item in _dict_items(payload.get("education"))
        ],
        "skills": [
            {"name": _text(item.get("name")), "normalized_id": _optional_text(item.get("normalized_id")), "proficiency": _optional_text(item.get("proficiency")), "years": _number_or_none(item.get("years")), "evidence": _text_list(item.get("evidence"))}
            for item in _dict_items(payload.get("skills"))
            if _text(item.get("name"))
        ],
        "projects": [
            {"name": _text(item.get("name")), "role": _text(item.get("role")), "description": _text(item.get("description")), "tech_stacks": _text_list(item.get("tech_stacks")), "achievements": _text_list(item.get("achievements"))}
            for item in _dict_items(payload.get("projects"))
            if _text(item.get("name"))
        ],
        "industries": _text_list(payload.get("industries")),
        "certificates": _text_list(payload.get("certificates")),
        "years_of_experience": _number_or_zero(payload.get("years_of_experience")),
        "confidence": min(1.0, max(0.0, _number_or_one(payload.get("confidence")))),
    }


def _dict_items(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _text_list(value: Any) -> list[str]:
    return [_text(item) for item in value if _text(item)] if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _optional_text(value: Any) -> str | None:
    return _text(value) or None


def _number_or_none(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _number_or_zero(value: Any) -> float:
    return _number_or_none(value) or 0.0


def _number_or_one(value: Any) -> float:
    result = _number_or_none(value)
    return result if result is not None else 1.0


def _looks_like_contact_text(name: str) -> bool:
    return bool(re.search(r"\d{7,}|电话|邮箱|年龄|性别", name))


def load_mongodb_resumes() -> dict[str, ResumeProfile]:
    """从简历模块的 MongoDB 存储读取已解析简历，转换为匹配模块的 ResumeProfile。"""
    try:
        from pymongo import MongoClient

        from app.config import settings

        client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=2000)
        collection = client[settings.MONGO_DATABASE]["resumes"]
        docs = list(collection.find({}).sort("created_at", -1))
    except Exception as exc:  # noqa: BLE001 - MongoDB 不可用时降级
        logger.warning("Failed to load resumes from MongoDB: {}", exc)
        return {}

    resumes: dict[str, ResumeProfile] = {}
    for doc in docs:
        parsed = doc.get("parsed_data")
        if not isinstance(parsed, dict):
            continue
        profile = _parsed_resume_to_profile(parsed)
        if profile and profile.id:
            resumes.setdefault(profile.id, profile)
    return resumes


def _parsed_resume_to_profile(parsed: dict[str, Any]) -> ResumeProfile | None:
    """将简历模块的 ParsedResume 字典转换为匹配模块的 ResumeProfile。"""
    resume_id = _text(parsed.get("id"))
    if not resume_id:
        return None
    education = [
        ResumeEducationProfile(
            school=_text(item.get("school")),
            degree=_text(item.get("degree")),
            major=_text(item.get("major")),
        )
        for item in _dict_items(parsed.get("education"))
    ]
    skills = [
        ResumeSkillProfile(name=_text(item))
        for item in (parsed.get("skills") or [])
        if isinstance(item, str) and _text(item)
    ]
    projects = [
        ResumeProjectProfile(
            name=_text(item.get("name")),
            role=_text(item.get("role")),
            description=_text(item.get("description")),
            tech_stacks=_text_list(item.get("tech_stacks")),
            achievements=_text_list(item.get("achievements")),
        )
        for item in _dict_items(parsed.get("projects"))
        if _text(item.get("name"))
    ]
    return ResumeProfile(
        id=resume_id,
        name=_text(parsed.get("name")),
        education=education,
        skills=skills,
        projects=projects,
        industries=[],
        certificates=_text_list(parsed.get("certificates")),
        years_of_experience=0.0,
        confidence=min(1.0, max(0.0, _number_or_one(parsed.get("confidence")))),
    )
