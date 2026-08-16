"""仪表盘 —— 统计概览、趋势数据、热门排行 的领域模型"""

from typing import Any

from pydantic import BaseModel, Field


class OverviewStats(BaseModel):
    """系统统计概览"""
    total_jobs: int = 0
    total_resumes: int = 0
    total_graph_entities: int = 0
    total_graph_relations: int = 0
    total_matches: int = 0
    total_data_sources: int = 0
    entities_by_type: dict[str, int] = Field(default_factory=dict)
    jobs_by_industry: dict[str, int] = Field(default_factory=dict)


class TrendQuery(BaseModel):
    """趋势数据查询"""
    time_range: str = Field(default="6m", pattern=r"^\d+[my]$")
    granularity: str = Field(default="monthly", pattern=r"^(monthly|quarterly)$")


class TrendPoint(BaseModel):
    """单个趋势数据点"""
    period: str
    value: float
    label: str = ""


class TrendSeries(BaseModel):
    """一条趋势线"""
    name: str
    data: list[TrendPoint]


class TrendResponse(BaseModel):
    """趋势数据响应"""
    series: list[TrendSeries]
    time_range: str
    granularity: str


class HotItem(BaseModel):
    """热门条目"""
    name: str
    count: int
    trend: str = "stable"
    rank: int = 0


class HotRankings(BaseModel):
    """热门排行"""
    top_skills: list[HotItem] = Field(default_factory=list)
    top_tech_stacks: list[HotItem] = Field(default_factory=list)
    top_industries: list[HotItem] = Field(default_factory=list)
    emerging_skills: list[str] = Field(default_factory=list)
    declining_skills: list[str] = Field(default_factory=list)
