"""数据清洗 —— 清洗管线、去重、质量检查、数据集 的领域模型"""

from typing import Literal

from pydantic import BaseModel, Field

from app.data_collection.models import TaskStatus


# ── 清洗管线 ──

class PipelineConfig(BaseModel):
    """清洗管线配置"""
    dedup_method: Literal["simhash", "minhash"] = "simhash"
    dedup_threshold: float = Field(default=0.9, ge=0.0, le=1.0)
    remove_noise: bool = True
    normalize: bool = True
    human_review: bool = False


class CleaningTaskCreate(BaseModel):
    """创建清洗任务"""
    raw_data_ids: list[str] = Field(min_length=1)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)


class CleaningTaskResponse(BaseModel):
    """清洗任务状态"""
    id: str
    input_count: int
    output_count: int = 0
    dedup_removed: int = 0
    noise_removed: int = 0
    status: TaskStatus = TaskStatus.PENDING


# ── 质量检查 ──

class QualityCheckItem(BaseModel):
    """待人工校验的数据项"""
    id: str
    original_text: str
    cleaned_text: str
    issues: list[str] = Field(default_factory=list)


class QualityReviewAction(BaseModel):
    """人工标注动作"""
    item_id: str
    action: Literal["approve", "reject", "edit"]
    edited_text: str | None = None
    comment: str = ""


# ── 数据集 ──

class DatasetQuery(BaseModel):
    """清洗后数据集查询"""
    keyword: str | None = None
    has_skills: list[str] | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class DatasetItem(BaseModel):
    """清洗后的数据集条目"""
    id: str
    title: str
    content: str
    source_name: str
    cleaned_at: str = ""
    quality_score: float | None = None
    tags: list[str] = Field(default_factory=list)


class DatasetListResponse(BaseModel):
    """数据集分页列表"""
    items: list[DatasetItem]
    total: int
    page: int
    page_size: int
