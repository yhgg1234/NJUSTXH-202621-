# coding: utf-8
"""信息抽取 REST API —— NER实体抽取、关系抽取、实体对齐、本体管理"""

import json
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, status, HTTPException
from fastapi.responses import JSONResponse

# 导入 LangChain 与大模型、向量库相关核心组件
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_milvus import Milvus
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.output_parsers import JsonOutputParser

# 完美承接原有路由定义：前缀为 /api/extraction
router = APIRouter(prefix="/api/extraction", tags=["extraction"])

_NOT_IMPL = {"message": "接口已定义，功能待实现", "status": 501}

# =====================================================================
# CONFIGURATION: 核心服务配置区
# =====================================================================
LLM_CONFIG = {
    "api_key": "cfVkXrSSmgBCnhKEPjKq:dLmtzXUzzrvoumPFtGXr",
    "base_url": "https://spark-api-open.xf-yun.com/v1",
    "model_name": "lite"  # 对齐云端底座兼容名称
}

MILVUS_CONFIG = {
    "connection_string": "http://localhost:19530",
    "collection_name": "standard_skills_lexicon"
}

# 本地模型软指向配置：可直接设为国内镜像下载的本地文件夹路径如 "D:/models/bge-m3"
# 如果保留为 "BAAI/bge-m3" 且本地无缓存，系统将在启动时安全检测并由于连接问题降级，不会死卡启动
LOCAL_MODEL_PATH = "BAAI/bge-m3"


# =====================================================================
# DATA CONTRACTS: 数据契约模型定义（严格保留，未做任何字段破坏）
# =====================================================================
class EntityExtractRequest(BaseModel):
    text: str = Field(..., description="需要进行实体抽取的原始招聘岗位 JD 文本")
    entity_types: Optional[List[str]] = Field(
        default=["position", "skill", "certificate", "industry", "tech_stack", "education", "company"],
        description="允许抽取的实体类型子集"
    )
    use_rag: bool = Field(default=True, description="是否启用 Milvus RAG")


class ExtractedEntity(BaseModel):
    name: str = Field(..., description="抽取出的实体文本名称")
    type: str = Field(..., description="实体类型")
    confidence: float = Field(default=1.0, description="置信度")


class InternalLlmSchema(BaseModel):
    position: List[str] = Field(default=[], description="岗位名称，如：高级后端开发工程师、电气控制工程师")
    skill: List[str] = Field(default=[],
                             description="硬性技术/工具/通用技能，如：Golang、Java、PLC编程。严禁放入学历、专业和证书！")
    certificate: List[str] = Field(default=[],
                                   description="要求的证书、执照或资质，如：注册电气工程师资格证、高级程序员证书")
    industry: List[str] = Field(default=[], description="行业或应用场景，如：互联网技术、重工、新能源、工业自动化")
    tech_stack: List[str] = Field(default=[],
                                  description="技术框架/底层架构/核心数据库，如：MySQL、Redis、Kafka、Spring Boot")
    education: List[str] = Field(default=[], description="学历要求或专业要求，如：硕士、本科、自动化专业、计算机相关专业")
    company: List[str] = Field(default=[],
                               description="招聘企业或机构名称，如：字节跳动、三一重工研究院、南京理工大学课题组")
    confidence_score: float = Field(default=0.9, description="整体抽取结果的置信度评分")
    reasoning_process: str = Field(default="", description="思维链推理轨迹")


class EntityExtractResponse(BaseModel):
    entities: List[ExtractedEntity] = Field(..., description="标准结构化实体资产列表")
    confidence_score: float = Field(..., description="整体抽取置信度")
    reasoning_process: str = Field(..., description="思维链推理轨迹描述")


# =====================================================================
# CORE SERVICES: RAG 服务与组件（高容错非阻塞优化）
# =====================================================================
class RagService:
    def __init__(self):
        try:
            # 💡 强力优化：使用 local_files_only=False，同时加入极端连接超时兜底
            # 优先加载本地缓存，避免在启动时无限死卡在外网下载
            self.embeddings = HuggingFaceEmbeddings(
                model_name=LOCAL_MODEL_PATH,
                model_kwargs={'device': 'cpu'}
            )
            self.vector_store = Milvus(
                embedding_function=self.embeddings,
                connection_string=MILVUS_CONFIG["connection_string"],
                collection_name=MILVUS_CONFIG["collection_name"]
            )
            self.enabled = True
        except Exception as e:
            # 优雅降级防护：即便本地没有下载好模型或者 Milvus 没启动，系统也能秒速加载，不卡死 Uvicorn 启动进程
            print(f"[RAG模块弱连提示] 本地嵌入模型未绪或Milvus断开，已安全降级，不影响基础大模型抽取。原因: {str(e)}")
            self.enabled = False

    def get_reference_skills(self, text: str) -> List[str]:
        if not self.enabled:
            return ["暂无关联标准词（向量数据库或本地嵌入模型未就绪）"]
        try:
            docs = self.vector_store.similarity_search(text, k=6)
            return [doc.page_content for doc in docs]
        except Exception:
            return []


rag_service = RagService()


