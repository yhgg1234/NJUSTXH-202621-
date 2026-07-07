"""岗位管理 —— 岗位定义、检索、新岗位发现、演化分析 的领域模型"""

from typing import Any

from pydantic import BaseModel, Field


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

class JobEvolutionQuery(BaseModel):
    """岗位演化查询"""
    job_id: str
    granularity: str = Field(default="quarterly", pattern=r"^(monthly|quarterly)$")
    time_range: tuple[str, str] | None = None


class SkillChange(BaseModel):
    """技能变化项"""
    skill_name: str
    change_type: str
    previous_weight: float | None = None
    current_weight: float | None = None
    evidence: str | None = None


class JobEvolutionPoint(BaseModel):
    """单个时间点的岗位快照"""
    period: str
    skill_set: list[dict[str, Any]] = Field(default_factory=list)
    jd_count: int = 0
    changes_from_previous: list[SkillChange] = Field(default_factory=list)


class JobEvolutionResponse(BaseModel):
    """岗位演化分析结果"""
    job_id: str
    job_title: str
    timeline: list[JobEvolutionPoint]
    hot_trends: list[dict[str, Any]] = Field(default_factory=list)
    cold_trends: list[dict[str, Any]] = Field(default_factory=list)
    prediction_6m: list[str] = Field(default_factory=list)
