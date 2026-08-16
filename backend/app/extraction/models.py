"""信息抽取 —— NER、关系抽取、实体对齐、本体定义 的领域模型"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── 枚举 ──

class EntityType(str, Enum):
    POSITION = "position"
    SKILL = "skill"
    CERTIFICATE = "certificate"
    INDUSTRY = "industry"
    TECH_STACK = "tech_stack"
    EDUCATION = "education"
    COMPANY = "company"


class RelationType(str, Enum):
    REQUIRES = "requires"
    PREFERS = "prefers"
    PREREQUISITE = "prerequisite"
    SAME_AS = "same_as"
    RELATED_TO = "related_to"
    BELONGS_TO = "belongs_to"
    EVOLVED_FROM = "evolved_from"
    APPLIES_TO = "applies_to"


# ── 实体抽取 ──

class EntityExtractionRequest(BaseModel):
    """实体抽取请求"""
    text: str = Field(min_length=1, description="待抽取的文本（JD/行业报告等）")
    entity_types: list[EntityType] | None = None
    use_rag: bool = True


class ExtractedEntity(BaseModel):
    """抽取出的实体"""
    name: str
    type: EntityType
    aliases: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    context: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class EntityExtractionResponse(BaseModel):
    """实体抽取结果"""
    text_id: str | None = None
    entities: list[ExtractedEntity]
    model_used: str = ""
    processing_time_ms: float = 0.0


# ── 关系抽取 ──

class RelationExtractionRequest(BaseModel):
    """关系抽取请求"""
    text: str = Field(min_length=1)
    entities: list[ExtractedEntity] = Field(min_length=1)


class ExtractedRelation(BaseModel):
    """抽取出的关系"""
    head_entity: str
    tail_entity: str
    relation: RelationType
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str | None = None


class RelationExtractionResponse(BaseModel):
    """关系抽取结果"""
    text_id: str | None = None
    relations: list[ExtractedRelation]
    model_used: str = ""
    processing_time_ms: float = 0.0


# ── 实体对齐 ──

class EntityAlignRequest(BaseModel):
    """实体对齐请求"""
    entities: list[ExtractedEntity] = Field(min_length=1)
    method: str = Field(default="bert_semantic", pattern=r"^(bert_semantic|rule_based|hybrid)$")


class EntityAlignResult(BaseModel):
    """对齐结果"""
    entity_name: str
    canonical_name: str
    matched_ontology_id: str | None = None
    is_new: bool = False
    confidence: float = Field(ge=0.0, le=1.0)


class EntityAlignResponse(BaseModel):
    """实体对齐结果"""
    results: list[EntityAlignResult]
    total_aligned: int
    new_entities: int
    conflicts: int = 0


# ── 本体定义 ──

class OntologyEntity(BaseModel):
    """本体实体定义"""
    id: str
    name: str
    type: EntityType
    definition: str
    aliases: list[str] = Field(default_factory=list)
    parent_id: str | None = None


class OntologyRelation(BaseModel):
    """本体关系定义"""
    from_type: EntityType
    to_type: EntityType
    relation: RelationType
    description: str = ""


class OntologySchema(BaseModel):
    """本体 Schema 定义"""
    version: str
    entities: list[OntologyEntity]
    relations: list[OntologyRelation]
