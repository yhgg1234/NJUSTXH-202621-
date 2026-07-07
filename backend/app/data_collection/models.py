"""数据采集 —— 数据源、采集任务、原始数据 的领域模型"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── 枚举 ──

class DataSourceType(str, Enum):
    SEARCH_ENGINE = "search_engine"
    RECRUIT_PLATFORM = "recruit_platform"
    ENTERPRISE_DB = "enterprise_db"
    INDUSTRY_REPORT = "industry_report"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ── 数据源 ──

class DataSourceCreate(BaseModel):
    """注册新数据源"""
    name: str = Field(min_length=1, max_length=200, examples=["BOSS直聘-AI岗位"])
    type: DataSourceType
    url: str | None = None
    auth_info: dict[str, Any] | None = None
    description: str = ""


class DataSourceUpdate(BaseModel):
    """更新数据源"""
    name: str | None = None
    url: str | None = None
    auth_info: dict[str, Any] | None = None
    description: str | None = None
    is_active: bool | None = None


class DataSourceResponse(BaseModel):
    """数据源信息"""
    id: str
    name: str
    type: DataSourceType
    url: str | None = None
    description: str = ""
    is_active: bool = True
    created_at: datetime | str = ""
    updated_at: datetime | str = ""


# ── 采集任务 ──

class CollectTaskCreate(BaseModel):
    """创建采集任务"""
    source_ids: list[str] = Field(min_length=1)
    keywords: list[str] = Field(min_length=1)
    max_pages: int = Field(default=10, ge=1, le=100)
    schedule: str | None = None


class CollectTaskResponse(BaseModel):
    """采集任务详情"""
    id: str
    source_ids: list[str]
    keywords: list[str]
    max_pages: int
    schedule: str | None = None
    status: TaskStatus = TaskStatus.PENDING


# ── 原始数据 ──

class RawDataQuery(BaseModel):
    """原始数据查询参数"""
    source_id: str | None = None
    keyword: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class RawDataItem(BaseModel):
    """单条原始采集数据"""
    id: str
    source_name: str
    title: str
    content: str
    url: str | None = None
    crawled_at: datetime | str = ""
    raw_metadata: dict[str, Any] | None = None


class RawDataListResponse(BaseModel):
    """原始数据分页列表"""
    items: list[RawDataItem]
    total: int
    page: int
    page_size: int
