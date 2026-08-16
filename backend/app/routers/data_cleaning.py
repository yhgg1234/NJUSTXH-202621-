"""数据清洗 REST API —— 清洗管线、去重、质量检查、数据集管理"""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/data-cleaning", tags=["data-cleaning"])

_NOT_IMPL = {"message": "接口已定义，功能待实现", "status": 501}


# ── 清洗管线 ──

@router.get("/pipeline/defaults")
def get_pipeline_defaults():
    """获取默认管线配置"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


# ── 清洗任务 ──

@router.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_cleaning_task():
    """创建清洗任务"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.get("/tasks")
def list_cleaning_tasks():
    """查询清洗任务列表"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.get("/tasks/{task_id}")
def get_cleaning_task(task_id: str):
    """查看清洗任务状态"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


# ── 质量检查 ──

@router.get("/quality-check")
def list_quality_items():
    """获取待校验数据项列表"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.post("/quality-review")
def submit_quality_review():
    """提交人工校验结果"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


# ── 数据集 ──

@router.get("/datasets")
def list_datasets():
    """查询清洗后数据集（分页）"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.get("/datasets/{item_id}")
def get_dataset_item(item_id: str):
    """查看数据集条目详情"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.delete("/datasets/{item_id}")
def delete_dataset_item(item_id: str):
    """删除数据集条目"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)
