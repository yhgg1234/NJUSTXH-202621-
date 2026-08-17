"""数据清洗 REST API —— 清洗管线、去重、质量检查、数据集管理"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, File, Query, UploadFile, status
from fastapi.responses import JSONResponse

from app.data_cleaning.service import _BASE_DIR, get_cleaning_service

router = APIRouter(prefix="/api/data-cleaning", tags=["data-cleaning"])


# ── 清洗管线 ──

@router.get("/pipeline/defaults")
def get_pipeline_defaults():
    """获取默认管线配置"""
    return get_cleaning_service().get_defaults()


# ── 清洗任务 ──

@router.post("/tasks", status_code=status.HTTP_201_CREATED)
async def create_cleaning_task(file: UploadFile = File(...)):
    """上传 JD 数据文件（xlsx/csv）并执行完整清洗流水线。"""
    if not file.filename:
        return JSONResponse(status_code=400, content={"detail": "文件名为空"})

    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".xlsx", ".csv"):
        return JSONResponse(status_code=400, content={"detail": "仅支持 .xlsx 或 .csv 文件"})

    try:
        content = await file.read()
    except Exception:
        return JSONResponse(status_code=500, content={"detail": "读取文件失败"})

    tmp_dir = Path(_BASE_DIR) / "data" / "raw" / "cleaning_uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"{uuid.uuid4().hex}{suffix}"
    tmp_path.write_bytes(content)

    try:
        task = get_cleaning_service().run(str(tmp_path))
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"detail": f"清洗流水线执行失败: {exc}"})

    return task


@router.post("/tasks/from-collection", status_code=status.HTTP_201_CREATED)
def create_cleaning_task_from_collection():
    """直接使用数据采集的最近一次结果运行清洗流水线（无需手动上传文件）。"""
    try:
        task = get_cleaning_service().run_from_collection()
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"detail": f"清洗流水线执行失败: {exc}"})
    return task


@router.get("/tasks")
def list_cleaning_tasks():
    """查询清洗任务列表"""
    return {"tasks": get_cleaning_service().list_tasks()}


@router.get("/tasks/{task_id}")
def get_cleaning_task(task_id: str):
    """查看清洗任务状态"""
    task = get_cleaning_service().get_task(task_id)
    if task is None:
        return JSONResponse(status_code=404, content={"detail": "任务不存在"})
    return task


# ── 质量检查 ──

@router.get("/quality-check")
def list_quality_items():
    """获取待人工校验数据项列表"""
    return {"items": get_cleaning_service().list_quality_items()}


@router.post("/quality-review")
def submit_quality_review(payload: dict):
    """提交人工校验结果（当前为演示版，仅回执）。"""
    return {"message": "已记录校验结果", "item_id": payload.get("item_id"), "action": payload.get("action")}


# ── 数据集 ──

@router.get("/datasets")
def list_datasets(
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """查询清洗后数据集（分页）"""
    items, total = get_cleaning_service().list_records(page, page_size, keyword)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/datasets/{item_id}")
def get_dataset_item(item_id: str):
    """查看数据集条目详情"""
    items, _ = get_cleaning_service().list_records(1, 10000)
    item = next((i for i in items if i["id"] == item_id), None)
    if item is None:
        return JSONResponse(status_code=404, content={"detail": "条目不存在"})
    return item


@router.delete("/datasets/{item_id}")
def delete_dataset_item(item_id: str):
    """删除数据集条目（演示版，仅回执）。"""
    return {"message": "删除成功", "item_id": item_id}
