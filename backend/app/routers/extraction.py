"""信息抽取 REST API —— NER实体抽取、关系抽取、实体对齐、本体管理"""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/extraction", tags=["extraction"])

_NOT_IMPL = {"message": "接口已定义，功能待实现", "status": 501}


# ── 实体抽取 ──

@router.post("/entities/extract")
def extract_entities():
    """NER 实体抽取"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


# ── 关系抽取 ──

@router.post("/relations/extract")
def extract_relations():
    """关系抽取"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


# ── 实体对齐 ──

@router.post("/entities/align")
def align_entities():
    """实体对齐（消歧、合并同义实体）"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.get("/entities/align/history")
def list_align_history():
    """查询对齐历史"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


# ── 本体管理 ──

@router.get("/ontology")
def get_ontology():
    """获取当前本体 Schema"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.put("/ontology")
def update_ontology():
    """更新本体 Schema"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.get("/ontology/entities")
def list_ontology_entities():
    """列出所有本体实体定义"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.get("/ontology/relations")
def list_ontology_relations():
    """列出所有本体关系定义"""
    return JSONResponse(status_code=501, content=_NOT_IMPL)
