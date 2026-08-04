"""读取并校验子任务 2.2 交付的 normalized JSON/JSONL。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from app.discovery.models import DiscoveryDataQuality


class NormalizedDataError(ValueError):
    pass


@dataclass(frozen=True)
class NormalizedSkill:
    id: str
    name: str
    raw_name: str
    requirement_type: str
    proficiency: str | None
    min_years: float | None
    confidence: float
    evidence: tuple[str, ...]
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class NormalizedJobRecord:
    jd_id: str
    source_id: str
    source_channel: str
    published_at: datetime
    content_hash: str | None
    job_id: str
    raw_name: str
    canonical_name: str
    description: str
    responsibilities: tuple[str, ...]
    is_new_candidate: bool
    company: str
    industries: tuple[str, ...]
    skills: tuple[NormalizedSkill, ...]
    confidence: float


@dataclass
class NormalizedLoadResult:
    records: list[NormalizedJobRecord]
    quality: DiscoveryDataQuality


class NormalizedRecordReader:
    """兼容单个 JSON/JSONL 文件或递归目录的只读适配器。"""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self, time_range: tuple[date, date] | None = None) -> NormalizedLoadResult:
        files = self._files()
        raw_records: list[dict[str, Any]] = []
        warnings: list[str] = []
        for path in files:
            try:
                raw_records.extend(_read_records(path))
            except (OSError, json.JSONDecodeError, NormalizedDataError) as exc:
                warnings.append(f"无法读取 {path}: {exc}")

        records: list[NormalizedJobRecord] = []
        seen: set[tuple[str, str | None]] = set()
        duplicate_count = 0
        missing_time_count = 0
        outside_count = 0
        for raw in raw_records:
            try:
                parsed = _parse_record(raw)
            except NormalizedDataError as exc:
                if "published_at" in str(exc):
                    missing_time_count += 1
                else:
                    warnings.append(str(exc))
                continue
            identity = (parsed.jd_id, parsed.content_hash)
            if identity in seen:
                duplicate_count += 1
                continue
            seen.add(identity)
            if time_range:
                published = parsed.published_at.date()
                if published < time_range[0] or published > time_range[1]:
                    outside_count += 1
                    continue
            records.append(parsed)

        if not files:
            warnings.append(
                f"未找到 2.2 标准化数据：{self.path}；请配置 DISCOVERY_NORMALIZED_PATH。"
            )
        if files and not records:
            warnings.append("没有可用于时序发现的有效 normalized_records。")
        quality = DiscoveryDataQuality(
            input_files=[str(path) for path in files],
            total_records=len(raw_records),
            valid_records=len(records),
            duplicate_records=duplicate_count,
            excluded_missing_published_at=missing_time_count,
            excluded_outside_time_range=outside_count,
            warnings=warnings[:100],
        )
        return NormalizedLoadResult(records=records, quality=quality)

    def _files(self) -> list[Path]:
        if self.path.is_file():
            return [self.path] if self.path.suffix.lower() in {".json", ".jsonl"} else []
        if not self.path.exists():
            return []
        return sorted(
            path
            for path in self.path.rglob("*")
            if path.is_file() and path.suffix.lower() in {".json", ".jsonl"}
        )


def _read_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        records = []
        with path.open("r", encoding="utf-8-sig") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise NormalizedDataError(f"第 {line_number} 行不是 JSON 对象")
                records.append(value)
        return records

    with path.open("r", encoding="utf-8-sig") as stream:
        value = json.load(stream)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        nested = value.get("normalized_records")
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
        # graph_import_batch.json 不属于 B 层，避免误当逐 JD 数据。
        if "nodes" in value and "relationships" in value:
            return []
        return [value]
    raise NormalizedDataError("JSON 顶层必须是对象或对象数组")


def _parse_record(raw: dict[str, Any]) -> NormalizedJobRecord:
    document_type = str(raw.get("document_type") or "job_description")
    if document_type != "job_description":
        raise NormalizedDataError("非 job_description 记录已排除")
    jd_id = _required(raw, "jd_id")
    source_id = str(raw.get("source_id") or f"source:{jd_id}")
    published_at = _datetime(raw.get("published_at"), f"{jd_id}: published_at")
    job = raw.get("job")
    if not isinstance(job, dict):
        raise NormalizedDataError(f"{jd_id}: job 必须是对象")
    job_id = str(job.get("canonical_id") or "").strip()
    raw_name = str(job.get("raw_name") or raw.get("job_title_raw") or "").strip()
    canonical_name = str(job.get("canonical_name") or raw_name).strip()
    if not raw_name or not canonical_name:
        raise NormalizedDataError(f"{jd_id}: 缺少岗位名称")

    skills = tuple(
        parsed
        for item in _list(raw.get("skills"))
        if (parsed := _parse_skill(item, source_id)) is not None
    )
    if not skills:
        raise NormalizedDataError(f"{jd_id}: 没有标准技能，无法参与新岗位发现")
    company = _name(raw.get("company")) or "未标注公司"
    industries = tuple(filter(None, (_name(item) for item in _list(raw.get("industries")))))
    responsibilities = _responsibilities(raw, job)
    confidence = _ratio(
        job.get("alignment_confidence", raw.get("alignment_confidence", 1.0)), 1.0
    )
    source_channel = str(raw.get("source_platform") or jd_id.split(":", 1)[0]).strip()
    return NormalizedJobRecord(
        jd_id=jd_id,
        source_id=source_id,
        source_channel=source_channel,
        published_at=published_at,
        content_hash=str(raw.get("content_hash") or "") or None,
        job_id=job_id,
        raw_name=raw_name,
        canonical_name=canonical_name,
        description=str(job.get("description") or raw.get("raw_text") or "").strip(),
        responsibilities=responsibilities,
        is_new_candidate=bool(job.get("is_new_candidate", False)),
        company=company,
        industries=industries,
        skills=skills,
        confidence=confidence,
    )


def _parse_skill(value: Any, source_id: str) -> NormalizedSkill | None:
    if not isinstance(value, dict):
        return None
    skill_id = str(value.get("canonical_id") or "").strip()
    name = str(value.get("canonical_name") or value.get("raw_name") or "").strip()
    if not skill_id or len(skill_id) > 160 or not name:
        return None
    requirement_type = str(value.get("requirement_type") or "mentioned").lower()
    if requirement_type not in {"required", "preferred", "mentioned"}:
        requirement_type = "mentioned"
    evidence = tuple(str(item) for item in _list(value.get("evidence")) if str(item).strip())
    aliases = tuple(str(item) for item in _list(value.get("aliases")) if str(item).strip())
    min_years = value.get("min_years")
    try:
        parsed_years = float(min_years) if min_years is not None else None
    except (TypeError, ValueError):
        parsed_years = None
    return NormalizedSkill(
        id=skill_id,
        name=name,
        raw_name=str(value.get("raw_name") or name),
        requirement_type=requirement_type,
        proficiency=str(value.get("proficiency") or "").strip() or None,
        min_years=parsed_years,
        confidence=_ratio(value.get("confidence"), 1.0),
        evidence=evidence or (source_id,),
        aliases=aliases,
    )


def _responsibilities(raw: dict[str, Any], job: dict[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for candidate in (job.get("core_responsibilities"), raw.get("responsibilities")):
        if isinstance(candidate, str):
            values.extend(_split_text(candidate))
        else:
            values.extend(str(item).strip() for item in _list(candidate) if str(item).strip())
    if not values and job.get("description"):
        values.extend(_split_text(str(job["description"])))
    return tuple(dict.fromkeys(value[:500] for value in values if value))


def _split_text(value: str) -> list[str]:
    normalized = value.replace("；", "\n").replace("。", "\n").replace(";", "\n")
    return [item.strip(" -\t") for item in normalized.splitlines() if item.strip(" -\t")]


def _required(value: dict[str, Any], key: str) -> str:
    parsed = str(value.get(key) or "").strip()
    if not parsed:
        raise NormalizedDataError(f"缺少必填字段 {key}")
    return parsed


def _datetime(value: Any, field: str) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise NormalizedDataError(f"{field} 必须带时区")
        return value
    if not value:
        raise NormalizedDataError(f"{field} 缺失")
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise NormalizedDataError(f"{field} 不是 ISO-8601 时间") from exc
    if parsed.tzinfo is None:
        raise NormalizedDataError(f"{field} 必须带时区")
    return parsed


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("canonical_name") or "").strip()
    return str(value or "").strip()


def _ratio(value: Any, default: float) -> float:
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return default
