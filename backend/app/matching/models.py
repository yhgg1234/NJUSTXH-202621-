"""人岗匹配 —— 匹配请求、匹配报告、差距分析、学习路径 的领域模型"""

from pydantic import BaseModel, Field


# ── 匹配请求 ──

class MatchRequest(BaseModel):
    """单岗位匹配请求"""
    resume_id: str
    job_id: str


class MultiMatchRequest(BaseModel):
    """多岗位对比匹配请求"""
    resume_id: str
    job_ids: list[str] = Field(min_length=2)


# ── 维度得分 ──

class DimensionScore(BaseModel):
    """单个维度的匹配得分"""
    dimension: str
    score: float = Field(ge=0.0, le=100.0)
    weight: float = Field(ge=0.0, le=1.0)
    matched_items: list[str] = Field(default_factory=list)
    missing_items: list[str] = Field(default_factory=list)
    surplus_items: list[str] = Field(default_factory=list)


# ── 匹配报告 ──

class MatchReport(BaseModel):
    """人岗匹配报告"""
    match_id: str
    resume_id: str
    job_id: str
    job_title: str
    total_score: float = Field(ge=0.0, le=100.0)
    skill_score: float = Field(ge=0.0, le=100.0)
    experience_score: float = Field(ge=0.0, le=100.0)
    education_score: float = Field(ge=0.0, le=100.0)
    industry_score: float = Field(ge=0.0, le=100.0)
    dimensions: list[DimensionScore] = Field(default_factory=list)
    overall_assessment: str = ""
    matched_at: str = ""


# ── 差距分析 ──

class GapAnalysisRequest(BaseModel):
    """差距分析请求"""
    resume_id: str
    job_id: str


class SkillGap(BaseModel):
    """技能差距项"""
    skill_name: str
    status: str
    importance: str = "required"
    current_level: str | None = None
    required_level: str | None = None


class GapAnalysisReport(BaseModel):
    """差距分析报告"""
    resume_id: str
    job_id: str
    job_title: str
    skill_gaps: list[SkillGap]
    total_missing: int = 0
    total_matched: int = 0
    total_surplus: int = 0


# ── 学习路径 ──

class LearningPathRequest(BaseModel):
    """学习路径生成请求"""
    resume_id: str
    job_id: str
    target_months: int = Field(default=6, ge=1, le=24)


class LearningPhase(BaseModel):
    """学习阶段"""
    phase: int
    title: str
    duration_weeks: int
    topics: list[str] = Field(default_factory=list)
    courses: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    certificates: list[str] = Field(default_factory=list)
    milestones: list[str] = Field(default_factory=list)


class LearningPathResponse(BaseModel):
    """学习路径规划"""
    resume_id: str
    job_id: str
    job_title: str
    total_months: int
    phases: list[LearningPhase]
    overall_suggestions: list[str] = Field(default_factory=list)


# ── 岗位对比 ──

class JobCompareItem(BaseModel):
    """岗位对比条目"""
    job_id: str
    job_title: str
    match_score: float
    advantages: list[str] = Field(default_factory=list)
    disadvantages: list[str] = Field(default_factory=list)


class JobCompareResponse(BaseModel):
    """多岗位对比结果"""
    resume_id: str
    comparisons: list[JobCompareItem]
    best_match_job_id: str
    recommendation: str = ""
