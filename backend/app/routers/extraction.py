# coding: utf-8
"""
HR 知识图谱信息抽取单文件服务 (FastAPI + LLM + RAG + Post-processing)
直接运行: python app.py
文档地址: http://127.0.0.1:8000/docs
"""

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import pandas as pd
from pydantic import BaseModel, Field
from pymilvus import DataType, MilvusClient
import uvicorn

try:
  from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
  from langchain_community.embeddings import HuggingFaceEmbeddings

# ==============================================================================
# 1. 全局基础配置与词典定义
# ==============================================================================

# 解决国内网络无法直接访问 HuggingFace 的超时问题
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# LLM 与向量服务配置
LLM_CONFIG = {
    "api_key": os.getenv(
        "SPARK_API_KEY", "cfVkXrSSmgBCnhKEPjKq:dLmtzXUzzrvoumPFtGXr"
    ),
    "base_url": "https://spark-api-open.xf-yun.com/v1",
    "model_name": "lite",
}

MILVUS_CONFIG = {
    "uri": os.getenv("MILVUS_URI", "http://127.0.0.1:19530"),
    "collection_name": "standard_skills_lexicon",
}

LOCAL_MODEL_PATH = "BAAI/bge-m3"
SCHEMA_VERSION = "1.0.0"
PROMPT_VERSION = "jd-extract-v2.5.1"
TZ_SHANGHAI = timezone(timedelta(hours=8))

# 实体与关系类型规范
ALLOWED_ENTITY_TYPES = {
    "position",
    "skill",
    "certificate",
    "industry",
    "tech_stack",
    "education",
    "company",
    "project",
}
ALLOWED_RELATION_TYPES = {
    "requires",
    "prefers",
    "prerequisite",
    "same_as",
    "related_to",
    "belongs_to",
    "evolved_from",
    "applies_to",
}

TYPE_MAPPING = {
    "岗位": "position",
    "职位": "position",
    "position": "position",
    "技能": "skill",
    "技能要求": "skill",
    "能力": "skill",
    "skill": "skill",
    "证书": "certificate",
    "资质": "certificate",
    "certificate": "certificate",
    "行业": "industry",
    "industry": "industry",
    "技术栈": "tech_stack",
    "工具": "tech_stack",
    "框架": "tech_stack",
    "tech_stack": "tech_stack",
    "学历": "education",
    "专业": "education",
    "education": "education",
    "公司": "company",
    "企业": "company",
    "company": "company",
    "项目": "project",
    "project": "project",
}

KNOWN_TECH_KEYWORDS = {
    "python",
    "java",
    "go",
    "golang",
    "c++",
    "c#",
    "typescript",
    "javascript",
    "html",
    "css",
    "react",
    "vue",
    "vue3",
    "vite",
    "spring",
    "spring boot",
    "mybatis",
    "django",
    "flask",
    "gin",
    "docker",
    "kubernetes",
    "k8s",
    "git",
    "linux",
    "mysql",
    "redis",
    "mongodb",
    "elasticsearch",
    "http",
    "tcp/ip",
    "restful",
    "grpc",
    "kafka",
    "tomcat",
    "jvm",
    "mlflow",
    "airflow",
    "opencv",
    "halcon",
    "yolo",
    "faster r-cnn",
    "openstack",
    "gitlab",
    "aws",
    "azure",
    "harbor",
    "minio",
    "nfs",
    "scikit-learn",
    "office",
    "excel",
    "word",
    "ppt",
    "visio",
    "cad",
    "solidworks",
    "node.js",
    "node",
}

NON_TECH_SKILL_KEYWORDS = {
    "安全管理",
    "隐患排查",
    "事故调查",
    "应急演练",
    "安全培训",
    "消防安全",
    "EHS",
    "安全生产",
    "行政管理",
    "考勤管理",
    "资产管理",
    "文档撰写",
    "绩效考核",
    "招聘选拔",
    "员工关系",
    "财务报销",
    "成本控制",
    "预算管理",
    "税务申报",
    "资金管理",
    "财务审计",
    "供应链管理",
    "采购管理",
    "供应商管理",
    "仓储管理",
    "物流调度",
    "质量控制",
    "品质管理",
    "QA",
    "QC",
    "ISO体系",
    "现场管理",
    "5S管理",
    "客户关系维护",
    "商务谈判",
    "渠道拓展",
    "项目进度管理",
    "风险评估",
}

