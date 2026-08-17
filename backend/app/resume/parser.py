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
import os
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


def _extract_json(text: str) -> dict | None:
    """从 LLM 输出中尽力提取 JSON 对象（容忍 ```json 包裹或前后多余文字）。"""
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            pass
    return None


def _pick(raw: dict, *keys: str):
    """从字典中按顺序取第一个非空字段值。"""
    for key in keys:
        value = raw.get(key)
        if value:
            return value
    return None


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

    confidence = float(raw.get("confidence", 0.8))
    confidence = max(0.0, min(1.0, confidence))

    return ParsedResume(
        id="",
        file_name=file_name,
        name=str(_pick(raw, "name", "姓名") or "").strip(),
        email=_pick(raw, "email", "邮箱"),
        phone=_pick(raw, "phone", "contact_number", "phone_number", "电话", "手机号", "联系电话"),
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

    async def parse(self, resume_text: str, file_name: str = "unknown", to_dir:bool = False, json_file_path:str = None) -> ParsedResume:
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

        # lite 模型偶发不按 JSON 输出，解析为空时用更强指令重试一次
        prompts = [
            self.system_prompt,
            self.system_prompt
            + "\n\n【重要】你必须只输出一个合法 JSON 对象，不要输出 ```json 代码块标记，"
              "也不要输出 JSON 之外的任何文字。",
        ]
        for attempt, prompt in enumerate(prompts):
            content = await self._request_llm(prompt, payload)
            if content is None:
                continue
            parsed = self._parse_response(content, file_name, to_dir, json_file_path)
            if (
                parsed.name
                or parsed.email
                or parsed.phone
                or parsed.skills
                or parsed.education
                or parsed.work_experience
            ):
                return parsed
            logger.warning("第 %d 次解析结果为空，准备重试", attempt + 1)

        return self._empty(file_name)

    async def _request_llm(self, system_prompt: str, payload: str) -> str | None:
        """调用 Spark Lite，成功返回文本，失败返回 None。"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": payload},
            ],
            "temperature": 0.1,
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self.api_url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception:
            logger.exception("LLM 请求失败")
            return None

    @staticmethod
    def _empty(file_name: str) -> ParsedResume:
        return ParsedResume(
            id="",
            file_name=file_name,
            parsed_at=datetime.now(timezone.utc).isoformat(),
            confidence=0.0,
        )

    def _parse_response(self, content: str, file_name: str, to_dir:bool = False, json_file_path:str = None) -> ParsedResume:
        """将 LLM 文本响应反序列化为 ParsedResume。"""
        text = _strip_json_fence(content)
        text = _sanitize_json_string(text)

        raw = _extract_json(text)
        if raw is None:
            logger.warning("LLM 返回非 JSON 内容，前 300 字符: %s", content[:300])
            return ParsedResume(
                id="",
                file_name=file_name,
                parsed_at=datetime.now(timezone.utc).isoformat(),
                confidence=0.0,
            )

        if to_dir and json_file_path is not None:
            with open(json_file_path, 'w', encoding='utf-8') as json_file:
                json.dump(raw, json_file, indent=4, ensure_ascii=False)

        

        return _build_parsed_resume(raw, file_name)



## 测试
if __name__ == "__main__":
    import asyncio
    import sys
    from pathlib import Path
    from app.resume.extractor import ResumeContentExtractor

    # ---------- 配置 ----------
    INPUT_DIR = "C:\\Users\\14005\\Desktop\\2022级应届生简历情况\\2022级应届生简历情况"          # 待处理文件夹
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # 项目根目录
    OUTPUT_DIR = PROJECT_ROOT / "data" / "resume_json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MAX_CONCURRENT = 3
    print(f"最大并发数: {MAX_CONCURRENT}")

    # ---------- 收集待处理文件 ----------
    file_paths = []
    for entry in Path(INPUT_DIR).iterdir():
        if entry.is_file():
            file_paths.append(entry)
    if not file_paths:
        print("输入文件夹中没有文件，程序退出。")
        sys.exit(0)
    print(f"共发现 {len(file_paths)} 个文件待处理。")

    # ---------- 异步任务函数 ----------
    async def process_one(file_path: Path, extractor, parser, output_dir: Path, semaphore: asyncio.Semaphore):
        """处理单个文件，受信号量控制并发"""
        async with semaphore:
            print(f"开始处理: {file_path.name}")
            try:
                # 1. 同步提取文本（若需避免阻塞，可改用 run_in_executor）
                raw_text = extractor.extract(str(file_path))

                # 2. 构造输出 JSON 路径
                output_json = output_dir / f"{file_path.stem}.json"

                # 3. 异步解析
                parsed_data = await parser.parse(
                    raw_text,
                    file_name=file_path.name,
                    to_dir=True,
                    json_file_path=str(output_json)
                )
                print(f"✅ 完成: {file_path.name} -> {output_json}")
                return True
            except Exception as e:
                print(f"❌ 处理 {file_path.name} 时出错: {e}")
                return False

    # ---------- 主异步入口 ----------
    async def main():
        extractor = ResumeContentExtractor()
        parser = ResumeLLMParser()
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        tasks = [
            process_one(fp, extractor, parser, OUTPUT_DIR, semaphore)
            for fp in file_paths
        ]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        success_count = sum(1 for r in results if r is True)
        fail_count = len(results) - success_count
        print(f"全部处理完成：成功 {success_count}，失败 {fail_count}")

    # 启动事件循环
    asyncio.run(main())