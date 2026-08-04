"""子任务 2.4 的领域模型与对外数据契约。"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now() -> datetime:
    """生成带时区时间，满足跨模块 ISO-8601 契约。"""

    return datetime.now(timezone.utc)


class CandidateStatus(str, Enum):
    PENDING = "pending"
    ADOPTED = "adopted"
    REJECTED = "rejected"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class EvidenceType(str, Enum):
    COMMUNITY_CLUSTER = "community_cluster"
    SKILL_NOVELTY = "skill_novelty"
    JD_FREQUENCY_SURGE = "jd_frequency_surge"
    MULTI_SOURCE_SUPPORT = "multi_source_support"


class Evidence(BaseModel):
    type: EvidenceType
    description: str
    confidence: float = Field(ge=0, le=1)
    supporting_ids: list[str] = Field(default_factory=list)


class CandidateSkill(BaseModel):
    """候选岗位中的标准技能及可解释统计。"""

    id: str
    name: str
    required: bool
    importance: float = Field(ge=0, le=1)
    support_count: int = Field(ge=0)
    support_ratio: float = Field(ge=0, le=1)
    latest_period_count: int = Field(default=0, ge=0)
    proficiency: str | None = None
    years: float | None = Field(default=None, ge=0)
    aliases: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class NewJobCandidate(BaseModel):
    """经算法发现、等待人工确认的新岗位完整定义。"""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    name: str
    standardized_id: str
    description: str
    core_responsibilities: list[str] = Field(default_factory=list)
    required_skills: list[CandidateSkill] = Field(default_factory=list)
    bonus_skills: list[CandidateSkill] = Field(default_factory=list)
    industry_scenarios: list[str] = Field(default_factory=list)
    derived_from: list[str] = Field(default_factory=list)
    estimated_emergence: str
    latest_period: str
    emergence_confidence: float = Field(ge=0, le=1)
    novelty_score: float = Field(ge=0, le=1)
    trend_score: float = Field(ge=0, le=1)
    closest_existing_job_id: str | None = None
    closest_existing_job_name: str | None = None
    closest_similarity: float = Field(default=0, ge=0, le=1)
    supporting_jd_count: int = Field(ge=0)
    latest_period_jd_count: int = Field(ge=0)
    company_count: int = Field(ge=0)
    source_count: int = Field(ge=0)
    period_counts: dict[str, int] = Field(default_factory=dict)
    source_ids: list[str] = Field(default_factory=list)
    evidence_chain: list[Evidence] = Field(default_factory=list)
    algorithm: str = "skill-community-novelty-v1"
    status: CandidateStatus = CandidateStatus.PENDING
    reviewer: str | None = None
    review_comment: str | None = None
    reviewed_at: datetime | None = None
    discovered_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @property
    def emerging_skills(self) -> list[str]:
        """兼容旧调用方；前端应优先使用结构化技能。"""

        return [skill.name for skill in self.required_skills + self.bonus_skills]


class DiscoverRequest(BaseModel):
    """触发新岗位发现；兼容项目 README 中冻结的三个核心参数。"""

    time_range: tuple[date, date] | None = None
    novelty_threshold: float = Field(default=0.3, ge=0, le=1)
    min_frequency: int = Field(default=5, ge=1)
    min_companies: int = Field(default=2, ge=1)
    min_sources: int = Field(default=2, ge=1)
    cluster_similarity_threshold: float = Field(default=0.55, ge=0, le=1)
    min_confidence: float = Field(default=0.5, ge=0, le=1)
    max_candidates: int = Field(default=20, ge=1, le=100)
    granularity: str = Field(default="quarterly", pattern="^(monthly|quarterly)$")

    @model_validator(mode="after")
    def validate_time_range(self) -> "DiscoverRequest":
        if self.time_range and self.time_range[0] > self.time_range[1]:
            raise ValueError("time_range start must not be later than end")
        return self


class DiscoveryDataQuality(BaseModel):
    input_files: list[str] = Field(default_factory=list)
    total_records: int = Field(ge=0)
    valid_records: int = Field(ge=0)
    duplicate_records: int = Field(ge=0)
    excluded_missing_published_at: int = Field(ge=0)
    excluded_outside_time_range: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class DiscoverResponse(BaseModel):
    candidates: list[NewJobCandidate]
    total_scanned_jobs: int
    total_scanned_skills: int
    total_scanned_records: int
    algorithm: str = "skill-community-novelty-v1"
    data_quality: DiscoveryDataQuality
    generated_at: datetime = Field(default_factory=utc_now)


class CandidateEditRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=4000)
    core_responsibilities: list[str] | None = None
    required_skills: list[CandidateSkill] | None = None
    bonus_skills: list[CandidateSkill] | None = None
    industry_scenarios: list[str] | None = None
    reviewer: str = Field(min_length=1, max_length=100)
    review_comment: str | None = Field(default=None, max_length=1000)


class CandidateReviewRequest(BaseModel):
    reviewer: str = Field(default="system-user", min_length=1, max_length=100)
    comment: str | None = Field(default=None, max_length=1000)
    create_graph_nodes: bool = True


class BatchAdoptRequest(BaseModel):
    candidate_ids: list[str] = Field(min_length=1, max_length=50)
    create_graph_nodes: bool = True
    reviewer: str = Field(default="system-user", min_length=1, max_length=100)
    comment: str | None = Field(default=None, max_length=1000)


class BatchRejectRequest(BaseModel):
    candidate_ids: list[str] = Field(min_length=1, max_length=50)
    reviewer: str = Field(default="system-user", min_length=1, max_length=100)
    comment: str | None = Field(default=None, max_length=1000)


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


class AbilityChangeType(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    INCREASED = "increased"
    DECREASED = "decreased"
    RENAMED = "renamed"
    MERGED = "merged"
    SPLIT = "split"


class AbilityChange(BaseModel):
    change_id: str
    job_id: str
    from_period: str
    to_period: str
    change_type: AbilityChangeType
    entity_id: str
    entity_name: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    delta: float
    algorithm: str = "adjacent-period-diff-v1"
    evidence_ids: list[str] = Field(default_factory=list)
    review_status: ReviewStatus = ReviewStatus.PENDING
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_comment: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class AbilityChangeAnalyzeRequest(BaseModel):
    job_id: str
    from_period: str
    to_period: str
    granularity: str = Field(default="quarterly", pattern="^(monthly|quarterly)$")
    change_threshold: float = Field(default=0.05, ge=0, le=1)

    @model_validator(mode="after")
    def validate_periods(self) -> "AbilityChangeAnalyzeRequest":
        pattern = r"^\d{4}-(0[1-9]|1[0-2])$" if self.granularity == "monthly" else r"^\d{4}Q[1-4]$"
        if not re.fullmatch(pattern, self.from_period) or not re.fullmatch(pattern, self.to_period):
            raise ValueError("period must match granularity (YYYY-MM or YYYYQ1 through YYYYQ4)")
        if _period_order(self.from_period, self.granularity) >= _period_order(
            self.to_period, self.granularity
        ):
            raise ValueError("from_period must be earlier than to_period")
        return self


class AbilityChangeResponse(BaseModel):
    job_id: str
    from_period: str
    to_period: str
    changes: list[AbilityChange]
    warnings: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)


class ChangeReviewRequest(BaseModel):
    status: ReviewStatus
    reviewer: str = Field(min_length=1, max_length=100)
    comment: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def reject_pending_review(self) -> "ChangeReviewRequest":
        if self.status == ReviewStatus.PENDING:
            raise ValueError("review status must be approved or rejected")
        return self


class ExpectedAbilityChange(BaseModel):
    job_id: str
    from_period: str
    to_period: str
    entity_id: str
    change_type: AbilityChangeType


class DiscoveryEvaluationRequest(BaseModel):
    """人工金标准，用于量化新岗位发现和能力更新效果。"""

    expected_new_job_ids: list[str] = Field(default_factory=list)
    expected_ability_changes: list[ExpectedAbilityChange] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_gold_labels(self) -> "DiscoveryEvaluationRequest":
        if not self.expected_new_job_ids and not self.expected_ability_changes:
            raise ValueError("至少提供一种人工金标准")
        return self


class EvaluationMetric(BaseModel):
    true_positive: int = Field(ge=0)
    false_positive: int = Field(ge=0)
    false_negative: int = Field(ge=0)
    precision: float = Field(ge=0, le=1)
    recall: float = Field(ge=0, le=1)
    f1: float = Field(ge=0, le=1)
    meets_80_percent: bool


class DiscoveryEvaluationResponse(BaseModel):
    new_job_discovery: EvaluationMetric | None = None
    ability_changes: EvaluationMetric | None = None
    evaluated_at: datetime = Field(default_factory=utc_now)


def _period_order(value: str, granularity: str) -> int:
    if granularity == "monthly":
        year, month = (int(item) for item in value.split("-", 1))
        return year * 12 + month - 1
    return int(value[:4]) * 4 + int(value[-1]) - 1
