"""简历解析 REST API —— 文件上传、结构化解析、简历检索"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, File, Query, UploadFile, status
from fastapi.responses import JSONResponse

from app.resume.models import ParsedResume, ResumeListResponse, ResumeUploadResponse
from app.resume.service import ResumeParsingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/resume", tags=["resume"])

# 服务单例（生产环境可通过应用生命周期注入）
_service: ResumeParsingService | None = None


def _get_service() -> ResumeParsingService:
    global _service  # noqa: PLW0603
    if _service is None:
        _service = ResumeParsingService()
    return _service


# ── 文件上传与解析 ──


@router.post("/upload", response_model=ParsedResume)
async def upload_resume(file: UploadFile = File(...)):
    """上传简历文件（PDF/DOCX）并触发结构化解析。

    Pipeline: 文件保存 → 文本提取 → LLM 解析 → MongoDB 持久化 → 返回 ParsedResume。
    """
    if not file.filename:
        return JSONResponse(
            status_code=400,
            content={"detail": "文件名为空"},
        )

    suffix = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if suffix not in ("pdf", "docx"):
        return JSONResponse(
            status_code=400,
            content={"detail": f"不支持的文件类型: .{suffix}，仅支持 PDF 和 DOCX"},
        )

    try:
        content = await file.read()
    except Exception:
        logger.exception("读取上传文件失败")
        return JSONResponse(status_code=500, content={"detail": "读取文件失败"})

    service = _get_service()
    try:
        result = await service.parse_single(content, file.filename)
    except Exception:
        logger.exception("简历解析失败: %s", file.filename)
        return JSONResponse(status_code=500, content={"detail": "简历解析失败"})

    return result


@router.post("/upload/batch")
async def batch_upload_resumes(files: list[UploadFile] = File(...)):
    """批量上传简历"""
    if not files:
        return JSONResponse(status_code=400, content={"detail": "至少上传一个文件"})

    file_tuples: list[tuple[bytes, str]] = []
    for f in files:
        if not f.filename:
            continue
        suffix = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
        if suffix not in ("pdf", "docx"):
            continue
        try:
            file_tuples.append((await f.read(), f.filename))
        except Exception:
            logger.warning("读取文件失败: %s", f.filename)

    service = _get_service()
    results = await service.parse_batch(file_tuples)

    return {
        "total": len(results),
        "results": [r.model_dump() for r in results],
    }


# ── 简历管理 ──


@router.get("/", response_model=ResumeListResponse)
async def list_resumes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """简历列表（分页）"""
    service = _get_service()
    items, total = await service.list_resumes(page=page, page_size=page_size)
    return ResumeListResponse(
        items=items, total=total, page=page, page_size=page_size
    )


@router.get("/{resume_id}", response_model=ParsedResume)
async def get_resume(resume_id: str):
    """查看解析后的结构化简历"""
    service = _get_service()
    result = await service.get_resume(resume_id)
    if result is None:
        return JSONResponse(
            status_code=404, content={"detail": f"简历不存在: {resume_id}"}
        )
    return result


@router.delete("/{resume_id}")
async def delete_resume(resume_id: str):
    """删除简历"""
    service = _get_service()
    deleted = await service.delete_resume(resume_id)
    if not deleted:
        return JSONResponse(
            status_code=404, content={"detail": f"简历不存在: {resume_id}"}
        )
    return {"message": "删除成功", "resume_id": resume_id}


# ── 简历检索 ──


@router.get("/search", response_model=ResumeListResponse)
async def search_resumes(
    keyword: str | None = Query(None, description="搜索关键词"),
    skills: list[str] | None = Query(None, description="技能筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """高级检索简历"""
    service = _get_service()
    items, total = await service.search_resumes(
        keyword=keyword,
        skills=skills,
        page=page,
        page_size=page_size,
    )
    return ResumeListResponse(
        items=items, total=total, page=page, page_size=page_size
    )