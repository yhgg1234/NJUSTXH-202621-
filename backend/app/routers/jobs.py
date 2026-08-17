"""岗位动态演化与能力变更 REST API —— 新岗位发现（2.4）、能力变更、演化分析（3.1）"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.discovery.dependencies import get_discovery_service
from app.discovery.models import (
    AbilityChange,
    AbilityChangeAnalyzeRequest,
    AbilityChangeResponse,
    BatchAdoptRequest,
    BatchRejectRequest,
    BatchResult,
    CandidateEditRequest,
    CandidateReviewRequest,
    ChangeReviewRequest,
    DiscoverRequest,
    DiscoverResponse,
    DiscoverStats,
    DiscoveryEvaluationRequest,
    DiscoveryEvaluationResponse,
    NewJobCandidate,
)
from app.discovery.service import DiscoveryDataError, DiscoveryService
from app.jobs.dependencies import get_job_evolution_service
from app.jobs.models import (
    JobEvolutionQuery,
    JobEvolutionResponse,
    TimeGranularity,
)
from app.jobs.service import JobEvolutionService

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

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


# ── 子任务 2.4：新岗位发现 ──

@router.post("/discover-new", response_model=DiscoverResponse)
def discover_new_jobs(payload: DiscoverRequest, service: DiscoveryServiceDep) -> DiscoverResponse:
    """执行新岗位发现分析，返回候选新岗位列表。"""
    try:
        return service.discover(payload)
    except DiscoveryDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/discover-new/stats", response_model=DiscoverStats)
def get_discover_stats(service: DiscoveryServiceDep) -> DiscoverStats:
    """获取新岗位发现统计概览。"""
    return service.get_stats()


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
    return {"history": service.history(), "stats": service.get_stats()}


@router.post("/discovery/evaluate", response_model=DiscoveryEvaluationResponse)
def evaluate_discovery(
    payload: DiscoveryEvaluationRequest, service: DiscoveryServiceDep
) -> DiscoveryEvaluationResponse:
    """使用人工金标准量化新岗位发现和能力更新的 Precision/Recall/F1。"""

    return service.evaluate(payload)


@router.post("/ability-changes/analyze", response_model=AbilityChangeResponse)
def analyze_ability_changes(
    payload: AbilityChangeAnalyzeRequest, service: DiscoveryServiceDep
) -> AbilityChangeResponse:
    """比较 2.3 的两个周期快照并生成完整、可审核的能力变更日志。"""

    return service.analyze_ability_changes(payload)


@router.get("/ability-changes", response_model=list[AbilityChange])
def list_ability_changes(
    service: DiscoveryServiceDep, job_id: str | None = None
) -> list[AbilityChange]:
    return service.list_ability_changes(job_id)


@router.put("/ability-changes/{change_id}/review", response_model=AbilityChange)
def review_ability_change(
    change_id: str,
    payload: ChangeReviewRequest,
    service: DiscoveryServiceDep,
) -> AbilityChange:
    try:
        return service.review_ability_change(change_id, payload)
    except DiscoveryDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# 动态 candidate_id 路由必须位于 batch/history 等静态路由之后，避免路由遮蔽。
@router.get("/discover-new/{candidate_id}", response_model=NewJobCandidate)
def get_discover_candidate(
    candidate_id: str, service: DiscoveryServiceDep
) -> NewJobCandidate:
    candidate = service.get_candidate(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="候选新岗位不存在")
    return candidate


@router.put("/discover-new/{candidate_id}", response_model=NewJobCandidate)
def edit_discover_candidate(
    candidate_id: str,
    payload: CandidateEditRequest,
    service: DiscoveryServiceDep,
) -> NewJobCandidate:
    try:
        return service.edit_candidate(candidate_id, payload)
    except DiscoveryDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/discover-new/{candidate_id}/adopt")
def adopt_candidate(
    candidate_id: str,
    payload: CandidateReviewRequest,
    service: DiscoveryServiceDep,
):
    """人工采纳候选；图谱批次成功后才记录采纳状态。"""

    try:
        result = service.adopt(candidate_id, payload)
    except DiscoveryDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return result


@router.post("/discover-new/{candidate_id}/reject")
def reject_candidate(
    candidate_id: str,
    payload: CandidateReviewRequest,
    service: DiscoveryServiceDep,
):
    try:
        return service.reject(candidate_id, payload)
    except DiscoveryDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


