"""人岗匹配 REST API —— 多维度匹配、差距分析、学习路径、多岗位对比"""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/matching", tags=["matching"])

_NOT_IMPL = {"message": "接口已定义，功能待实现", "status": 501}


# ── 单岗位匹配 ──

@router.post("/match")
def match_resume_to_job():
    """简历与单个岗位匹配"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.get("/match/{match_id}")
def get_match_report(match_id: str):
    """查看匹配报告详情"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


# ── 多岗位对比 ──

@router.post("/multi-match")
def multi_match():
    """简历与多个岗位对比匹配"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


# ── 差距分析 ──

@router.post("/gap-analysis")
def gap_analysis():
    """差距分析（逐技能对比）"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


# ── 学习路径 ──

@router.post("/learning-path")
def generate_learning_path():
    """生成学习路径规划"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


# ── 历史记录 ──

@router.get("/history")
def list_match_history():
    """查看匹配历史记录"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)
