"""岗位管理 REST API —— 岗位CRUD、检索、新岗位发现、演化分析"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.jobs.dependencies import get_job_evolution_service
from app.jobs.models import (
    JobEvolutionQuery,
    JobEvolutionResponse,
    TimeGranularity,
)
from app.jobs.service import JobEvolutionService

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

_NOT_IMPL = {"message": "接口已定义，功能待实现", "status": 501}
EvolutionService = Annotated[JobEvolutionService, Depends(get_job_evolution_service)]


# ── 子任务 3.1：岗位动态演化 ──

@router.post("/evolution", response_model=JobEvolutionResponse)
def analyze_evolution(payload: JobEvolutionQuery, service: EvolutionService) -> JobEvolutionResponse:
    """返回岗位在多个时间切片中的技能快照、变化与趋势。"""

    return service.analyze(payload)


@router.get("/{job_id}/evolution-timeline", response_model=JobEvolutionResponse)
def get_evolution_timeline(
    job_id: str,
    service: EvolutionService,
    granularity: TimeGranularity = TimeGranularity.QUARTERLY,
    start: date | None = None,
    end: date | None = None,
    top_n: Annotated[int, Query(ge=1, le=30)] = 10,
    change_threshold: Annotated[float, Query(ge=0.0, le=1.0)] = 0.05,
    prediction_horizon_months: Annotated[int, Query(ge=1, le=12)] = 6,
) -> JobEvolutionResponse:
    """GET 形式的演化时间线，便于前端时间滑块和图表刷新。"""

    if (start is None) != (end is None):
        raise HTTPException(status_code=422, detail="start and end must be supplied together")
    return service.analyze(
        JobEvolutionQuery(
            job_id=job_id,
            granularity=granularity,
            time_range=(start, end) if start and end else None,
            top_n=top_n,
            change_threshold=change_threshold,
            prediction_horizon_months=prediction_horizon_months,
        )
    )


# ── 岗位 CRUD ──

@router.get("/")
def list_jobs():
    """岗位列表（支持检索/筛选）"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_job():
    """创建新岗位"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.get("/{job_id}")
def get_job(job_id: str):
    """查看岗位详情"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.put("/{job_id}")
def update_job(job_id: str):
    """更新岗位信息"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.delete("/{job_id}")
def delete_job(job_id: str):
    """删除岗位"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


# ── 岗位检索 ──

@router.get("/search")
def search_jobs():
    """高级检索岗位"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


# ── 新岗位发现 ──

@router.post("/discover-new")
def discover_new_jobs():
    """新岗位自动发现"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


# ── 技能管理 ──

@router.get("/skills/hot")
def get_hot_skills():
    """获取热门技能排行"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.get("/skills/{skill_name}/trend")
def get_skill_trend(skill_name: str):
    """获取技能趋势数据"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)