FALLBACK_SKILL_PATTERNS = [
    r"Python",
    r"Java",
    r"Go(?:lang)?",
    r"C\+\+",
    r"C#",
    r"TypeScript",
    r"JavaScript",
    r"HTML5?",
    r"CSS3?",
    r"React",
    r"Vue(?:\.js|3)?",
    r"Vite",
    r"Spring(?:\s*Boot)?",
    r"MyBatis",
    r"Django",
    r"Flask",
    r"Gin",
    r"Docker",
    r"Kubernetes|K8s",
    r"Git",
    r"Linux",
    r"MySQL",
    r"Redis",
    r"MongoDB",
    r"Elasticsearch",
    r"Kafka",
    r"Tomcat",
    r"JVM",
    r"MLflow",
    r"Airflow",
    r"OpenCV",
    r"Halcon",
    r"YOLO",
    r"Node(?:\.js)?",
    r"深度学习",
    r"机器学习",
    r"计算机视觉",
    r"特征工程",
    r"缺陷检测",
    r"安全管理",
    r"隐患排查",
    r"应急演练",
    r"消防安全",
    r"安全生产",
    r"EHS",
    r"考勤管理",
    r"绩效考核",
    r"成本控制",
    r"预算管理",
    r"质量控制",
    r"5S管理",
    r"本科",
    r"硕士",
    r"博士",
    r"大专",
    r"英语四级",
    r"英语六级",
    r"PMP",
    r"注册安全工程师",
    r"初级会计",
]

PREFER_KEYWORDS = {
    "优先",
    "加分",
    "优先考虑",
    "优先录取",
    "优先录用",
    "加分项",
    "plus",
    "preferred",
}

SEED_SKILLS_DATA = [
    {"text": "Python", "category": "tech_stack"},
    {"text": "Java", "category": "tech_stack"},
    {"text": "C++", "category": "tech_stack"},
    {"text": "Go", "category": "tech_stack"},
    {"text": "TypeScript", "category": "tech_stack"},
    {"text": "JavaScript", "category": "tech_stack"},
    {"text": "React", "category": "tech_stack"},
    {"text": "Vue", "category": "tech_stack"},
    {"text": "Node.js", "category": "tech_stack"},
    {"text": "Spring Boot", "category": "tech_stack"},
    {"text": "Docker", "category": "tech_stack"},
    {"text": "Kubernetes", "category": "tech_stack"},
    {"text": "Redis", "category": "tech_stack"},
    {"text": "MySQL", "category": "tech_stack"},
    {"text": "PyTorch", "category": "tech_stack"},
    {"text": "TensorFlow", "category": "tech_stack"},
    {"text": "OpenCV", "category": "tech_stack"},
    {"text": "安全管理", "category": "skill"},
    {"text": "隐患排查", "category": "skill"},
    {"text": "安全培训", "category": "skill"},
]

# ==============================================================================
# 2. Pydantic 数据模型定义
# ==============================================================================


class SingleExtractRequest(BaseModel):
  """单条 JD 即时抽取请求数据规范"""

  job_title: Optional[str] = Field(default="岗位", description="岗位名称")
  responsibilities: Optional[str] = Field(
      default="", description="工作职责内容"
  )
  requirements: Optional[str] = Field(default="", description="任职要求内容")
  raw_text: Optional[str] = Field(
      default=None, description="完整正文文本（若无则自动拼接）"
  )


class DerivedFields(BaseModel):
  """快捷统计结构"""

  raw_skills: Optional[str] = Field(None, description="通用技能列表 (分号分隔)")
  tech_stack: Optional[str] = Field(
      None, description="技术栈/工具列表 (分号分隔)"
  )
  certificates: Optional[str] = Field(
      "无硬性要求", description="证书列表 (分号分隔)"
  )
  education: Optional[str] = Field(None, description="学历要求 (分号分隔)")


