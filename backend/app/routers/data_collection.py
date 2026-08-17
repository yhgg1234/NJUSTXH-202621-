"""数据采集 REST API —— 数据源管理、采集任务、原始数据查询"""

from __future__ import annotations

from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.data_collection.service import get_collection_service

router = APIRouter(prefix="/api/data-collection", tags=["data-collection"])


class CollectTaskCreate(BaseModel):
    source_ids: list[str] = Field(min_length=1)
    keywords: list[str] = Field(min_length=1)
    max_pages: int = Field(default=3, ge=1, le=100)


# ── 数据源管理 ──

@router.get("/sources")
def list_sources():
    """查询数据源列表"""
    return {"items": get_collection_service().list_sources()}


@router.post("/sources", status_code=status.HTTP_201_CREATED)
def create_source(payload: dict):
    """注册新数据源（演示版：仅回执，不真正落库）"""
    return {"id": payload.get("name", "source"), **payload}


@router.get("/sources/{source_id}")
def get_source(source_id: str):
    """查看数据源详情"""
    source = get_collection_service().get_source(source_id)
    if source is None:
        return JSONResponse(status_code=404, content={"detail": "数据源不存在"})
    return source


@router.put("/sources/{source_id}")
def update_source(source_id: str, payload: dict):
    """更新数据源配置（演示版：仅回执）"""
    return {"id": source_id, **payload}


@router.delete("/sources/{source_id}")
def delete_source(source_id: str):
    """删除数据源（演示版：仅回执）"""
    return {"message": "删除成功", "source_id": source_id}


# ── 采集任务 ──

@router.get("/tasks")
def list_tasks():
    """查询采集任务列表"""
    return {"tasks": get_collection_service().list_tasks()}


@router.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_task(payload: CollectTaskCreate):
    """创建采集任务（按数据源运行爬虫 + 导出）"""
    task = get_collection_service().run_task(
        payload.source_ids, payload.keywords, payload.max_pages
    )
    if task.get("status") == "failed":
        return JSONResponse(status_code=500, content={"detail": task.get("error")})
    return task


@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    """查看采集任务状态"""
    task = get_collection_service().get_task(task_id)
    if task is None:
        return JSONResponse(status_code=404, content={"detail": "任务不存在"})
    return task


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str):
    """取消采集任务（演示版：仅回执）"""
    return {"message": "已取消", "task_id": task_id}


# ── 原始数据 ──

@router.get("/raw-data")
def list_raw_data(
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """查询原始数据（分页）"""
    items, total = get_collection_service().list_raw_data(page, page_size, keyword)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/raw-data/{item_id}")
def get_raw_data(item_id: str):
    """查看原始数据详情"""
    item = get_collection_service().get_raw_data(item_id)
    if item is None:
        return JSONResponse(status_code=404, content={"detail": "数据不存在"})
    return item
