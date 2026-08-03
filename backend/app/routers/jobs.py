"""岗位管理 REST API —— 岗位CRUD、检索、新岗位发现、演化分析"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.discovery.dependencies import get_discovery_service
from app.discovery.models import (
    BatchAdoptRequest,
    BatchRejectRequest,
    BatchResult,
    DiscoverRequest,
    DiscoverResponse,
    DiscoverStats,
)
from app.discovery.service import DiscoveryService
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
DiscoveryServiceDep = Annotated[DiscoveryService, Depends(get_discovery_service)]


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


# ── 子任务 2.4：新岗位发现 ──

@router.post("/discover-new", response_model=DiscoverResponse)
def discover_new_jobs(payload: DiscoverRequest, service: DiscoveryServiceDep) -> DiscoverResponse:
    """执行新岗位发现分析，返回候选新岗位列表。"""
    return service.discover(payload)


@router.get("/discover-new/stats", response_model=DiscoverStats)
def get_discover_stats(service: DiscoveryServiceDep) -> DiscoverStats:
    """获取新岗位发现统计概览。"""
    return service.get_stats()


@router.get("/discover-new/{candidate_id}")
def get_discover_candidate(candidate_id: str, service: DiscoveryServiceDep):
    """查看单个候选新岗位详情。"""
    candidate = service.get_candidate(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="候选新岗位不存在")
    return candidate


@router.post("/discover-new/{candidate_id}/adopt")
def adopt_candidate(
    candidate_id: str,
    service: DiscoveryServiceDep,
    create_graph_nodes: bool = True,
):
    """采纳候选新岗位，可选择是否写入图谱。"""
    result = service.adopt(candidate_id, create_graph_nodes)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return result


@router.post("/discover-new/{candidate_id}/reject")
def reject_candidate(candidate_id: str, service: DiscoveryServiceDep):
    """否决候选新岗位。"""
    result = service.reject(candidate_id)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return result


@router.post("/discover-new/batch/adopt", response_model=BatchResult)
def batch_adopt(payload: BatchAdoptRequest, service: DiscoveryServiceDep) -> BatchResult:
    """批量采纳候选新岗位。"""
    return service.batch_adopt(payload)


@router.post("/discover-new/batch/reject", response_model=BatchResult)
def batch_reject(payload: BatchRejectRequest, service: DiscoveryServiceDep) -> BatchResult:
    """批量否决候选新岗位。"""
    return service.batch_reject(payload)


@router.get("/discover-new/history")
def get_adoption_history(service: DiscoveryServiceDep):
    """查看采纳/否决历史记录。"""
    stats = service.get_stats()
    candidates = []
    for cid, status in service._adoption_log.items():
        c = service.get_candidate(cid)
        if c:
            candidates.append({"candidate_id": cid, "name": c.name, "status": status.value})
    return {"history": candidates, "stats": stats}


# ── 技能管理 ──

@router.get("/skills/hot")
def get_hot_skills():
    """获取热门技能排行"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.get("/skills/{skill_name}/trend")
def get_skill_trend(skill_name: str):
    """获取技能趋势数据"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)
