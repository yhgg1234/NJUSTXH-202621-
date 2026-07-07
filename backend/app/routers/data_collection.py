"""数据采集 REST API —— 数据源管理、采集任务、原始数据查询"""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/data-collection", tags=["data-collection"])

_NOT_IMPL = {"message": "接口已定义，功能待实现", "status": 501}


# ── 数据源管理 ──

@router.get("/sources")
def list_sources():
    """查询数据源列表"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.post("/sources", status_code=status.HTTP_201_CREATED)
def create_source():
    """注册新数据源"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.get("/sources/{source_id}")
def get_source(source_id: str):
    """查看数据源详情"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.put("/sources/{source_id}")
def update_source(source_id: str):
    """更新数据源配置"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.delete("/sources/{source_id}")
def delete_source(source_id: str):
    """删除数据源"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


# ── 采集任务 ──

@router.get("/tasks")
def list_tasks():
    """查询采集任务列表"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_task():
    """创建采集任务"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    """查看采集任务状态"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str):
    """取消采集任务"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


# ── 原始数据 ──

@router.get("/raw-data")
def list_raw_data():
    """查询原始数据（分页）"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.get("/raw-data/{item_id}")
def get_raw_data(item_id: str):
    """查看原始数据详情"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)