class ExtractionResponseData(BaseModel):
  """图谱提取核心结果格式"""

  entities: List[Dict[str, Any]] = Field(..., description="实体节点列表")
  relations: List[Dict[str, Any]] = Field(..., description="关系边列表")
  events: List[Dict[str, Any]] = Field(default=[], description="事件列表")
  overall_confidence: float = Field(..., description="整体提取置信度")
  needs_human_review: bool = Field(..., description="是否触发人工复核闸门")
  quality_issues: List[str] = Field(
      default=[], description="质量问题列表 (如召回过低)"
  )
  derived_fields: DerivedFields = Field(..., description="快捷离散提取汇总")


class SingleExtractResponse(BaseModel):
  """接口统一返回包装"""

  code: int = Field(200, description="状态码")
  message: str = Field("success", description="返回信息")
  data: ExtractionResponseData


# ==============================================================================
# 3. Milvus 向量服务 & 图谱抽取逻辑
# ==============================================================================


class RagService:

  def __init__(self):
    try:
      self.client = MilvusClient(uri=MILVUS_CONFIG["uri"])
      self.embeddings = HuggingFaceEmbeddings(
          model_name=LOCAL_MODEL_PATH, model_kwargs={"device": "cpu"}
      )
      self.enabled = True
      print("✅ [RAG服务] Milvus 向量检索服务初始化成功！")
    except Exception as e:
      print(f"⚠️ [RAG服务未就绪，降级运行]: {str(e)}")
      self.enabled = False

  def get_reference_skills(self, text: str, top_k: int = 8) -> List[str]:
    if not self.enabled or not text or not text.strip():
      return []
    try:
      query_vector = self.embeddings.embed_query(text)
      results = self.client.search(
          collection_name=MILVUS_CONFIG["collection_name"],
          data=[query_vector],
          limit=top_k,
          output_fields=["text"],
      )
      if not results or not results[0]:
        return []
      return [hit["entity"]["text"] for hit in results[0]]
    except Exception as e:
      print(f"⚠️ [RAG向量检索异常]: {str(e)}")
      return []


rag_service = RagService()


def init_milvus_collection():
  """初始化向量标准词库表"""
  client = MilvusClient(uri=MILVUS_CONFIG["uri"])
  coll_name = MILVUS_CONFIG["collection_name"]

  if client.has_collection(coll_name):
    print(f"🗑️ 发现旧 Collection `{coll_name}`，清理重建...")
    client.drop_collection(coll_name)

  embeddings = HuggingFaceEmbeddings(
      model_name=LOCAL_MODEL_PATH, model_kwargs={"device": "cpu"}
  )
  texts = [item["text"] for item in SEED_SKILLS_DATA]
  vectors = embeddings.embed_documents(texts)

  schema = client.create_schema(auto_id=True, enable_dynamic_field=True)
  schema.add_field(
      field_name="id", datatype=DataType.INT64, is_primary=True, auto_id=True
  )
  schema.add_field(
      field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=len(vectors[0])
  )
  schema.add_field(
      field_name="text", datatype=DataType.VARCHAR, max_length=128
  )
  schema.add_field(
      field_name="category", datatype=DataType.VARCHAR, max_length=64
  )

  index_params = client.prepare_index_params()
  index_params.add_index(
      field_name="vector", metric_type="COSINE", index_type="AUTOINDEX"
  )

  client.create_collection(
      collection_name=coll_name, schema=schema, index_params=index_params
  )

  data = [
      {"vector": vec, "text": item["text"], "category": item["category"]}
      for item, vec in zip(SEED_SKILLS_DATA, vectors)
  ]
  res = client.insert(collection_name=coll_name, data=data)
  print(f"🎉 Milvus 初始化完成，写入 {res['insert_count']} 条种子词库！")


