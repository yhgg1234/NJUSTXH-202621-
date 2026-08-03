"""简历结构化解析模块 —— 利用 LLM 将文本抽取为 ParsedResume JSON。

工作流程:
1. 接收 extractor 输出的纯文本
2. 拼装 few-shot 系统提示词（见 prompt_parser.txt）
3. 调用 OpenAI 兼容接口（DeepSeek / Spark Lite）获取 JSON
4. 清洗、校验并将结果反序列化为 ParsedResume 模型
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.resume.models import Education, ParsedResume, ProjectExperience, WorkExperience

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Few-shot 系统提示词
# ---------------------------------------------------------------------------

_DEFAULT_SYSTEM_PROMPT = """你是一位专业的简历解析助手。给你一份简历原文，请提取以下字段并严格输出 JSON:

字段说明:
- name: 姓名
- email: 邮箱
- phone: 手机号
- education: 数组，每项包含 school(学校), degree(学位), major(专业), start_date, end_date
- work_experience: 数组，每项包含 company(公司), position(职位), start_date, end_date, description(工作描述), achievements(工作成果,字符串数组)
- projects: 数组，每项包含 name(项目名), role(角色), start_date, end_date, description(描述), tech_stacks(技术栈数组), achievements(成果数组)
- skills: 技能字符串数组(具体技术,如 Python、FastAPI、Kubernetes、RAG 等)
- certificates: 证书字符串数组
- languages: 语言字符串数组
- confidence: 0-1 之间的置信度

规则:
1. 未找到的字段用空字符串、空数组或 null;education/work_experience/projects 至少是空数组
2. 日期统一为 YYYY-MM 或 YYYY-MM-DD 格式;不可推断时为 null
3. 技能必须精确到框架/工具/方法级别,不要输出宽泛词如"计算机能力"
4. 只输出 JSON,不要带 ```json 标记或额外解释

示例输入:
张三
zhangsan@example.com | 13800138000
教育经历: 清华大学 计算机科学与技术 硕士 2020-2023
工作经历: 字节跳动 后端开发工程师 2023-至今 负责推荐系统后端服务开发
技能: Python, Go, Kubernetes, Docker, MySQL, Redis

示例输出:
{
  "name": "张三",
  "email": "zhangsan@example.com",
  "phone": "13800138000",
  "education": [{"school":"清华大学","degree":"硕士","major":"计算机科学与技术","start_date":"2020-09","end_date":"2023-06"}],
  "work_experience": [{"company":"字节跳动","position":"后端开发工程师","start_date":"2023-07","end_date":null,"description":"负责推荐系统后端服务开发","achievements":[]}],
  "projects": [],
  "skills": ["Python","Go","Kubernetes","Docker","MySQL","Redis"],
  "certificates": [],
  "languages": [],
  "confidence": 0.95
}"""


def _strip_json_fence(content: str) -> str:
    """去除 LLM 输出外层 ```json ... ``` 标记。"""
    text = content.strip()
    if text.startswith("```json"):
        text = text.removeprefix("```json").strip()
    elif text.startswith("```"):
        text = text.removeprefix("```").strip()
    if text.endswith("```"):
        text = text.removesuffix("```").strip()
    return text


def _sanitize_json_string(text: str) -> str:
    """处理 LLM 输出中常见的 JSON 语法问题。"""
    text = re.sub(r",\s*(\]|\})", r"\1", text)
    return text


