"""Task 2.2 deterministic normalization and monthly graph aggregation pipeline."""

from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

if __package__:
    from .parse_excel import parse_extracted_data
else:  # Support ``python entity_aligner.py`` from this directory.
    from parse_excel import parse_extracted_data


SCHEMA_VERSION = "1.0.0"
ONTOLOGY_VERSION = "job-ontology-1.0.0"
DICTIONARY_VERSION = "synonyms-1.0.0"
CHINA_TZ = timezone(timedelta(hours=8))
PERIOD_PATTERN = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")

NOISE_BLACKLIST = {
    "沟通",
    "沟通能力",
    "团队协作",
    "抗压能力",
    "责任心",
    "学历",
    "工作经验",
    "积极主动",
    "熟练使用",
    "具备",
    "无不良记录",
}

LEVEL_MAPPING = {
    "初级": "junior",
    "中级": "mid",
    "高级": "senior",
    "实习": "intern",
    "专家": "expert",
}

ENTITY_TYPE_NAMES = {
    "skill": "Skill",
    "education": "Education",
    "certificate": "Certificate",
    "tech_stack": "TechStack",
    "industry": "Industry",
    "company": "Company",
}


def load_json_file(path: str | Path) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"未找到配置文件: {resolved}")
    with resolved.open("r", encoding="utf-8-sig") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"配置文件顶层必须是对象: {resolved}")
    return value


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return clean_text(value).lower() in {"1", "true", "yes", "y", "是"}