def build_prompt_template() -> ChatPromptTemplate:
  system_instruction = (
      "你是一个极其细致的人力资源知识图谱抽取专家，必须严格遵守 1.0.0 数据规范。\n"
      "你的核心任务是从招聘 JD 文本中**高召回、高精准**地提取实体与依赖关系。\n\n"
      "【分类核心标准】\n"
      "1. `tech_stack`: 编程语言(Python/Java)、开源框架(React/Vue)、组件/工具(Docker/Git/Excel)。\n"
      "2. `skill`: 业务与管理能力，如 '安全管理'、'隐患排查'、'机器学习'、'沟通协调'。\n"
      "3. `position`: 招聘目标岗位名称（如 '安全工程师'、'前端开发工程师'）。\n"
      "4. `education`: 学历/专业（如 本科、硕士、计算机相关专业）。\n"
      "5. `certificate`: 硬性资质证书（如 英语四级、注册安全工程师、PMP）。\n\n"
      "【关系类型说明】\n"
      "- `requires`: 岗位必要的技能/条件（硬性门槛）。\n"
      "- `prefers`: 岗位偏好/加分技能/条件（原文包含 '优先'、'加分' 等表述）。\n\n"
      "【输出 JSON 示例】\n"
      "```json\n"
      "{{\n"
      '  "entities": [\n'
      '    {{"mention_id": "m-0001", "type": "position", "name":'
      ' "Web前端工程师", "confidence": 1.0, "evidence": {{"quote":'
      ' "Web前端工程师", "section": "metadata"}}}},\n'
      '    {{"mention_id": "m-0002", "type": "tech_stack", "name": "Vue",'
      ' "confidence": 0.95, "evidence": {{"quote": "熟练掌握 Vue", "section":'
      ' "requirements"}}}},\n'
      '    {{"mention_id": "m-0003", "type": "tech_stack", "name": "Node.js",'
      ' "confidence": 0.95, "evidence": {{"quote": "了解 Node.js 优先",'
      ' "section": "requirements"}}}}\n'
      "  ],\n"
      '  "relations": [\n'
      '    {{"relation_id": "r-0001", "type": "requires", "head_mention_id":'
      ' "m-0001", "tail_mention_id": "m-0002", "confidence": 0.9, "evidence":'
      ' {{"quote": "熟练掌握 Vue", "section": "requirements"}}}},\n'
      '    {{"relation_id": "r-0002", "type": "prefers", "head_mention_id":'
      ' "m-0001", "tail_mention_id": "m-0003", "confidence": 0.9, "evidence":'
      ' {{"quote": "了解 Node.js 优先", "section": "requirements"}}}}\n'
      "  ]\n"
      "}}\n"
      "```\n\n"
      "只输出合法 JSON 格式，绝不添加任何解释说明！"
  )
  user_input_template = (
      "待处理文本:\n{text}\n\n参考标准词库:\n{rag_skills}\n\n请按规范全量抽取并输出"
      " JSON："
  )
  return ChatPromptTemplate.from_messages(
      [("system", system_instruction), ("user", user_input_template)]
  )


def clean_position_name(pos_name: str) -> str:
  if not pos_name:
    return "岗位"
  pos_name = pos_name.strip()
  pos_clean = re.sub(r"[\(（].*?[\)）]", "", pos_name).strip()
  return pos_clean if pos_clean else pos_name


def clean_entity_name(name: str) -> str:
  name = name.strip()
  prefixes = [
      r"^熟练掌握",
      r"^精通",
      r"^熟悉",
      r"^了解",
      r"^具备",
      r"^拥有",
      r"^负责",
      r"^组织",
      r"^定期",
      r"^参与",
      r"^监督",
      r"^协调",
      r"^编制",
      r"^修订",
      r"^开展",
      r"^建立",
  ]
  for p in prefixes:
    name = re.sub(p, "", name).strip()
  suffixes = [r"经验$", r"能力$", r"负责$", r"相关$", r"等法规标准$", r"工作$"]
  for s in suffixes:
    name = re.sub(s, "", name).strip()
  return name


def is_valid_entity(name: str, ent_type: str) -> bool:
  if not name or len(name) < 2:
    return False
  if any(tech in name.lower() for tech in KNOWN_TECH_KEYWORDS):
    return True
  if name in NON_TECH_SKILL_KEYWORDS:
    return True
  if ent_type in ["position", "education", "certificate"]:
    return True
  if len(name) > 10:
    return False
  verb_indicators = [
      "建设",
      "维护",
      "沟通",
      "调查",
      "处置",
      "解决方案",
      "培训",
      "识别",
      "隐患",
      "制定",
      "演练",
      "编制",
      "审查",
  ]
  if any(v in name for v in verb_indicators) and len(name) > 5:
    return False
  return True


