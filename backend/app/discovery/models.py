"""2.4 新岗位发现 —— 领域模型。"""

from datetime import date, datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


class CandidateStatus(str, Enum):
    PENDING = "pending"
    ADOPTED = "adopted"
    REJECTED = "rejected"


class EvidenceType(str, Enum):
    SKILL_DIVERGENCE = "skill_divergence"        # 技能组合偏离现有岗位
    NEW_SKILL_EMERGENCE = "new_skill_emergence"    # 出现了全新技能
    JD_FREQUENCY_SURGE = "jd_frequency_surge"      # JD 数量突然增长
    INDUSTRY_SPREAD = "industry_spread"            # 跨行业扩散


class Evidence(BaseModel):
    type: EvidenceType
    description: str
    confidence: float = Field(ge=0, le=1)
    supporting_ids: list[str] = Field(default_factory=list)


class NewJobCandidate(BaseModel):
    candidate_id: str
    name: str
    standardized_id: str
    emerging_skills: list[str] = Field(default_factory=list)
    derived_from: list[str] = Field(default_factory=list)   # 来源现有岗位
    estimated_emergence: str = ""                            # e.g. "2024Q3"
    emergence_confidence: float = Field(ge=0, le=1)
    description: str = ""
    evidence_chain: list[Evidence] = Field(default_factory=list)
    status: CandidateStatus = CandidateStatus.PENDING
    discovered_at: datetime = Field(default_factory=datetime.utcnow)


class DiscoverRequest(BaseModel):
    """触发新岗位发现的请求。"""
    min_confidence: float = Field(default=0.5, ge=0, le=1)
    max_candidates: int = Field(default=20, ge=1, le=100)
    period_key: str | None = None  # 限定分析周期，如 "2024Q3"


class DiscoverResponse(BaseModel):
    candidates: list[NewJobCandidate]
    total_scanned_jobs: int
    total_scanned_skills: int
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class BatchAdoptRequest(BaseModel):
    candidate_ids: list[str] = Field(min_length=1, max_length=50)
    create_graph_nodes: bool = True


class BatchRejectRequest(BaseModel):
    candidate_ids: list[str] = Field(min_length=1, max_length=50)


class AdoptResult(BaseModel):
    candidate_id: str
    success: bool
    created_job_id: str | None = None
    message: str = ""


class BatchResult(BaseModel):
    results: list[AdoptResult]
    summary: str


class DiscoverStats(BaseModel):
    total_candidates: int
    adopted_count: int
    rejected_count: int
    pending_count: int
    avg_confidence: float
    by_status: dict[str, int]
