"""简历解析模块 —— 文件上传（PDF/DOCX）、文本提取、LLM 结构化解析、MongoDB 存储。

Pipeline:
1. ResumeContentExtractor  → PDF/DOCX 文字提取 + 正则化 (extractor.py)
2. ResumeLLMParser        → LLM few-shot 结构化抽取 → ParsedResume (parser.py)
3. ResumeParsingService   → 编排提取/解析/存储全流程 (service.py)"""

from app.resume.extractor import ResumeContentExtractor, normalize_text
from app.resume.parser import ResumeLLMParser
from app.resume.service import ResumeParsingService

__all__ = [
    "normalize_text",
    "ResumeContentExtractor",
    "ResumeLLMParser",
    "ResumeParsingService",
]