"""简历解析服务 —— 串联文本提取 → LLM 解析 → 存储的完整 pipeline。"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiofiles
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from app.config import settings
from app.resume.extractor import ResumeContentExtractor
from app.resume.models import ParsedResume, ResumeUploadResponse
from app.resume.parser import ResumeLLMParser

logger = logging.getLogger(__name__)


class ResumeParsingService:
    """简历解析服务 —— 端到端简历处理。

    职责:
    - 管理文件保存、文本提取、LLM 解析、结果存储
    - 提供单文件和批量解析接口
    - 降级策略：LLM 不可用时仍保存原始文本和文件元数据
    """

    def __init__(
        self,
        extractor: ResumeContentExtractor | None = None,
        parser: ResumeLLMParser | None = None,
        mongo_client: AsyncIOMotorClient | None = None,
        upload_dir: str | None = None,
    ) -> None:
        self.extractor = extractor or ResumeContentExtractor()
        self.parser = parser or ResumeLLMParser()
        self.upload_dir = Path(
            upload_dir
            or (
                Path(__file__).resolve().parent.parent.parent.parent
                / "data"
                / "raw"
                / "resumes"
            )
        )
        self.upload_dir.mkdir(parents=True, exist_ok=True)

        # MongoDB 异步连接
        mongo = mongo_client or AsyncIOMotorClient(settings.MONGO_URI)
        self.db = mongo[settings.MONGO_DATABASE]
        self.collection: Collection = self.db["resumes"]

    # ------------------------------------------------------------------
    # 文件管理
    # ------------------------------------------------------------------

    async def _save_uploaded_file(
        self, content: bytes, original_name: str
    ) -> tuple[str, Path, int]:
        """保存上传文件到磁盘（异步），返回 (file_id, 存储路径, 文件大小)。"""
        file_id = uuid.uuid4().hex[:12]
        # 按年月分区存储
        month_dir = datetime.now(timezone.utc).strftime("%Y/%m")
        target_dir = self.upload_dir / month_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        # 保留原始扩展名
        suffix = Path(original_name).suffix.lower()
        stored_name = f"{file_id}{suffix}"
        stored_path = target_dir / stored_name

        async with aiofiles.open(stored_path, "wb") as f:
            await f.write(content)
        logger.info("文件已保存: %s (size=%d)", stored_path, len(content))

        return file_id, stored_path, len(content)

    # ------------------------------------------------------------------
    # 核心解析 pipeline
    # ------------------------------------------------------------------

    async def parse_single(
        self,
        file_content: bytes,
        original_name: str,
    ) -> ParsedResume:
        """解析单个简历文件，返回结构化 ParsedResume。

        流水线:
        1. 保存文件到磁盘
        2. 文本提取 (ResumeContentExtractor)
        3. LLM 结构化解析 (ResumeLLMParser)
        4. 存入 MongoDB
        5. 返回 ParsedResume（已分配 ID）
        """
        # 1. 保存文件
        file_id, stored_path, file_size = await self._save_uploaded_file(
            file_content, original_name
        )

        # 2. 提取文本
        try:
            cleaned_text = self.extractor.extract(stored_path)
        except Exception:
            logger.exception("文本提取失败: %s", stored_path)
            # 保存空解析记录
            fallback = ParsedResume(
                id=file_id,
                file_name=original_name,
                parsed_at=datetime.now(timezone.utc).isoformat(),
                confidence=0.0,
            )
            await self._store_resume(fallback, stored_path, file_size)
            return fallback

        # 3. LLM 解析
        parsed = await self.parser.parse(cleaned_text, original_name)
        parsed.id = file_id  # 注入 file_id

        # 4. 持久化
        await self._store_resume(parsed, stored_path, file_size)

        return parsed

    async def parse_batch(
        self,
        files: list[tuple[bytes, str]],
    ) -> list[ParsedResume]:
        """批量解析简历。

        Args:
            files: [(二进制内容, 原始文件名), ...]

        Returns:
            按输入顺序的 ParsedResume 列表。
        """
        results: list[ParsedResume] = []
        for content, name in files:
            try:
                result = await self.parse_single(content, name)
            except Exception:
                logger.exception("批量解析中跳过失败文件: %s", name)
                result = ParsedResume(
                    id="",
                    file_name=name,
                    parsed_at=datetime.now(timezone.utc).isoformat(),
                    confidence=0.0,
                )
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # MongoDB 持久化
    # ------------------------------------------------------------------

    async def _store_resume(
        self,
        parsed: ParsedResume,
        stored_path: Path,
        file_size: int,
    ) -> None:
        """将解析结果写入 MongoDB（异步）。"""
        doc = {
            "resume_id": parsed.id,
            "file_name": parsed.file_name,
            "file_path": str(stored_path),
            "file_size": file_size,
            "parsed_data": parsed.model_dump(),
            "created_at": datetime.now(timezone.utc),
        }
        try:
            await self.collection.insert_one(doc)
            logger.info("简历已存入 MongoDB: resume_id=%s", parsed.id)
        except PyMongoError:
            logger.exception("MongoDB 写入失败: resume_id=%s", parsed.id)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    async def get_resume(self, resume_id: str) -> ParsedResume | None:
        """按 ID 查询单份解析结果（异步）。"""
        try:
            doc = await self.collection.find_one({"resume_id": resume_id})
        except PyMongoError:
            logger.exception("MongoDB 查询失败: resume_id=%s", resume_id)
            return None

        if not doc:
            return None

        return ParsedResume(**doc["parsed_data"])

    async def list_resumes(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ParsedResume], int]:
        """分页查询简历列表（异步）。

        Returns:
            (简历列表, 总数)
        """
        try:
            total = await self.collection.count_documents({})
            cursor = (
                self.collection.find({})
                .sort("created_at", -1)
                .skip((page - 1) * page_size)
                .limit(page_size)
            )
            items = [ParsedResume(**doc["parsed_data"]) async for doc in cursor]
        except PyMongoError:
            logger.exception("MongoDB 列表查询失败")
            return [], 0

        return items, total

    async def delete_resume(self, resume_id: str) -> bool:
        """删除简历（MongoDB + 磁盘文件）（异步）。"""
        try:
            doc = await self.collection.find_one({"resume_id": resume_id})
        except PyMongoError:
            logger.exception("MongoDB 查询失败: resume_id=%s", resume_id)
            return False

        if not doc:
            return False

        # 删除磁盘文件
        file_path = Path(doc.get("file_path", ""))
        if file_path.exists():
            try:
                file_path.unlink()
                logger.info("已删除磁盘文件: %s", file_path)
            except OSError:
                logger.warning("删除磁盘文件失败: %s", file_path)

        # 删除 MongoDB 记录
        try:
            await self.collection.delete_one({"resume_id": resume_id})
        except PyMongoError:
            logger.exception("MongoDB 删除失败: resume_id=%s", resume_id)
            return False

        return True

    async def search_resumes(
        self,
        keyword: str | None = None,
        skills: list[str] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ParsedResume], int]:
        """高级检索简历（按关键词或技能）（异步）。"""
        query: dict = {}

        if keyword:
            query["$or"] = [
                {"parsed_data.name": {"$regex": keyword, "$options": "i"}},
                {"parsed_data.skills": {"$regex": keyword, "$options": "i"}},
                {
                    "parsed_data.work_experience.position": {
                        "$regex": keyword,
                        "$options": "i",
                    }
                },
                {
                    "parsed_data.work_experience.company": {
                        "$regex": keyword,
                        "$options": "i",
                    }
                },
            ]

        if skills:
            query["parsed_data.skills"] = {"$all": skills}

        try:
            total = await self.collection.count_documents(query)
            cursor = (
                self.collection.find(query)
                .sort("created_at", -1)
                .skip((page - 1) * page_size)
                .limit(page_size)
            )
            items = [ParsedResume(**doc["parsed_data"]) async for doc in cursor]
        except PyMongoError:
            logger.exception("MongoDB 搜索失败")
            return [], 0

        return items, total