def detect_relation_type(
    ent_name: str,
    evidence: dict,
    raw_text: str,
    llm_suggested_type: str = "requires",
) -> str:
  rel_type = (
      llm_suggested_type
      if llm_suggested_type in ALLOWED_RELATION_TYPES
      else "requires"
  )
  if rel_type == "prefers":
    return "prefers"

  quote = ""
  if isinstance(evidence, dict):
    quote = str(evidence.get("quote", ""))
  elif isinstance(evidence, str):
    quote = evidence

  if quote and any(kw in quote for kw in PREFER_KEYWORDS):
    return "prefers"

  if raw_text and ent_name:
    segments = re.split(r"[\n;；。]", raw_text)
    for seg in segments:
      if ent_name.lower() in seg.lower() and any(
          kw in seg for kw in PREFER_KEYWORDS
      ):
        return "prefers"

  return rel_type


def clean_and_normalize_json(
    raw_str: str,
    job_title_default: str = "岗位",
    raw_input_full: str = "",
) -> dict:
  clean_str = re.sub(r"^```json\s*", "", raw_str.strip(), flags=re.MULTILINE)
  clean_str = re.sub(r"^```\s*", "", clean_str, flags=re.MULTILINE)
  clean_str = re.sub(r"```$", "", clean_str, flags=re.MULTILINE).strip()

  try:
    data = json.loads(clean_str)
  except Exception:
    match = re.search(r"\{.*\}", clean_str, re.DOTALL)
    data = (
        json.loads(match.group())
        if match
        else {"entities": [], "relations": []}
    )

  if not isinstance(data, dict):
    data = {"entities": [], "relations": []}

  raw_entities = data.get("entities", [])
  raw_relations = data.get("relations", [])

  llm_rel_type_map = {}
  if isinstance(raw_relations, list):
    for r in raw_relations:
      if isinstance(r, dict) and "tail_mention_id" in r:
        llm_rel_type_map[r["tail_mention_id"]] = r.get("type", "requires")

  norm_entities, seen_names = [], set()
  entity_counter = 1

  position_head_id = "m-0000"
  clean_pos = clean_position_name(job_title_default)
  norm_entities.append({
      "mention_id": position_head_id,
      "type": "position",
      "name": clean_pos,
      "confidence": 1.0,
      "evidence": {"quote": job_title_default, "section": "metadata"},
      "_rel_type": "requires",
  })
  seen_names.add(clean_pos.lower())

  for e in raw_entities:
    if not isinstance(e, dict):
      continue
    raw_id = e.get("mention_id", "")
    raw_name = str(e.get("name") or e.get("quote") or "").strip()
    cleaned_name = clean_entity_name(raw_name)
    c_lower = cleaned_name.lower()

    if not cleaned_name or c_lower in seen_names:
      continue

    raw_type = str(e.get("type", "skill")).strip()
    norm_type = TYPE_MAPPING.get(raw_type, raw_type.lower())

    if (
        any(tech in c_lower for tech in KNOWN_TECH_KEYWORDS)
        or norm_type == "tech_stack"
    ):
      norm_type = "tech_stack"
    elif norm_type in ["education", "certificate"]:
      pass
    elif norm_type == "position":
      continue
    else:
      norm_type = "skill"

    if not is_valid_entity(cleaned_name, norm_type):
      continue

    evidence_info = e.get(
        "evidence", {"quote": cleaned_name, "section": "requirements"}
    )
    llm_suggested_rel = llm_rel_type_map.get(raw_id, "requires")
    rel_type = detect_relation_type(
        cleaned_name, evidence_info, raw_input_full, llm_suggested_rel
    )

    if norm_type in ["skill", "tech_stack"] and (
        "/" in cleaned_name or "、" in cleaned_name
    ):
      sub_names = [
          s.strip() for s in re.split(r"[/、]", cleaned_name) if s.strip()
      ]
      for sub in sub_names:
        sub_clean = clean_entity_name(sub)
        sub_lower = sub_clean.lower()
        if not sub_clean or sub_lower in seen_names:
          continue
        seen_names.add(sub_lower)
        sub_type = (
            "tech_stack"
            if any(t in sub_lower for t in KNOWN_TECH_KEYWORDS)
            else norm_type
        )
        sub_rel_type = detect_relation_type(
            sub_clean, evidence_info, raw_input_full, llm_suggested_rel
        )

        norm_entities.append({
            "mention_id": f"m-{entity_counter:04d}",
            "type": sub_type,
            "name": sub_clean,
            "confidence": float(e.get("confidence", 0.9)),
            "evidence": evidence_info,
            "_rel_type": sub_rel_type,
        })
        entity_counter += 1
    else:
      seen_names.add(c_lower)
      norm_entities.append({
          "mention_id": f"m-{entity_counter:04d}",
          "type": norm_type,
          "name": cleaned_name,
          "confidence": float(e.get("confidence", 0.9)),
          "evidence": evidence_info,
          "_rel_type": rel_type,
      })
      entity_counter += 1

  if raw_input_full:
    for pat in FALLBACK_SKILL_PATTERNS:
      matches = re.findall(pat, raw_input_full, re.IGNORECASE)
      for m in matches:
        m_str = clean_entity_name(m.strip())
        m_lower = m_str.lower()
        if m_str and m_lower not in seen_names:
          seen_names.add(m_lower)
          if m_str in ["本科", "硕士", "博士", "大专"]:
            ent_t = "education"
          elif (
              "级" in m_str
              or "证书" in m_str
              or "工程师" in m_str
              or "PMP" in m_str
          ):
            ent_t = "certificate"
          elif any(t in m_lower for t in KNOWN_TECH_KEYWORDS):
            ent_t = "tech_stack"
          else:
            ent_t = "skill"

          fallback_rel_type = detect_relation_type(
              m_str,
              {"quote": m_str, "section": "requirements"},
              raw_input_full,
              "requires",
          )
          norm_entities.append({
              "mention_id": f"m-{entity_counter:04d}",
              "type": ent_t,
              "name": m_str,
              "confidence": 0.85,
              "evidence": {"quote": m_str, "section": "requirements"},
              "_rel_type": fallback_rel_type,
          })
          entity_counter += 1

  norm_relations = []
  relation_counter = 1
  for ent in norm_entities:
    e_id = ent["mention_id"]
    if e_id != position_head_id:
      rel_type = ent.pop("_rel_type", "requires")
      norm_relations.append({
          "relation_id": f"r-{relation_counter:04d}",
          "type": rel_type,
          "head_mention_id": position_head_id,
          "tail_mention_id": e_id,
          "confidence": ent["confidence"],
          "evidence": ent["evidence"],
          "properties": {"proficiency": None, "min_years": None},
      })
      relation_counter += 1
    else:
      ent.pop("_rel_type", None)

  non_position_count = len(norm_entities) - 1
  needs_review = non_position_count == 0

  return {
      "entities": norm_entities,
      "relations": norm_relations,
      "events": [],
      "overall_confidence": 0.95 if non_position_count > 0 else 0.50,
      "needs_human_review": needs_review,
  }


