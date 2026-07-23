"""岗位管理 —— 岗位定义、检索、新岗位发现、演化分析 的领域模型。"""

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, model_validator


# ── 岗位定义 ──

class JobSkill(BaseModel):
    """岗位技能要求"""
    name: str
    required: bool = True
    proficiency: str | None = None
    years: int | None = None


class JobCreate(BaseModel):
    """创建/定义新岗位"""
    title: str = Field(min_length=1, max_length=200, examples=["AI Agent开发工程师"])
    description: str = Field(min_length=1)
    skills: list[JobSkill] = Field(default_factory=list)
    education_required: str | None = None
    experience_years: tuple[int, int] | None = None
    industries: list[str] = Field(default_factory=list)
    tech_stacks: list[str] = Field(default_factory=list)
    certificates: list[str] = Field(default_factory=list)
    source: str = Field(default="manual", pattern=r"^(manual|auto_discovered)$")


class JobUpdate(BaseModel):
    """更新已有岗位"""
    title: str | None = None
    description: str | None = None
    skills: list[JobSkill] | None = None
    education_required: str | None = None
    experience_years: tuple[int, int] | None = None
    industries: list[str] | None = None
    tech_stacks: list[str] | None = None
    certificates: list[str] | None = None


class JobResponse(BaseModel):
    """岗位详情"""
    id: str
    title: str
    description: str
    skills: list[JobSkill]
    education_required: str | None = None
    experience_years: tuple[int, int] | None = None
    industries: list[str]
    tech_stacks: list[str]
    certificates: list[str]
    source: str
    created_at: str = ""
    updated_at: str = ""
    is_active: bool = True


class JobListResponse(BaseModel):
    """岗位分页列表"""
    items: list[JobResponse]
    total: int
    page: int
    page_size: int


# ── 岗位检索 ──

class JobSearchQuery(BaseModel):
    """岗位检索条件"""
    keyword: str | None = None
    skills: list[str] | None = None
    tech_stacks: list[str] | None = None
    industries: list[str] | None = None
    education: str | None = None
    sort_by: str = "updated_at"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


# ── 新岗位发现 ──

class NewJobDiscoveryRequest(BaseModel):
    """新岗位发现请求"""
    time_range: tuple[str, str]
    novelty_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    min_frequency: int = Field(default=5, ge=1)


class DiscoveredJob(BaseModel):
    """发现的新岗位"""
    suggested_title: str
    confidence: float = Field(ge=0.0, le=1.0)
    sample_descriptions: list[str] = Field(default_factory=list)
    key_skills: list[str] = Field(default_factory=list)
    similar_existing_jobs: list[str] = Field(default_factory=list)
    novelty_score: float = Field(ge=0.0, le=1.0)


class NewJobDiscoveryResponse(BaseModel):
    """新岗位发现结果"""
    discovered: list[DiscoveredJob]
    analyzed_jd_count: int
    time_range: tuple[str, str]


# ── 岗位演化 ──

class TimeGranularity(str, Enum):
    """3.1 支持的时间切片粒度。"""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class SkillChangeType(str, Enum):
    """相邻时间切片之间的能力变化类型。"""

    ADDED = "added"
    REMOVED = "removed"
    INCREASED = "increased"
    DECREASED = "decreased"


class JobEvolutionQuery(BaseModel):
    """岗位演化查询"""

    job_id: str
    granularity: TimeGranularity = TimeGranularity.QUARTERLY
    time_range: tuple[date, date] | None = None
    top_n: int = Field(default=10, ge=1, le=30)
    change_threshold: float = Field(default=0.05, ge=0.0, le=1.0)
    prediction_horizon_months: int = Field(default=6, ge=1, le=12)

    @model_validator(mode="after")
    def validate_time_range(self) -> "JobEvolutionQuery":
        if self.time_range and self.time_range[0] > self.time_range[1]:
            raise ValueError("time_range start must not be later than end")
        return self


class SkillMetric(BaseModel):
    """一个岗位技能在一个时间切片中的聚合指标。"""

    skill_id: str
    skill_name: str
    required: bool = True
    skill_jd_count: int = Field(default=0, ge=0)
    job_jd_count: int = Field(default=0, ge=0)
    demand_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    importance: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)


class SkillChange(BaseModel):
    """技能变化项"""

    skill_id: str
    skill_name: str
    change_type: SkillChangeType
    previous_demand_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    current_demand_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    delta: float = 0.0
    evidence_ids: list[str] = Field(default_factory=list)


class SkillTrend(BaseModel):
    """跨时间范围的技能趋势摘要。"""

    skill_id: str
    skill_name: str
    first_demand_ratio: float = Field(ge=0.0, le=1.0)
    latest_demand_ratio: float = Field(ge=0.0, le=1.0)
    delta: float


class EvolutionPrediction(BaseModel):
    """基于历史切片的轻量趋势外推结果。"""

    available: bool
    model: str | None = None
    horizon_months: int = Field(default=6, ge=1, le=12)
    reason: str | None = None
    rising_skills: list[str] = Field(default_factory=list)


class EvolutionDataQuality(BaseModel):
    """向前端暴露样本覆盖与数据限制，避免把低质量数据解释为趋势。"""

    period_count: int = Field(ge=0)
    total_jd_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class JobEvolutionPoint(BaseModel):
    """单个时间点的岗位快照"""

    period: str
    period_start: date | None = None
    skill_set: list[SkillMetric] = Field(default_factory=list)
    jd_count: int = 0
    changes_from_previous: list[SkillChange] = Field(default_factory=list)


class JobEvolutionResponse(BaseModel):
    """岗位演化分析结果"""

    job_id: str
    job_title: str
    timeline: list[JobEvolutionPoint]
    hot_trends: list[SkillTrend] = Field(default_factory=list)
    cold_trends: list[SkillTrend] = Field(default_factory=list)
    prediction: EvolutionPrediction
    data_quality: EvolutionDataQuality
