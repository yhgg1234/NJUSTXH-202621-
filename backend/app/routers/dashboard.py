"""仪表盘 REST API —— 统计概览、趋势数据、热门排行"""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

_NOT_IMPL = {"message": "接口已定义，功能待实现", "status": 501}


# ── 概览 ──

@router.get("/overview")
def get_overview():
    """系统统计概览（总数、分布等）"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


# ── 趋势 ──

@router.get("/trends")
def get_trends():
    """岗位/技能趋势数据"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


# ── 热门排行 ──

@router.get("/hot-rankings")
def get_hot_rankings():
    """热门技能、技术栈、行业排行"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


# ── 最近活动 ──

@router.get("/recent-activity")
def get_recent_activity():
    """最近系统活动记录"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)