def derive_helper_fields(entities: list) -> dict:
  raw_skills, tech_stack, certificates, education = [], [], [], []
  for e in entities:
    if not isinstance(e, dict):
      continue
    t, name = e.get("type"), e.get("name")
    if not name or t == "position":
      continue
    if t == "skill" and name not in raw_skills:
      raw_skills.append(name)
    elif t == "tech_stack" and name not in tech_stack:
      tech_stack.append(name)
    elif t == "certificate" and name not in certificates:
      certificates.append(name)
    elif t == "education" and name not in education:
      education.append(name)

  return {
      "raw_skills": ";".join(raw_skills) if raw_skills else None,
      "tech_stack": ";".join(tech_stack) if tech_stack else None,
      "certificates": (
          ";".join(certificates) if certificates else "无硬性要求"
      ),
      "education": ";".join(education) if education else None,
  }


def process_single_jd_logic(
    job_title: str, responsibilities: str, requirements: str, raw_text: str
) -> dict:
  if raw_text and raw_text.strip():
    text_input = raw_text.strip()
  else:
    parts = [p for p in [job_title, responsibilities, requirements] if p]
    text_input = "\n".join(parts)

  job_title_def = job_title if job_title else "岗位"

  if not text_input.strip():
    parsed = {
        "entities": [],
        "relations": [],
        "events": [],
        "overall_confidence": 0.0,
        "needs_human_review": True,
    }
  else:
    llm = ChatOpenAI(
        api_key=LLM_CONFIG["api_key"],
        base_url=LLM_CONFIG["base_url"],
        model=LLM_CONFIG["model_name"],
        temperature=0.0,
    )
    prompt_template = build_prompt_template()

    retrieved_skills = rag_service.get_reference_skills(text_input, top_k=8)
    rag_skills_str = ", ".join(retrieved_skills) if retrieved_skills else "无"

    chain = prompt_template | llm
    res = chain.invoke({"text": text_input, "rag_skills": rag_skills_str})

    parsed = clean_and_normalize_json(
        res.content, job_title_default=job_title_def, raw_input_full=text_input
    )

  derived = derive_helper_fields(parsed["entities"])
  quality_issues = (
      ["Low entity recall"] if parsed["needs_human_review"] else []
  )

  return {
      "entities": parsed["entities"],
      "relations": parsed["relations"],
      "events": parsed["events"],
      "overall_confidence": parsed["overall_confidence"],
      "needs_human_review": parsed["needs_human_review"],
      "quality_issues": quality_issues,
      "derived_fields": derived,
  }


