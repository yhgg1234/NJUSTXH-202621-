"""将 2.3 知识图谱子图适配为 3.3 岗位画像。"""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.graph.dependencies import get_graph_service
from app.matching.models import JobProfile, JobSkillRequirement


def load_job_profile_from_graph(job_id: str) -> JobProfile | None:
    """优先从 2.3 图谱读取岗位能力要求。

    2.3 目前提供的是子图查询接口，因此这里把子图中的节点和关系转换为
    3.3 匹配算法需要的岗位画像。图谱不可用时返回 None，由服务层回退到
    并行开发阶段的演示岗位数据。
    """
    try:
        subgraph = get_graph_service().get_subgraph(
            job_id=job_id,
            tech_stack=None,
            level=None,
            industry=None,
            period=None,
            as_of=None,
            include_history=False,
            limit=120,
        )
    except Exception as exc:  # noqa: BLE001 - 图谱服务不可用时允许降级
        logger.warning("Failed to load job profile from graph: {}", exc)
        return None

    nodes = subgraph.get("nodes", [])
    links = subgraph.get("links", [])
    if not nodes:
        return None

    node_map = {node.get("id"): node for node in nodes}
    job_node = node_map.get(job_id)
    if not job_node:
        return None

    skills: list[JobSkillRequirement] = []
    industries: list[str] = []
    tech_stacks: list[str] = []
    certificates: list[str] = []
    education_required: str | None = None

    for link in links:
        if link.get("source") != job_id:
            continue
        target = node_map.get(link.get("target"))
        if not target:
            continue
        rel_type = link.get("type")
        target_type = target.get("type")
        props = link.get("properties") or {}

        if rel_type in {"REQUIRES_SKILL", "BONUS_SKILL"} and target_type == "Skill":
            skills.append(_skill_from_graph_node(target, props, rel_type == "REQUIRES_SKILL"))
        elif rel_type == "APPLIES_TO_INDUSTRY" and target_type == "Industry":
            industries.append(_node_label(target))
        elif rel_type == "REQUIRES_CERTIFICATE" and target_type == "Certificate":
            certificates.append(_node_label(target))
        elif rel_type == "REQUIRES_EDUCATION" and target_type == "Education":
            education_required = _node_label(target)

    skill_ids = {skill.normalized_id for skill in skills}
    for link in links:
        if link.get("type") != "BELONGS_TO_STACK":
            continue
        if link.get("source") not in skill_ids:
            continue
        stack_node = node_map.get(link.get("target"))
        if stack_node and stack_node.get("type") == "TechStack":
            tech_stacks.append(_node_label(stack_node))

    properties = job_node.get("properties") or {}
    experience_years = _experience_years(properties)
    if not education_required:
        education_required = _string_or_none(properties.get("education_required"))

    return JobProfile(
        id=job_id,
        title=_node_label(job_node),
        description=_string_or_none(properties.get("description")) or "",
        skills=skills,
        education_required=education_required,
        experience_years=experience_years,
        industries=_dedupe(industries),
        tech_stacks=_dedupe(tech_stacks),
        certificates=_dedupe(certificates),
    )


def _skill_from_graph_node(
    node: dict[str, Any],
    relationship_properties: dict[str, Any],
    required: bool,
) -> JobSkillRequirement:
    node_properties = node.get("properties") or {}
    aliases = node_properties.get("aliases") or []
    if not isinstance(aliases, list):
        aliases = []
    return JobSkillRequirement(
        name=_node_label(node),
        normalized_id=node.get("id"),
        required=required,
        proficiency=_string_or_none(relationship_properties.get("proficiency")),
        years=_float_or_none(relationship_properties.get("years")),
        importance=_importance(relationship_properties),
        aliases=[str(item) for item in aliases],
    )


def _node_label(node: dict[str, Any]) -> str:
    return str(node.get("label") or node.get("id") or "")


def _importance(properties: dict[str, Any]) -> float:
    raw = properties.get("importance")
    if raw is None:
        raw = properties.get("frequency")
        if raw is not None:
            return min(1.0, max(0.1, float(raw) / 20.0))
    try:
        return min(1.0, max(0.1, float(raw)))
    except (TypeError, ValueError):
        return 1.0


def _experience_years(properties: dict[str, Any]) -> tuple[int, int] | None:
    value = properties.get("experience_years")
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return int(value[0]), int(value[1])
        except (TypeError, ValueError):
            return None
    minimum = properties.get("min_experience_years")
    preferred = properties.get("preferred_experience_years")
    if minimum is not None:
        try:
            min_value = int(minimum)
            preferred_value = int(preferred) if preferred is not None else min_value
            return min_value, preferred_value
        except (TypeError, ValueError):
            return None
    return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.strip()
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result
