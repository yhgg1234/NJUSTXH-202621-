"""数据清洗服务 —— 包装 src 数据预处理流水线，暴露给 REST API。

流水线是文件级的（输入 Excel/CSV → 输出 final_dataset.xlsx + 报告），
这里将其包装为记录级服务：运行流水线后把结果读进内存，供查询/校验接口使用。
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 让 src 包（数据清洗流水线）和 data_pipeline/config.py 可被导入
_BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent  # 项目根目录
if str(_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_DIR))
if str(_BASE_DIR / "data_pipeline") not in sys.path:
    sys.path.insert(0, str(_BASE_DIR / "data_pipeline"))


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value != value:  # NaN
        return ""
    return str(value).strip()


class DataCleaningService:
    """运行清洗流水线并缓存最近一次结果。"""

    def __init__(self) -> None:
        self._output_dir = Path(_BASE_DIR) / "data" / "processed" / "cleaning"
        self._result: dict[str, Any] | None = None
        self._tasks: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # 运行流水线
    # ------------------------------------------------------------------

    def run(self, file_path: str) -> dict[str, Any]:
        """对给定文件执行完整流水线，返回总结报告。"""
        from src.pipeline import DataPreprocessingPipeline

        pipeline = DataPreprocessingPipeline(output_dir=str(self._output_dir))
        pipeline.run(input_file=file_path)

        summary = self._read_json("summary_report.json") or {}
        records = self._read_excel_records("final_dataset.xlsx")
        review_items = self._read_excel_records("needs_human_review.xlsx")

        self._result = {
            "summary": summary,
            "records": records,
            "review_items": review_items,
        }

        task_id = uuid.uuid4().hex[:12]
        data_flow = summary.get("data_flow", {})
        task = {
            "id": task_id,
            "input_count": int(data_flow.get("original", 0)),
            "output_count": int(data_flow.get("final", len(records))),
            "dedup_removed": int(data_flow.get("after_cleaning", 0)) - int(data_flow.get("after_deduplication", 0)),
            "noise_removed": int(data_flow.get("original", 0)) - int(data_flow.get("after_cleaning", 0)),
            "status": "completed",
            "summary": summary,
        }
        self._tasks.append(task)
        return task

    def run_from_collection(self) -> dict[str, Any]:
        """直接从数据采集的最近一次结果运行清洗流水线。"""
        from app.data_collection.service import get_collection_service

        latest_file = get_collection_service().get_latest_collected_file()
        if not latest_file:
            raise ValueError("还没有采集数据，请先到「数据采集」页运行一次采集")
        return self.run(latest_file)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_summary(self) -> dict[str, Any] | None:
        return (self._result or {}).get("summary")

    def list_records(self, page: int, page_size: int, keyword: str | None = None) -> tuple[list[dict], int]:
        records = (self._result or {}).get("records", [])
        if keyword:
            kw = keyword.lower()
            records = [
                r for r in records
                if kw in str(r.get("job_title", "")).lower()
                or kw in str(r.get("company", "")).lower()
                or kw in str(r.get("raw_skills", "")).lower()
                or kw in str(r.get("tech_stack", "")).lower()
            ]
        total = len(records)
        start = (page - 1) * page_size
        items = records[start : start + page_size]
        return [self._to_dataset_item(r) for r in items], total

    def list_quality_items(self) -> list[dict]:
        return [self._to_quality_item(r) for r in (self._result or {}).get("review_items", [])]

    def get_defaults(self) -> dict[str, Any]:
        from data_pipeline.config import (  # noqa: F401
            CLEANING_CONFIG,
            DEDUPLICATION_CONFIG,
            SPLIT_CONFIG,
        )

        return {
            "dedup_method": "simhash",
            "dedup_threshold": DEDUPLICATION_CONFIG.simhash_threshold,
            "remove_noise": True,
            "normalize": True,
            "human_review": True,
            "split": {
                "train_ratio": SPLIT_CONFIG.train_ratio,
                "val_ratio": SPLIT_CONFIG.val_ratio,
                "test_ratio": SPLIT_CONFIG.test_ratio,
            },
        }

    def list_tasks(self) -> list[dict[str, Any]]:
        return self._tasks

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        return next((t for t in self._tasks if t["id"] == task_id), None)

    def get_raw_records(self) -> list[dict[str, Any]]:
        """返回清洗后的原始记录（含 job_title/responsibilities/requirements 等列），供信息抽取消费。"""
        return (self._result or {}).get("records", [])

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _to_dataset_item(self, row: dict[str, Any]) -> dict[str, Any]:
        tags: list[str] = []
        for key in ("tech_stack", "raw_skills", "extracted_skills"):
            value = _clean(row.get(key))
            for part in re.split(r"[;,、，/]+", value):
                part = part.strip()
                if part and part not in tags:
                    tags.append(part)
        return {
            "id": _clean(row.get("jd_id")) or uuid.uuid4().hex[:12],
            "title": _clean(row.get("job_title")) or "（无岗位名）",
            "content": _clean(row.get("responsibilities")) or _clean(row.get("requirements")),
            "source_name": _clean(row.get("company")) or _clean(row.get("source_platform")),
            "cleaned_at": _clean(row.get("collection_time")),
            "quality_score": self._to_float(row.get("quality_score")),
            "tags": tags[:8],
        }

    def _to_quality_item(self, row: dict[str, Any]) -> dict[str, Any]:
        issues: list[str] = []
        issues_json = _clean(row.get("quality_issues_json"))
        if issues_json:
            try:
                parsed = json.loads(issues_json)
                if isinstance(parsed, list):
                    issues.extend(str(item) for item in parsed if str(item).strip())
                elif isinstance(parsed, dict):
                    issues.extend(str(v) for v in parsed.values() if str(v).strip())
            except (json.JSONDecodeError, TypeError):
                pass
        if row.get("contains_inflation"):
            issues.append("含通胀词汇")
        if row.get("is_stale"):
            issues.append("数据可能过时")
        if row.get("quality_score") is not None and float(row.get("quality_score")) < 0.6:
            issues.append("质量评分偏低")
        return {
            "id": _clean(row.get("jd_id")) or uuid.uuid4().hex[:12],
            "original_text": _clean(row.get("requirements")) or _clean(row.get("responsibilities")),
            "cleaned_text": _clean(row.get("responsibilities")),
            "issues": issues,
        }

    @staticmethod
    def _to_float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _read_json(self, name: str) -> dict[str, Any] | None:
        path = self._output_dir / name
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _read_excel_records(self, name: str) -> list[dict[str, Any]]:
        path = self._output_dir / name
        if not path.exists():
            return []
        import pandas as pd

        df = pd.read_excel(path)
        return df.to_dict(orient="records")


_service: DataCleaningService | None = None


def get_cleaning_service() -> DataCleaningService:
    global _service
    if _service is None:
        _service = DataCleaningService()
    return _service