# ==============================================================================
# 4. FastAPI 应用与 API 路由声明
# ==============================================================================

app = FastAPI(
    title="HR 知识图谱信息抽取服务",
    description="支持即时单条图谱抽取、批量 Excel 解析与 RAG 向量检索",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", summary="服务健康状态检查")
async def health_check():
  return {
      "status": "online",
      "time": datetime.now(TZ_SHANGHAI).strftime("%Y-%m-%d %H:%M:%S"),
  }


@app.post(
    "/api/extraction/extract",
    response_model=SingleExtractResponse,
    summary="单条 JD 实时图谱抽取",
)
async def extract_single_jd(req: SingleExtractRequest):
  """前端联调接口：提交 JD 文本，实时返回图谱 JSON"""
  try:
    result = process_single_jd_logic(
        job_title=req.job_title,
        responsibilities=req.responsibilities,
        requirements=req.requirements,
        raw_text=req.raw_text,
    )
    return SingleExtractResponse(
        code=200, message="success", data=ExtractionResponseData(**result)
    )
  except Exception as e:
    raise HTTPException(status_code=500, detail=f"图谱抽取失败: {str(e)}")


@app.post("/api/extraction/batch-file", summary="批量 Excel 文件异步抽取")
async def extract_batch_file(file: UploadFile, workers: int = 5):
  """离线处理接口：上传 Excel 批量解析"""
  if not file.filename.endswith((".xlsx", ".xls")):
    raise HTTPException(
        status_code=400, detail="仅支持上传 .xlsx 或 .xls 格式文件"
    )

  try:
    df = pd.read_excel(file.file)
  except Exception as e:
    raise HTTPException(status_code=400, detail=f"Excel 解析异常: {str(e)}")

  def run_batch_job(data_frame: pd.DataFrame, max_workers: int):
    results_map = {}

    def row_worker(idx_row):
      idx, row = idx_row
      title = str(row.get("job_title", "岗位"))
      resp = str(row.get("responsibilities", ""))
      req = str(row.get("requirements", ""))
      raw = (
          str(row.get("raw_text", ""))
          if pd.notna(row.get("raw_text"))
          else None
      )
      return idx, process_single_jd_logic(title, resp, req, raw)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
      futures = [
          executor.submit(row_worker, (idx, row))
          for idx, row in data_frame.iterrows()
      ]
      for f in as_completed(futures):
        idx, res = f.result()
        results_map[idx] = res
    print(f"🎉 批量分析已完成，共处理 {len(data_frame)} 条记录。")

  return {
      "code": 200,
      "message": (
          f"已接收批量提取任务，文件包含 {len(df)} 条，并发线程数: {workers}"
      ),
  }


@app.post("/api/extraction/init-rag", summary="手动触发 Milvus 词库建库初始化")
async def trigger_rag_init():
  """在 API 网页端一键创建/刷新 Milvus 标准技能向量数据库"""
  try:
    init_milvus_collection()
    return {"code": 200, "message": "Milvus 种子词库初始化成功！"}
  except Exception as e:
    raise HTTPException(status_code=500, detail=f"向量数据库初始化失败: {str(e)}")


# ==============================================================================
# 5. 主程序启动入口
# ==============================================================================

if __name__ == "__main__":
  uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