def confidence(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return min(1.0, max(0.0, parsed))


def is_valid_entity(raw_name: Any) -> bool:
    cleaned = clean_text(raw_name)
    if len(cleaned) <= 1:
        return False
    if re.search(r"[（(].*?[）)]", cleaned) and len(cleaned) > 15:
        return False
    if cleaned in NOISE_BLACKLIST:
        return False
    return not any(fragment in cleaned for fragment in ("年经验", "年以上", "学历"))


def generate_hash(text: Any) -> str:
    payload = clean_text(text)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generate_ascii_slug(prefix: str, raw_text: Any) -> str:
    value = clean_text(raw_text)
    if not value:
        return f"{prefix}:unknown"
    if re.fullmatch(r"[a-zA-Z0-9+.\-]+", value):
        slug = value.lower().replace(" ", "-").replace("+", "plus").replace(".", "dot")
        slug = re.sub(r"-+", "-", slug).strip("-")
        return f"{prefix}:{slug}"
    return f"{prefix}:hash-{hashlib.md5(value.encode('utf-8')).hexdigest()[:10]}"


def source_id_for(record: dict[str, Any], index: int) -> tuple[str, str]:
    raw = clean_text(record.get("jd_id") or record.get("url") or f"auto-{index}")
    for prefix in ("source:", "external:"):
        if raw.startswith(prefix):
            raw = raw[len(prefix) :]
    return f"source:{raw}", raw


def period_key_for(value: Any) -> str | None:
    text = clean_text(value)
    return text[:7] if len(text) >= 7 and PERIOD_PATTERN.fullmatch(text[:7]) else None


def period_bounds(period_key: str) -> tuple[str, str]:
    year, month = map(int, period_key.split("-"))
    start = f"{year:04d}-{month:02d}-01T00:00:00+08:00"
    if month == 12:
        end = f"{year + 1:04d}-01-01T00:00:00+08:00"
    else:
        end = f"{year:04d}-{month + 1:02d}-01T00:00:00+08:00"
    return start, end


def extract_evidence_and_type(
    skill_name: str,
    requirements_text: Any,
    responsibilities_text: Any,
) -> tuple[list[str], str]:
    text = f"{clean_text(requirements_text)} {clean_text(responsibilities_text)}".strip()
    if not text or not skill_name:
        return [], "mentioned"

    evidence: list[str] = []
    requirement_type = "required"
    for match in re.finditer(re.escape(skill_name), text, re.IGNORECASE):
        start, end = match.span()
        sentence_start = max(
            0,
            text.rfind("；", 0, start) + 1,
            text.rfind("。", 0, start) + 1,
            text.rfind("\n", 0, start) + 1,
        )
        candidates = [position for marker in ("；", "。", "\n") if (position := text.find(marker, end)) >= 0]
        sentence_end = min(candidates) if candidates else len(text)
        sentence = text[sentence_start:sentence_end].strip()
        if sentence and sentence not in evidence:
            evidence.append(sentence)
        if any(marker in sentence for marker in ("优先", "加分", "plus", "优势", "了解")):
            requirement_type = "preferred"
    return evidence, requirement_type


def parse_entities(raw_entities: Any) -> dict[str, list[dict[str, Any]]]:
    structured = {key: [] for key in ENTITY_TYPE_NAMES}
    if not isinstance(raw_entities, list):
        return structured
    for item in raw_entities:
        if not isinstance(item, dict):
            continue
        category = clean_text(item.get("type")).lower()
        if category not in structured:
            category = "skill"
        name = clean_text(item.get("name"))
        if not is_valid_entity(name):
            continue
        evidence_value = item.get("evidence")
        upstream_quote = evidence_value.get("quote") if isinstance(evidence_value, dict) else None
        structured[category].append(
            {
                "name": name,
                "confidence": item.get("confidence"),
                "upstream_evidence": clean_text(upstream_quote),
            }
        )
    return structured


def relation_types_by_entity_name(
    raw_entities: Any,
    raw_relations: Any,
) -> dict[str, str]:
    mention_names: dict[str, str] = {}
    if isinstance(raw_entities, list):
        for entity in raw_entities:
            if not isinstance(entity, dict):
                continue
            mention_id = clean_text(entity.get("mention_id"))
            name = clean_text(entity.get("name")).lower()
            if mention_id and name:
                mention_names[mention_id] = name

    result: dict[str, str] = {}
    if isinstance(raw_relations, list):
        for relation in raw_relations:
            if not isinstance(relation, dict):
                continue
            name = mention_names.get(clean_text(relation.get("tail_mention_id")))
            relation_type = clean_text(relation.get("type")).lower()
            if not name or relation_type not in {"requires", "prefers"}:
                continue
            if relation_type == "requires" or name not in result:
                result[name] = relation_type
    return result


def fallback_skills(value: Any) -> list[str]:
    if isinstance(value, dict):
        parsed = value
    elif isinstance(value, list):
        parsed = value
    else:
        text = clean_text(value)
        if not text:
            return []
        try:
            parsed = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            return []

    values: list[Any] = []
    if isinstance(parsed, dict):
        for group in parsed.values():
            if isinstance(group, list):
                values.extend(group)
    elif isinstance(parsed, list):
        values.extend(parsed)
    return [clean_text(item).replace("\\+", "+") for item in values if is_valid_entity(item)]


def without_nulls(properties: dict[str, Any] | None) -> dict[str, Any]:
    return {key: value for key, value in (properties or {}).items() if value is not None}


class GraphBatchBuilder:
    def __init__(self, batch_id: str) -> None:
        self.batch_id = batch_id
        self.nodes: dict[str, dict[str, Any]] = {}
        self.relationships: dict[str, dict[str, Any]] = {}

    def add_node(
        self,
        node_id: str,
        node_type: str,
        name: str,
        node_confidence: float,
        source_id: str,
        aliases: Iterable[str] | None = None,
        properties: dict[str, Any] | None = None,
    ) -> None:
        cleaned_aliases = sorted({clean_text(alias) for alias in aliases or [] if clean_text(alias)})
        if node_id not in self.nodes:
            self.nodes[node_id] = {
                "id": node_id,
                "type": node_type,
                "name": name,
                "confidence": node_confidence,
                "source_ids": [source_id],
                "aliases": cleaned_aliases,
                "properties": without_nulls(properties),
            }
            return

        node = self.nodes[node_id]
        if source_id not in node["source_ids"]:
            node["source_ids"].append(source_id)
        node["aliases"] = sorted(set(node["aliases"]) | set(cleaned_aliases))

    def add_relation(
        self,
        from_id: str,
        to_id: str,
        relationship_type: str,
        relationship_confidence: float,
        evidence_id: str | None = None,
        properties: dict[str, Any] | None = None,
        id_suffix: str | None = None,
    ) -> None:
        relationship_id = f"{from_id}|{relationship_type}|{to_id}"
        if id_suffix:
            relationship_id += f"|{id_suffix}"
        if relationship_id not in self.relationships:
            self.relationships[relationship_id] = {
                "id": relationship_id,
                "type": relationship_type,
                "from_id": from_id,
                "to_id": to_id,
                "confidence": relationship_confidence,
                "evidence_ids": [evidence_id] if evidence_id else [],
                "properties": without_nulls(properties),
            }
            return
        if evidence_id and evidence_id not in self.relationships[relationship_id]["evidence_ids"]:
            self.relationships[relationship_id]["evidence_ids"].append(evidence_id)

    def payload(self) -> dict[str, Any]:
        connected = {
            endpoint
            for relation in self.relationships.values()
            for endpoint in (relation["from_id"], relation["to_id"])
        }
        nodes = [
            node
            for node in self.nodes.values()
            if node["type"] != "TechStack" or node["id"] in connected
        ]
        return {
            "batch_id": self.batch_id,
            "producer": "task-2.2",
            "nodes": nodes,
            "relationships": list(self.relationships.values()),
        }


@dataclass(frozen=True)
class AlignmentResult:
    normalized_records: list[dict[str, Any]]
    graph_batch: dict[str, Any]
    deduplication_logs: list[dict[str, Any]]
    quality_report: dict[str, Any]


class EntityAlignmentPipeline:
    def __init__(self, synonym_path: str | Path, job_ontology_path: str | Path) -> None:
        self.registry = {key.lower().strip(): value for key, value in load_json_file(synonym_path).items()}
        self.job_ontology = load_json_file(job_ontology_path)
        self.job_aliases: dict[str, dict[str, Any]] = {}
        for canonical_name, job in self.job_ontology.items():
            self.job_aliases[canonical_name.lower().strip()] = job
            for alias in job.get("aliases", []):
                self.job_aliases[clean_text(alias).lower()] = job

    def align(self, records: list[dict[str, Any]], batch_id: str | None = None) -> AlignmentResult:
        now = datetime.now(CHINA_TZ)
        generated_at = now.isoformat()
        batch_id = batch_id or f"task-2.2-auto-{now.strftime('%Y%m%d-%H%M%S')}"
        unique_records, deduplication_logs = self._deduplicate(records)

        graph = GraphBatchBuilder(batch_id)
        normalized: list[dict[str, Any]] = []
        relation_aggregator: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "required_jd_ids": set(),
                "preferred_jd_ids": set(),
                "skill_jd_ids": set(),
                "evidence": set(),
            }
        )
        job_period_jd_ids: dict[tuple[str, str], set[str]] = defaultdict(set)
        low_confidence_mentions = 0
        missing_published_at = 0
        parse_issue_count = 0

        for record in unique_records:
            parse_issue_count += len(record.get("_parse_issues") or [])
            source_id = record["_source_id"]
            jd_id = record["_jd_id"]
            requirements = clean_text(record.get("requirements"))
            responsibilities = clean_text(record.get("responsibilities"))
            published_at = record.get("published_at")
            crawled_at = record.get("crawled_at")
            period_key = period_key_for(published_at)
            if period_key is None:
                missing_published_at += 1

            graph.add_node(
                source_id,
                "Source",
                source_id,
                1.0,
                source_id,
                properties={
                    "document_type": "job_description",
                    "content_hash": record["_content_hash"],
                    "crawled_at": crawled_at,
                    "url": clean_text(record.get("url")),
                    "published_at": published_at,
                    "source_platform": clean_text(record.get("source_platform")),
                    "jd_id": jd_id,
                },
            )

            raw_title = clean_text(record.get("job_title_raw")) or "未知岗位"
            job_id, job_name, job_aliases, job_is_new = self._align_job(raw_title)
            level_raw = clean_text(record.get("job_level_raw"))
            job_properties = {
                "description": responsibilities[:200],
                "level": LEVEL_MAPPING.get(level_raw, "unknown"),
                "education_required": clean_text(record.get("education")),
            }
            if level_raw:
                job_properties["level_raw"] = level_raw
            graph.add_node(
                job_id,
                "Job",
                job_name,
                0.9 if not job_is_new else 0.8,
                source_id,
                aliases=job_aliases,
                properties=job_properties,
            )
            graph.add_relation(job_id, source_id, "DERIVED_FROM", 1.0, source_id)
            if period_key:
                job_period_jd_ids[(job_id, period_key)].add(jd_id)

            raw_entities = record.get("extracted_entities_json") or []
            relation_types = relation_types_by_entity_name(
                raw_entities,
                record.get("extracted_relations_json") or [],
            )
            review_reasons: list[str] = []
            needs_review = parse_bool(record.get("needs_human_review"))
            skill_buffer: dict[str, dict[str, Any]] = {}
            seen_entity_ids: set[str] = set()
            ignored_job_names = {
                raw_title.lower(),
                job_name.lower(),
                *(clean_text(alias).lower() for alias in job_aliases),
            }

            normalized_record = {
                "schema_version": SCHEMA_VERSION,
                "jd_id": jd_id,
                "source_id": source_id,
                "source_platform": clean_text(record.get("source_platform")),
                "url": clean_text(record.get("url")),
                "document_type": "job_description",
                "published_at": published_at,
                "crawled_at": crawled_at,
                "content_hash": record["_content_hash"],
                "raw_text": clean_text(record.get("raw_text")),
                "responsibilities": responsibilities,
                "job": {
                    "raw_name": raw_title,
                    "canonical_id": job_id,
                    "canonical_name": job_name,
                    "aliases": job_aliases,
                    "level": job_properties["level"],
                    "alignment_confidence": 0.95 if not job_is_new else 0.8,
                    "is_new_candidate": job_is_new,
                },
                "skills": [],
                "tech_stacks": [],
                "industries": [],
                "certificates": [],
                "education": [],
                "company": None,
                "alignment_meta": {
                    "ontology_version": ONTOLOGY_VERSION,
                    "dictionary_version": DICTIONARY_VERSION,
                    "method": "hybrid",
                    "needs_human_review": False,
                    "normalized_at": generated_at,
                    "conflicts": [],
                    "review_reasons": review_reasons,
                },
            }

            for category, entities in parse_entities(raw_entities).items():
                for entity in entities:
                    raw_name = entity["name"]
                    lower_name = raw_name.lower().strip()
                    if category == "skill" and lower_name in ignored_job_names:
                        continue
                    canonical = self._align_entity(category, raw_name)
                    if canonical["id"] in seen_entity_ids and canonical["type"] != "Skill":
                        continue
                    seen_entity_ids.add(canonical["id"])
                    if canonical["is_new"]:
                        low_confidence_mentions += 1
                        needs_review = True

                    upstream_type = relation_types.get(lower_name)
                    requirement_type = "preferred" if upstream_type == "prefers" else "required"
                    evidence = [entity["upstream_evidence"]] if entity["upstream_evidence"] else []
                    if not evidence:
                        evidence, fallback_type = extract_evidence_and_type(raw_name, requirements, responsibilities)
                        if upstream_type is None and fallback_type == "preferred":
                            requirement_type = "preferred"
                    entity_confidence = confidence(
                        entity.get("confidence"),
                        0.8 if canonical["is_new"] else 1.0,
                    )
                    if canonical["type"] == "Skill":
                        self._merge_skill(
                            skill_buffer,
                            canonical,
                            raw_name,
                            entity_confidence,
                            requirement_type,
                            evidence,
                        )
                    else:
                        self._add_non_skill(
                            normalized_record,
                            graph,
                            canonical,
                            raw_name,
                            entity_confidence,
                            source_id,
                            job_id,
                        )

            if not skill_buffer:
                for fallback_name in fallback_skills(record.get("extracted_skills")):
                    if fallback_name.lower() in ignored_job_names:
                        continue
                    registry_entry = self.registry.get(fallback_name.lower().strip())
                    if registry_entry and registry_entry.get("type") == "Skill":
                        # Auxiliary-column fallbacks must reuse known canonical
                        # skills as well.  This keeps C++, cpp and cplusplus on
                        # the same node instead of producing skill:cplusplus.
                        canonical = self._align_entity("skill", fallback_name)
                    else:
                        canonical = {
                            "id": generate_ascii_slug("skill", fallback_name.lower()),
                            "name": fallback_name,
                            "type": "Skill",
                            "category": "Domain Specific",
                            "is_new": True,
                        }
                    evidence, fallback_type = extract_evidence_and_type(
                        fallback_name,
                        requirements,
                        responsibilities,
                    )
                    self._merge_skill(
                        skill_buffer,
                        canonical,
                        fallback_name,
                        0.7,
                        "preferred" if fallback_type == "preferred" else "required",
                        evidence or [fallback_name],
                    )
                if skill_buffer:
                    needs_review = True
                    review_reasons.append("fallback_skill_extraction")

            self._add_company_and_industry_fallbacks(
                normalized_record,
                graph,
                record,
                job_id,
                source_id,
            )

            for skill_id, skill in skill_buffer.items():
                skill["evidence"] = sorted(set(skill["evidence"]))
                skill["aliases"] = sorted(set(skill["aliases"]))
                normalized_record["skills"].append(skill)
                graph.add_node(
                    skill_id,
                    "Skill",
                    skill["canonical_name"],
                    skill["confidence"],
                    source_id,
                    aliases=skill["aliases"],
                    properties={"category": skill["category"]},
                )
                self._add_stack_membership(graph, skill_id, source_id)
                if skill["is_new_candidate"]:
                    needs_review = True
                if period_key:
                    aggregate_key = f"{job_id}||{period_key}||{skill_id}"
                    aggregate = relation_aggregator[aggregate_key]
                    aggregate["skill_jd_ids"].add(jd_id)
                    aggregate["evidence"].add(source_id)
                    aggregate[f"{skill['requirement_type']}_jd_ids"].add(jd_id)

            if not normalized_record["skills"]:
                needs_review = True
                review_reasons.append("no_standard_skill_after_fallback")
            if job_is_new:
                needs_review = True
            if needs_review and not review_reasons:
                review_reasons.append("upstream_needs_human_review")
            normalized_record["alignment_meta"]["needs_human_review"] = needs_review
            normalized_record["alignment_meta"]["review_reasons"] = sorted(set(review_reasons))
            normalized_record["skills"] = sorted(
                normalized_record["skills"], key=lambda item: item["canonical_id"]
            )
            normalized.append(normalized_record)

        for aggregate_key, aggregate in relation_aggregator.items():
            job_id, period_key, skill_id = aggregate_key.split("||")
            skill_count = len(aggregate["skill_jd_ids"])
            required_count = len(aggregate["required_jd_ids"])
            preferred_count = len(aggregate["preferred_jd_ids"])
            job_count = len(job_period_jd_ids[(job_id, period_key)])
            demand_ratio = skill_count / job_count if job_count else 0.0
            required_ratio = required_count / skill_count if skill_count else 0.0
            period_start, period_end = period_bounds(period_key)
            relationship_type = "REQUIRES_SKILL" if required_count else "BONUS_SKILL"
            properties = {
                "period_key": period_key,
                "period_start": period_start,
                "period_end": period_end,
                "job_jd_count": job_count,
                "skill_jd_count": skill_count,
                "required_jd_count": required_count,
                "preferred_jd_count": preferred_count,
                "required_ratio": round(required_ratio, 4),
                "demand_ratio": round(demand_ratio, 4),
                "importance": round(0.7 * demand_ratio + 0.3 * required_ratio, 4),
                "importance_method": "0.7 * demand_ratio + 0.3 * required_ratio",
            }
            for evidence_id in sorted(aggregate["evidence"]):
                graph.add_relation(
                    job_id,
                    skill_id,
                    relationship_type,
                    0.9,
                    evidence_id,
                    properties=properties,
                    id_suffix=period_key,
                )

        graph_batch = graph.payload()
        graph_errors, cross_period_count = validate_graph_batch(graph_batch)
        period_counts: dict[str, int] = defaultdict(int)
        for record in normalized:
            period = period_key_for(record.get("published_at"))
            if period:
                period_counts[period] += 1
        periodic_relationships = [
            relation
            for relation in graph_batch["relationships"]
            if relation["type"] in {"REQUIRES_SKILL", "BONUS_SKILL"}
            and relation["properties"].get("period_key")
        ]
        quality_report = {
            "schema_version": SCHEMA_VERSION,
            "batch_id": batch_id,
            "total_records": len(records),
            "structurally_valid_records": len(unique_records),
            "valid_records": len(unique_records),
            "discovery_eligible_records": sum(bool(record["skills"]) for record in normalized),
            "excluded_zero_skill_records": sum(not record["skills"] for record in normalized),
            "duplicate_records": len(deduplication_logs),
            "missing_published_at": missing_published_at,
            "missing_job_title": sum(record["job"]["raw_name"] == "未知岗位" for record in normalized),
            "missing_evidence": sum(
                not skill["evidence"] for record in normalized for skill in record["skills"]
            ),
            "invalid_source_json_cells": parse_issue_count,
            "low_confidence_entity_mentions": low_confidence_mentions,
            "human_review_required": sum(
                record["alignment_meta"]["needs_human_review"] for record in normalized
            ),
            "rejected_records": 0,
            "records_by_period": dict(sorted(period_counts.items())),
            "periodic_skill_relationships": len(periodic_relationships),
            "graph_validation_passed": not graph_errors,
            "graph_validation_errors": graph_errors[:100],
            "cross_period_evidence_relationships": cross_period_count,
            "ontology_version": ONTOLOGY_VERSION,
            "dictionary_version": DICTIONARY_VERSION,
            "model_version": "v1-hybrid",
            "prompt_version": "v1.0",
            "generated_at": generated_at,
        }
        return AlignmentResult(normalized, graph_batch, deduplication_logs, quality_report)

    def _deduplicate(
        self,
        records: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        unique_by_source: dict[str, dict[str, Any]] = {}
        source_by_hash: dict[str, str] = {}
        logs: list[dict[str, Any]] = []
        for index, original in enumerate(records):
            record = dict(original)
            source_id, jd_id = source_id_for(record, index)
            content_hash = clean_text(record.get("content_hash")) or generate_hash(
                clean_text(record.get("raw_text")) + clean_text(record.get("job_title_raw"))
            )
            if source_id in unique_by_source:
                logs.append(
                    {
                        "kept_jd_id": source_id,
                        "duplicate_jd_ids": [source_id],
                        "reason": "same_jd_id",
                    }
                )
                continue
            if content_hash in source_by_hash:
                logs.append(
                    {
                        "kept_jd_id": source_by_hash[content_hash],
                        "duplicate_jd_ids": [source_id],
                        "reason": "same_content_hash",
                    }
                )
                continue
            record["_source_id"] = source_id
            record["_jd_id"] = jd_id
            record["_content_hash"] = content_hash
            unique_by_source[source_id] = record
            source_by_hash[content_hash] = source_id
        return list(unique_by_source.values()), logs

    def _align_job(self, raw_title: str) -> tuple[str, str, list[str], bool]:
        normalized = raw_title.lower().strip()
        matched = self.job_aliases.get(normalized)
        if matched is None:
            for alias, job in self.job_aliases.items():
                if alias in normalized or normalized in alias:
                    matched = job
                    break
        if matched is None:
            return generate_ascii_slug("job", raw_title), raw_title, [raw_title], True
        aliases = sorted({clean_text(alias) for alias in matched.get("aliases", []) if clean_text(alias)})
        return matched["id"], matched["name"], aliases or [matched["name"]], False

    def _align_entity(self, category: str, raw_name: str) -> dict[str, Any]:
        normalized = raw_name.lower().strip()
        matched = self.registry.get(normalized)
        if matched:
            return {
                "id": matched["id"],
                "name": matched["name"],
                "type": matched["type"],
                "category": matched.get("category", "General"),
                "is_new": False,
            }

        node_type = ENTITY_TYPE_NAMES[category]
        prefix = {
            "Skill": "skill",
            "Education": "edu",
            "Certificate": "cert",
            "Industry": "industry",
            "Company": "company",
            "TechStack": "stack",
        }[node_type]
        return {
            "id": generate_ascii_slug(prefix, normalized),
            "name": raw_name,
            "type": node_type,
            "category": "Domain Specific",
            "is_new": True,
        }

    @staticmethod
    def _merge_skill(
        buffer: dict[str, dict[str, Any]],
        canonical: dict[str, Any],
        raw_name: str,
        entity_confidence: float,
        requirement_type: str,
        evidence: Iterable[str],
    ) -> None:
        skill_id = canonical["id"]
        if skill_id not in buffer:
            buffer[skill_id] = {
                "raw_name": raw_name,
                "canonical_id": skill_id,
                "canonical_name": canonical["name"],
                "aliases": [raw_name],
                "confidence": entity_confidence,
                "is_new_candidate": canonical["is_new"],
                "category": canonical["category"],
                "requirement_type": requirement_type,
                "proficiency": None,
                "min_years": None,
                "evidence": list(evidence),
            }
            return
        existing = buffer[skill_id]
        existing["aliases"].append(raw_name)
        existing["evidence"].extend(evidence)
        existing["confidence"] = max(existing["confidence"], entity_confidence)
        if requirement_type == "required":
            existing["requirement_type"] = "required"

    @staticmethod
    def _add_non_skill(
        record: dict[str, Any],
        graph: GraphBatchBuilder,
        canonical: dict[str, Any],
        raw_name: str,
        entity_confidence: float,
        source_id: str,
        job_id: str,
    ) -> None:
        node_type = canonical["type"]
        value = {"canonical_id": canonical["id"], "name": canonical["name"]}
        target_key = {
            "TechStack": "tech_stacks",
            "Industry": "industries",
            "Education": "education",
            "Certificate": "certificates",
        }.get(node_type)
        if target_key and value not in record[target_key]:
            record[target_key].append(value)
        elif node_type == "Company":
            record["company"] = value

        graph.add_node(
            canonical["id"],
            node_type,
            canonical["name"],
            entity_confidence,
            source_id,
            aliases=[raw_name],
        )
        relationship_type = {
            "Industry": "APPLIES_TO_INDUSTRY",
            "Education": "REQUIRES_EDUCATION",
            "Certificate": "REQUIRES_CERTIFICATE",
            "Company": "PUBLISHED_BY",
        }.get(node_type)
        if relationship_type:
            graph.add_relation(job_id, canonical["id"], relationship_type, 0.9, source_id)

    @staticmethod
    def _add_company_and_industry_fallbacks(
        record: dict[str, Any],
        graph: GraphBatchBuilder,
        source: dict[str, Any],
        job_id: str,
        source_id: str,
    ) -> None:
        if not record["company"] and clean_text(source.get("company_raw")):
            name = clean_text(source["company_raw"])
            company_id = generate_ascii_slug("company", name)
            record["company"] = {"canonical_id": company_id, "name": name}
            graph.add_node(company_id, "Company", name, 1.0, source_id)
            graph.add_relation(job_id, company_id, "PUBLISHED_BY", 1.0, source_id)

        if not record["industries"] and clean_text(source.get("industry_raw")):
            name = clean_text(source["industry_raw"])
            industry_id = f"industry:{hashlib.md5(name.encode('utf-8')).hexdigest()[:8]}"
            record["industries"].append({"canonical_id": industry_id, "name": name})
            graph.add_node(industry_id, "Industry", name, 1.0, source_id)
            graph.add_relation(job_id, industry_id, "APPLIES_TO_INDUSTRY", 1.0, source_id)

    @staticmethod
    def _add_stack_membership(graph: GraphBatchBuilder, skill_id: str, source_id: str) -> None:
        if any(token in skill_id for token in ("docker", "kubernetes", "aws", "azure")):
            stack_id, stack_name = "stack:cloud-native", "Cloud Native"
        elif any(token in skill_id for token in ("hadoop", "spark", "flink", "hive")):
            stack_id, stack_name = "stack:big-data", "Big Data"
        else:
            return
        graph.add_node(stack_id, "TechStack", stack_name, 1.0, source_id)
        graph.add_relation(skill_id, stack_id, "BELONGS_TO_STACK", 0.9, source_id)


def validate_graph_batch(graph_batch: dict[str, Any]) -> tuple[list[str], int]:
    errors: list[str] = []
    nodes = graph_batch["nodes"]
    relationships = graph_batch["relationships"]
    node_ids = {node["id"] for node in nodes}
    source_periods = {
        node["id"]: period_key_for(node["properties"].get("published_at"))
        for node in nodes
        if node["type"] == "Source"
    }
    if len(node_ids) != len(nodes):
        errors.append("duplicate_node_ids")
    if len({relation["id"] for relation in relationships}) != len(relationships):
        errors.append("duplicate_relationship_ids")

    cross_period_relationships = 0
    for relation in relationships:
        if relation["from_id"] not in node_ids or relation["to_id"] not in node_ids:
            errors.append(f"missing_endpoint:{relation['id']}")
        for evidence_id in relation["evidence_ids"]:
            if evidence_id not in node_ids:
                errors.append(f"missing_evidence_node:{relation['id']}:{evidence_id}")
        if relation["type"] not in {"REQUIRES_SKILL", "BONUS_SKILL"}:
            continue
        properties = relation["properties"]
        period_key = properties.get("period_key")
        if not period_key:
            continue
        required = {
            "period_start",
            "period_end",
            "job_jd_count",
            "skill_jd_count",
            "required_jd_count",
            "preferred_jd_count",
            "required_ratio",
            "demand_ratio",
            "importance",
            "importance_method",
        }
        missing = required - properties.keys()
        if missing:
            errors.append(f"missing_period_properties:{relation['id']}:{sorted(missing)}")
            continue
        if period_key not in relation["id"]:
            errors.append(f"period_not_in_id:{relation['id']}")
        skill_count = int(properties["skill_jd_count"])
        job_count = int(properties["job_jd_count"])
        required_count = int(properties["required_jd_count"])
        if len(set(relation["evidence_ids"])) != skill_count:
            errors.append(f"evidence_count_mismatch:{relation['id']}")
        if skill_count > job_count:
            errors.append(f"skill_count_exceeds_job_count:{relation['id']}")
        if job_count and abs(float(properties["demand_ratio"]) - skill_count / job_count) > 0.001:
            errors.append(f"bad_demand_ratio:{relation['id']}")
        if skill_count and abs(float(properties["required_ratio"]) - required_count / skill_count) > 0.001:
            errors.append(f"bad_required_ratio:{relation['id']}")
        expected_importance = 0.7 * float(properties["demand_ratio"]) + 0.3 * float(properties["required_ratio"])
        if abs(float(properties["importance"]) - expected_importance) > 0.001:
            errors.append(f"bad_importance:{relation['id']}")
        if any(source_periods.get(item) != period_key for item in relation["evidence_ids"]):
            cross_period_relationships += 1
            errors.append(f"cross_period_evidence:{relation['id']}")
    return errors, cross_period_relationships


def write_result(result: AlignmentResult, output_dir: str | Path) -> dict[str, Path]:
    directory = Path(output_dir).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "normalized": directory / "normalized_records.jsonl",
        "graph": directory / "graph_import_batch.json",
        "deduplication": directory / "deduplication_logs.json",
        "quality": directory / "quality_report.json",
    }
    with paths["normalized"].open("w", encoding="utf-8", newline="\n") as stream:
        for record in result.normalized_records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    for key, value in (
        ("graph", result.graph_batch),
        ("deduplication", result.deduplication_logs),
        ("quality", result.quality_report),
    ):
        with paths[key].open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    return paths