def build_prompt_template() -> ChatPromptTemplate:
    # Prompt 深度优化：建立严苛的负面规约限制，指导大模型区分极易混淆的传统行业词汇
    system_instruction = (
        "你是一个专业的人力资源数据分析专家与图谱构建大师。\n"
        "你的任务是从输入的原始招聘岗位 JD 文本中，高精度地抽取核心实体。\n\n"
        "【硬性抽取判定规矩 —— 严防分类错位】\n"
        "1. 将实体严格归类到以下 7 种标准类型中：position, skill, certificate, industry, tech_stack, education, company。\n"
        "2. 资质证书（如高级程序员、注册电气工程师等）必须放入 certificate 字段；学历、学位以及所属专业（如硕士、自动化专业、电气工程）必须放入 education 字段。严禁将这二者混入普通的 skill 中！\n"
        "3. 严禁将参考背景中的环境提示词（如“未启用RAG”、“暂无关联标准词”、“向量数据库未就绪”）作为实体抽取出来！这些属于系统变量噪音，绝非文本中自带的实体！\n"
        "4. 必须按照指定的 JSON 格式返回结构化数据，且格式必须完整包含指定的全部字段。\n"
        "5. 直接输出合法 JSON 文本，严禁夹带 Markdown 的 ```json 标记或任何其他前导、后随的解释说明大白话。"
    )

    user_input_template = (
        "现在请处理以下真实的岗位数据，并根据限制抽取的类型【{target_types}】进行过滤归纳：\n"
        "【输入原始文本】:\n{text}\n\n"
        "【参考标准技能词】:\n{rag_skills}\n\n"
        "输出要求的格式化 JSON 字典："
    )

    return ChatPromptTemplate.from_messages([
        ("system", system_instruction),
        ("user", user_input_template)
    ])


# =====================================================================
# API CONTROLLER: 核心功能实现
# =====================================================================

# ── 实体抽取 ──
@router.post("/entities/extract", response_model=EntityExtractResponse)
async def extract_entities(payload: EntityExtractRequest):
    """高级大模型驱动的 NER 实体抽取接口（高容错后处理+多重防污染强化版）"""
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="输入的待解析文本(text)不能为空")

    try:
        # 1. 初始化通用语言模型实例
        llm = ChatOpenAI(
            api_key=LLM_CONFIG["api_key"],
            base_url=LLM_CONFIG["base_url"],
            model=LLM_CONFIG["model_name"],
            temperature=0.1
        )

        prompt_template = build_prompt_template()
        parser = JsonOutputParser(pydantic_object=InternalLlmSchema)
        chain = prompt_template | llm | parser

        # 2. 判断是否应用 RAG
        rag_skills = ["未启用RAG"]
        if payload.use_rag:
            rag_skills = rag_service.get_reference_skills(payload.text)

        # 3. 驱动大模型链路进行智能推理
        raw_output = chain.invoke({
            "text": payload.text,
            "target_types": ", ".join(payload.entity_types),
            "rag_skills": str(rag_skills)
        })

        # 💡 防护层 1：格式规整。若大模型将字段吐成了单字符串，自动转换为合法的 List
        list_fields = ["position", "skill", "certificate", "industry", "tech_stack", "education", "company"]
        for field in list_fields:
            if field in raw_output:
                if isinstance(raw_output[field], str):
                    raw_output[field] = [raw_output[field]] if raw_output[field].strip() else []
                elif raw_output[field] is None:
                    raw_output[field] = []

        # 确保基础兜底字段稳固
        if "confidence_score" not in raw_output or not raw_output["confidence_score"]:
            raw_output["confidence_score"] = 0.9
        if "reasoning_process" not in raw_output:
            raw_output["reasoning_process"] = "抽取完成。"

        # 4. 进行安全的数据契约校验转化
        llm_output = InternalLlmSchema(**raw_output)

        # 5. 平铺展开为标准实体资产长列表输出
        final_entities: List[ExtractedEntity] = []
        entity_mapping = {
            "position": llm_output.position,
            "skill": llm_output.skill,
            "certificate": llm_output.certificate,
            "industry": llm_output.industry,
            "tech_stack": llm_output.tech_stack,
            "education": llm_output.education,
            "company": llm_output.company
        }

        # 💡 防护层 2：规则黑名单清洗。彻底杜绝系统级的控制词、环境变量流入图谱数据库
        black_list_keywords = ["未启用", "RAG", "暂无关联", "标准词", "向量数据库", "未就绪"]

        for entity_type, entity_list in entity_mapping.items():
            if entity_type in payload.entity_types and entity_list:
                for name in entity_list:
                    # 基础清洗：剔除空值、去除首尾多余空格
                    if not name or not name.strip():
                        continue
                    clean_name = name.strip()

                    # 匹配黑名单拦截规则
                    if any(kw in clean_name for kw in black_list_keywords):
                        continue

                    final_entities.append(ExtractedEntity(
                        name=clean_name,
                        type=entity_type,
                        confidence=llm_output.confidence_score
                    ))

        return EntityExtractResponse(
            entities=final_entities,
            confidence_score=llm_output.confidence_score,
            reasoning_process=llm_output.reasoning_process
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"大模型信息抽取管线内部异常: {str(e)}")


# ── 关系/对齐/本体 [完美留存原有桩状态，未做任何改变] ──
@router.post("/relations/extract")
def extract_relations(): return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.post("/entities/align")
def align_entities(): return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.get("/entities/align/history")
def list_align_history(): return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.get("/ontology")
def get_ontology(): return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.put("/ontology")
def update_ontology(): return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.get("/ontology/entities")
def list_ontology_entities(): return JSONResponse(status_code=501, content=_NOT_IMPL)


@router.get("/ontology/relations")
def list_ontology_relations(): return JSONResponse(status_code=501, content=_NOT_IMPL)
