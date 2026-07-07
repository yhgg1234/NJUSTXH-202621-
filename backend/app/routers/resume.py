"""简历解析 REST API —— 文件上传、结构化解析、简历检索"""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/resume", tags=["resume"])

_NOT_IMPL = {"message": "接口已定义，功能待实现", "status": 501}


# ── 文件上传与解析 ──

@router.post("/upload")
def upload_resume():
    """上传简历文件（PDF/DOCX）并触发解析"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.post("/upload/batch")
def batch_upload_resumes():
    """批量上传简历"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


# ── 简历管理 ──

@router.get("/")
def list_resumes():
    """简历列表（支持检索/筛选）"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.get("/{resume_id}")
def get_resume(resume_id: str):
    """查看解析后的结构化简历"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.delete("/{resume_id}")
def delete_resume(resume_id: str):
    """删除简历"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


# ── 简历检索 ──

@router.get("/search")
def search_resumes():
    """高级检索简历"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)
