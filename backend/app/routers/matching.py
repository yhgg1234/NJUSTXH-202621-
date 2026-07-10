"""人岗匹配 REST API —— 多维度匹配、差距分析、学习路径、多岗位对比"""

from fastapi import APIRouter, HTTPException

from app.matching.models import (
    DemoOptionsResponse,
    GapAnalysisReport,
    GapAnalysisRequest,
    JobCompareResponse,
    LearningPathRequest,
    LearningPathResponse,
    MatchReport,
    MatchRequest,
    MultiMatchRequest,
)
from app.matching.service import MatchingService

router = APIRouter(prefix="/api/matching", tags=["matching"])
service = MatchingService()


def _not_found(exc: KeyError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc).strip("'"))


# ── 单岗位匹配 ──

@router.get("/demo-options", response_model=DemoOptionsResponse)
def get_demo_options():
    """并行开发阶段的演示简历和岗位选项"""
    return service.demo_options()


@router.post("/match", response_model=MatchReport)
async def match_resume_to_job(request: MatchRequest):
    """简历与单个岗位匹配"""
    try:
        return await service.match(request.resume_id, request.job_id)
    except KeyError as exc:
        raise _not_found(exc) from exc


@router.get("/match/{match_id}", response_model=MatchReport)
def get_match_report(match_id: str):
    """查看匹配报告详情"""
    try:
        return service.get_report(match_id)
    except KeyError as exc:
        raise _not_found(exc) from exc


# ── 多岗位对比 ──

@router.post("/multi-match", response_model=JobCompareResponse)
async def multi_match(request: MultiMatchRequest):
    """简历与多个岗位对比匹配"""
    try:
        return await service.multi_match(request.resume_id, request.job_ids)
    except KeyError as exc:
        raise _not_found(exc) from exc


# ── 差距分析 ──

@router.post("/gap-analysis", response_model=GapAnalysisReport)
async def gap_analysis(request: GapAnalysisRequest):
    """差距分析（逐技能对比）"""
    try:
        return await service.gap_analysis(request.resume_id, request.job_id)
    except KeyError as exc:
        raise _not_found(exc) from exc


# ── 学习路径 ──

@router.post("/learning-path", response_model=LearningPathResponse)
async def generate_learning_path(request: LearningPathRequest):
    """生成学习路径规划"""
    try:
        return await service.learning_path(
            request.resume_id,
            request.job_id,
            request.target_months,
        )
    except KeyError as exc:
        raise _not_found(exc) from exc


# ── 历史记录 ──

@router.get("/history", response_model=list[MatchReport])
def list_match_history():
    """查看匹配历史记录"""
    return service.list_history()
