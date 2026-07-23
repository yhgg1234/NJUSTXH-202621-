"""图谱领域模型及跨子任务数据契约。"""

from datetime import datetime
from enum import Enum
import re
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


GraphId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
GraphName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
PropertyValue = str | int | float | bool | datetime | list[str] | list[int] | list[float] | list[bool]
RESERVED_NODE_PROPERTIES = {
    "id", "name", "aliases", "confidence", "source_ids", "observed_at",
    "valid_from", "valid_to", "created_at", "updated_at", "last_batch_id",
}
RESERVED_RELATIONSHIP_PROPERTIES = {
    "id", "confidence", "evidence_ids", "observed_at", "valid_from", "valid_to",
    "created_at", "updated_at", "last_batch_id",
}
_PERIOD_KEY_PATTERN = re.compile(r"^(?P<year>\d{4})(?:(?P<quarter>Q[1-4])|-(?P<month>0[1-9]|1[0-2]))$")
_SKILL_RELATIONSHIP_TYPES = {"REQUIRES_SKILL", "BONUS_SKILL"}


class NodeType(str, Enum):
    JOB = "Job"
    SKILL = "Skill"
    TECH_STACK = "TechStack"
    INDUSTRY = "Industry"
    CERTIFICATE = "Certificate"
    EDUCATION = "Education"
    PROJECT = "Project"
    COMPANY = "Company"
    SOURCE = "Source"


class RelationshipType(str, Enum):
    REQUIRES_SKILL = "REQUIRES_SKILL"
    BONUS_SKILL = "BONUS_SKILL"
    BELONGS_TO_STACK = "BELONGS_TO_STACK"
    APPLIES_TO_INDUSTRY = "APPLIES_TO_INDUSTRY"
    REQUIRES_CERTIFICATE = "REQUIRES_CERTIFICATE"
    REQUIRES_EDUCATION = "REQUIRES_EDUCATION"
    RELATED_PROJECT = "RELATED_PROJECT"
    PUBLISHED_BY = "PUBLISHED_BY"
    PREREQUISITE_OF = "PREREQUISITE_OF"
    DERIVED_FROM = "DERIVED_FROM"
    EVOLVES_TO = "EVOLVES_TO"


class GraphNode(BaseModel):
    """2.2 输出、2.3 入库使用的标准节点。"""

    model_config = ConfigDict(extra="forbid")

    id: GraphId
    type: NodeType
    name: GraphName
    aliases: list[str] = Field(default_factory=list)
    properties: dict[str, PropertyValue] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0, le=1)
    source_ids: list[str] = Field(default_factory=list)
    observed_at: datetime | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None

    @model_validator(mode="after")
    def validate_validity_window(self) -> "GraphNode":
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValueError("valid_from must not be later than valid_to")
        reserved = RESERVED_NODE_PROPERTIES.intersection(self.properties)
        if reserved:
            raise ValueError(f"properties contains reserved keys: {', '.join(sorted(reserved))}")
        return self


class GraphRelationship(BaseModel):
    """标准关系；id 用于幂等导入和后续变更追踪。"""

    model_config = ConfigDict(extra="forbid")

    id: GraphId
    type: RelationshipType
    from_id: GraphId
    to_id: GraphId
    properties: dict[str, PropertyValue] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)
    observed_at: datetime | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None

    @model_validator(mode="after")
    def validate_relationship(self) -> "GraphRelationship":
        if self.from_id == self.to_id:
            raise ValueError("from_id and to_id must be different")
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValueError("valid_from must not be later than valid_to")
        reserved = RESERVED_RELATIONSHIP_PROPERTIES.intersection(self.properties)
        if reserved:
            raise ValueError(f"properties contains reserved keys: {', '.join(sorted(reserved))}")
        self._validate_skill_snapshot()
        return self

    def _validate_skill_snapshot(self) -> None:
        """校验 3.1 使用的周期快照，静态 2.3 关系仍可不带周期字段导入。"""

        if self.type.value not in _SKILL_RELATIONSHIP_TYPES:
            return
        temporal_keys = {"period_key", "period_start", "period_end", "skill_jd_count", "job_jd_count", "demand_ratio"}
        supplied = temporal_keys.intersection(self.properties)
        if not supplied:
            return
        required = {"period_key", "period_start", "skill_jd_count", "job_jd_count", "demand_ratio"}
        missing = required - set(self.properties)
        if missing:
            raise ValueError(
                "periodic skill relationship is missing required properties: "
                + ", ".join(sorted(missing))
            )
        if not self.evidence_ids:
            raise ValueError("periodic skill relationship requires at least one evidence_id")

        period_key = str(self.properties["period_key"])
        match = _PERIOD_KEY_PATTERN.fullmatch(period_key)
        if not match:
            raise ValueError("period_key must use YYYY-MM or YYYYQ1 through YYYYQ4")
        period_start = _parse_iso_datetime(self.properties["period_start"], "period_start")
        if "period_end" in self.properties:
            period_end = _parse_iso_datetime(self.properties["period_end"], "period_end")
            if period_end <= period_start:
                raise ValueError("period_end must be later than period_start")
        expected_month = int(match.group("month") or ((int(match.group("quarter")[-1]) - 1) * 3 + 1))
        if period_start.year != int(match.group("year")) or period_start.month != expected_month:
            raise ValueError("period_start must match the start of period_key")

        skill_jd_count = _non_negative_int(self.properties["skill_jd_count"], "skill_jd_count")
        job_jd_count = _non_negative_int(self.properties["job_jd_count"], "job_jd_count")
        if skill_jd_count > job_jd_count:
            raise ValueError("skill_jd_count must not exceed job_jd_count")
        demand_ratio = _ratio(self.properties["demand_ratio"], "demand_ratio")
        if job_jd_count and abs(demand_ratio - skill_jd_count / job_jd_count) > 0.001:
            raise ValueError("demand_ratio must equal skill_jd_count / job_jd_count within 0.001")


def _parse_iso_datetime(value: Any, field_name: str) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an ISO-8601 datetime") from exc
    raise ValueError(f"{field_name} must be an ISO-8601 datetime")


def _non_negative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a non-negative integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a non-negative integer") from exc
    if parsed < 0 or parsed != value:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return parsed


def _ratio(value: Any, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number between 0 and 1")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number between 0 and 1") from exc
    if not 0 <= parsed <= 1:
        raise ValueError(f"{field_name} must be a number between 0 and 1")
    return parsed


class GraphImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: GraphId
    producer: str = Field(default="task-2.2", min_length=1, max_length=100)
    nodes: list[GraphNode] = Field(default_factory=list, max_length=5000)
    relationships: list[GraphRelationship] = Field(default_factory=list, max_length=10000)

    @model_validator(mode="after")
    def validate_batch(self) -> "GraphImportRequest":
        if not self.nodes and not self.relationships:
            raise ValueError("nodes and relationships cannot both be empty")
        node_ids = [node.id for node in self.nodes]
        relationship_ids = [rel.id for rel in self.relationships]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("node ids must be unique within a batch")
        if len(relationship_ids) != len(set(relationship_ids)):
            raise ValueError("relationship ids must be unique within a batch")
        return self


class GraphImportResult(BaseModel):
    batch_id: str
    nodes_upserted: int
    relationships_upserted: int


class SubgraphResponse(BaseModel):
    nodes: list[dict[str, Any]]
    links: list[dict[str, Any]]
    truncated: bool = False