def _build_parsed_resume(raw: dict, file_name: str) -> ParsedResume:
    """将 LLM 返回的字典安全转换为 ParsedResume。"""

    def _to_education_list(items: list) -> list[Education]:
        results: list[Education] = []
        for item in items or []:
            try:
                results.append(Education(
                    school=str(item.get("school", "")),
                    degree=str(item.get("degree", "")),
                    major=str(item.get("major", "")),
                    start_date=item.get("start_date"),
                    end_date=item.get("end_date"),
                ))
            except Exception:
                logger.debug("跳过无效教育经历条目: %s", item)
        return results

    def _to_work_list(items: list) -> list[WorkExperience]:
        results: list[WorkExperience] = []
        for item in items or []:
            try:
                results.append(WorkExperience(
                    company=str(item.get("company", "")),
                    position=str(item.get("position", "")),
                    start_date=item.get("start_date"),
                    end_date=item.get("end_date"),
                    description=str(item.get("description", "")),
                    achievements=list(item.get("achievements") or []),
                ))
            except Exception:
                logger.debug("跳过无效工作经历条目: %s", item)
        return results

    def _to_project_list(items: list) -> list[ProjectExperience]:
        results: list[ProjectExperience] = []
        for item in items or []:
            try:
                results.append(ProjectExperience(
                    name=str(item.get("name", "")),
                    role=str(item.get("role", "")),
                    start_date=item.get("start_date"),
                    end_date=item.get("end_date"),
                    description=str(item.get("description", "")),
                    tech_stacks=list(item.get("tech_stacks") or []),
                    achievements=list(item.get("achievements") or []),
                ))
            except Exception:
                logger.debug("跳过无效项目经验条目: %s", item)
        return results

    confidence = float(raw.get("confidence", 0))
    confidence = max(0.0, min(1.0, confidence))

    return ParsedResume(
        id="",
        file_name=file_name,
        name=str(raw.get("name", "")).strip(),
        email=raw.get("email"),
        phone=raw.get("phone"),
        education=_to_education_list(raw.get("education") or []),
        work_experience=_to_work_list(raw.get("work_experience") or []),
        projects=_to_project_list(raw.get("projects") or []),
        skills=[str(s) for s in (raw.get("skills") or [])],
        certificates=[str(c) for c in (raw.get("certificates") or [])],
        languages=[str(l) for l in (raw.get("languages") or [])],
        parsed_at=datetime.now(timezone.utc).isoformat(),
        confidence=confidence,
    )


class ResumeLLMParser:
    """简历 LLM 解析器 —— 异步调用兼容 OpenAI 接口的大模型做结构化抽取。"""

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        system_prompt: str | None = None,
    ) -> None:
        self.api_url = api_url if api_url is not None else settings.LLM_API_URL
        self.api_key = api_key if api_key is not None else settings.LLM_API_KEY
        self.model = model if model is not None else settings.LLM_MODEL
        self.system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT

    @property
    def enabled(self) -> bool:
        return bool(self.api_url and self.api_key)

    async def parse(self, resume_text: str, file_name: str = "unknown") -> ParsedResume:
        """异步解析简历文本为结构化 ParsedResume。

        Args:
            resume_text: 清洗后的简历纯文本。
            file_name: 原始文件名（用于 ParsedResume.file_name）。

        Returns:
            ParsedResume: 解析结果。LLM 不可用时返回仅含 file_name 的空骨架。
        """
        if not self.enabled:
            logger.warning("LLM 未配置，返回空解析结果")
            return ParsedResume(
                id="",
                file_name=file_name,
                parsed_at=datetime.now(timezone.utc).isoformat(),
                confidence=0.0,
            )

        if not resume_text.strip():
            logger.warning("简历文本为空，跳过 LLM 调用")
            return ParsedResume(
                id="",
                file_name=file_name,
                parsed_at=datetime.now(timezone.utc).isoformat(),
                confidence=0.0,
            )

        max_chars = 4000
        payload = resume_text[:max_chars]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": payload},
            ],
            "temperature": 0.1,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    json=body,
                )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except Exception:
            logger.exception("LLM 请求失败")
            return ParsedResume(
                id="",
                file_name=file_name,
                parsed_at=datetime.now(timezone.utc).isoformat(),
                confidence=0.0,
            )

        return self._parse_response(content, file_name)

    def _parse_response(self, content: str, file_name: str) -> ParsedResume:
        """将 LLM 文本响应反序列化为 ParsedResume。"""
        text = _strip_json_fence(content)
        text = _sanitize_json_string(text)

        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("LLM 返回非 JSON 内容，前 300 字符: %s", content[:300])
            return ParsedResume(
                id="",
                file_name=file_name,
                parsed_at=datetime.now(timezone.utc).isoformat(),
                confidence=0.0,
            )

        if not isinstance(raw, dict):
            logger.warning("LLM 返回非字典 JSON: %s", type(raw))
            return ParsedResume(
                id="",
                file_name=file_name,
                parsed_at=datetime.now(timezone.utc).isoformat(),
                confidence=0.0,
            )

        return _build_parsed_resume(raw, file_name)


if __name__ == "__main__":
    import asyncio
    from app.resume.extractor import ResumeContentExtractor

    path = "C:\\Users\\14005\\Desktop\\data\\辛佳颖简历.pdf"
    extractor = ResumeContentExtractor()
    raw_txt = extractor.extract(path)
    parseror = ResumeLLMParser()
    parsered_data = asyncio.run(parseror.parse(raw_txt))
    print(parsered_data)