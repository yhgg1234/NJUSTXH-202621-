"""简历文字抽取模块 —— 支持 PDF、DOCX 等格式的文档文字提取与正则化。

工作流程:
1. ResumeContentExtractor 接收文件路径，校验文件存在性与类型
2. 按 MIME 类型分发到具体提取器（PyMuPDF / python-docx）
3. 对提取后的文本做正则化清洗，输出纯文本字符串
"""

from __future__ import annotations

import io
import logging
import mimetypes
import re
from pathlib import Path

import fitz  # PyMuPDF
from docx import Document

logger = logging.getLogger(__name__)



_SUPPORTED_MIME: dict[str, str] = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}

_SUPPORTED_EXTENSIONS: set[str] = {".pdf", ".docx"}


def _normalize_whitespace(text: str) -> str:
    """合并连续空白行，去除零宽字符和不可见控制符。"""
    # 保留常见的换行与制表符，将其它 ASCII 控制符转空格
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", " ", text)
    # 零宽字符
    text = re.sub(r"[\u200b-\u200f\u2028-\u202f\u00a0]", " ", text)
    # 连续 ≥3 个换行合并为 2 个
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 行尾空白
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    return text.strip()


def _normalize_punctuation(text: str) -> str:
    """统一中文标点和常见排版符号。"""
    # 全角括号 / 逗号 / 冒号 → 半角（数字与英文环境）
    replacements = {
        "\u3000": " ",  # 全角空格
        "\uff0c": ",",  # ，
        "\uff1a": ":",  # ：
        "\uff08": "(",  # （
        "\uff09": ")",  # ）
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def normalize_text(text: str) -> str:
    """对抽取出的简历文本做规范化清洗。"""
    text = _normalize_whitespace(text)
    text = _normalize_punctuation(text)
    return text


class _PDFExtractor:
    """基于 PyMuPDF 的 PDF 文本提取。"""

    def extract(self, file_path: Path) -> str:
        doc = fitz.open(str(file_path))
        try:
            pages: list[str] = []
            for page in doc:
                pages.append(page.get_text())
            return "\n".join(pages)
        finally:
            doc.close()


class _DocxExtractor:
    """基于 python-docx 的 Word 文本提取。"""

    def extract(self, file_path: Path) -> str:
        doc = Document(str(file_path))
        paragraphs: list[str] = []
        for paragraph in doc.paragraphs:
            text = paragraph.text
            if text.strip():
                paragraphs.append(text)
        return "\n".join(paragraphs)


class ResumeContentExtractor:
    """简历文本抽取器 —— 自动判断格式并提取纯文本。

    Usage::

        extractor = ResumeContentExtractor()
        text = extractor.extract("resume.pdf")
    """

    def __init__(self) -> None:
        self._extractors: dict[str, object] = {
            "pdf": _PDFExtractor(),
            "docx": _DocxExtractor(),
        }

    # ------------------------------------------------------------------
    # file‑type detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_type(file_path: Path) -> str:
        """通过扩展名与 MIME 双重检测返回 'pdf' / 'docx'；未知时抛异常。"""
        if file_path.suffix.lower() in _SUPPORTED_EXTENSIONS:
            return file_path.suffix.lower()[1:]  # 去掉点号

        # 部分文件可能不带扩展名，回退 MIME
        mime, _ = mimetypes.guess_type(str(file_path))
        if mime and mime in _SUPPORTED_MIME:
            return _SUPPORTED_MIME[mime]

        raise ValueError(
            f"不支持的文件类型: {file_path.suffix or '(无扩展名)'}。"
            f"当前支持: {sorted(_SUPPORTED_EXTENSIONS)}"
        )

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def extract(self, file_path: str | Path) -> str:
        """提取简历文件全文并返回规范化纯文本。

        Args:
            file_path: PDF 或 DOCX 文件的路径。

        Returns:
            清洗后的文字内容。

        Raises:
            FileNotFoundError: 文件不存在。
            ValueError: 文件类型不支持。
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")

        doc_type = self._detect_type(path)
        logger.info("开始提取简历文本: %s (类型=%s)", path.name, doc_type)

        try:
            raw_text = self._extractors[doc_type].extract(path)
        except Exception:
            logger.exception("文本提取失败: %s", path)
            raise

        cleaned = normalize_text(raw_text)
        logger.info(
            "简历文本提取完成: %s, 原始长度=%d, 清洗后长度=%d",
            path.name,
            len(raw_text),
            len(cleaned),
        )
        return cleaned


if __name__ =="__main__":
    path = "C:\\Users\\14005\\Desktop\\data\\巩秋实简历.pdf"
    extractor = ResumeContentExtractor()
    txt = extractor.extract(path)
    print(txt)