def default_paths() -> tuple[Path, Path, Path, Path]:
    pipeline_dir = Path(__file__).resolve().parent
    project_root = pipeline_dir.parents[1]
    return (
        project_root / "data" / "raw" / "1000条抽取数据.xlsx",
        project_root / "data" / "processed" / "task_2_2",
        pipeline_dir / "job_ontology.json",
        pipeline_dir / "synonym_map.json",
    )


def build_parser() -> argparse.ArgumentParser:
    default_input, default_output, default_jobs, default_synonyms = default_paths()
    parser = argparse.ArgumentParser(description="将2.1 Excel转换为2.2 JSONL和月度图谱批次")
    parser.add_argument("--input", type=Path, default=default_input, help="2.1 Excel路径")
    parser.add_argument("--output-dir", type=Path, default=default_output, help="输出目录")
    parser.add_argument("--job-ontology", type=Path, default=default_jobs, help="岗位本体JSON")
    parser.add_argument("--synonyms", type=Path, default=default_synonyms, help="实体同义词JSON")
    parser.add_argument("--batch-id", help="可选的固定批次ID；默认使用当前时间")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    records = parse_extracted_data(args.input)
    pipeline = EntityAlignmentPipeline(args.synonyms, args.job_ontology)
    result = pipeline.align(records, args.batch_id)
    paths = write_result(result, args.output_dir)
    print(f"输入记录: {result.quality_report['total_records']}")
    print(f"标准化记录: {result.quality_report['structurally_valid_records']}")
    print(f"发现分析有效记录: {result.quality_report['discovery_eligible_records']}")
    print(f"月度岗位技能关系: {result.quality_report['periodic_skill_relationships']}")
    print(f"图谱校验: {'通过' if result.quality_report['graph_validation_passed'] else '失败'}")
    for label, path in paths.items():
        print(f"{label}: {path}")
    return 0 if result.quality_report["graph_validation_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
