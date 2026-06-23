"""图谱领域模型及跨子任务数据契约。"""

from datetime import datetime
from enum import Enum
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
        return self


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
