"""数据采集服务 —— 包装合规爬虫框架，暴露给 REST API。

爬虫是文件级 CLI（jd_crawler.py），这里将其包装为记录级服务：
按数据源（adapter）运行采集 + 导出契约版 xlsx，结果读进内存供查询。
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_CRAWLER_DIR = Path(__file__).resolve().parent / "crawler"
if str(_CRAWLER_DIR) not in sys.path:
    sys.path.insert(0, str(_CRAWLER_DIR))

_BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent  # 项目根目录

# 内置数据源（对应爬虫 adapter）
_SOURCES = [
    {
        "id": "public_search_demo",
        "name": "国聘（演示数据源）",
        "type": "recruit_platform",
        "url": None,
        "description": "内置 mock JD，不联网，用于验证采集→过滤→导出全流程",
        "is_active": True,
    },
    {
        "id": "logged_in_template",
        "name": "BOSS直聘（登录态模板）",
        "type": "recruit_platform",
        "url": "https://www.zhipin.com",
        "description": "需自行用浏览器抓包填写 Cookie/URL 后使用，仅抓公开 JD",
        "is_active": True,
    },
]


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value != value:  # NaN
        return ""
    return str(value).strip()


class DataCollectionService:
    """运行采集任务并缓存最近一次结果。"""

    def __init__(self) -> None:
        self._output_dir = Path(_BASE_DIR) / "data" / "raw" / "collected"
        self._result: dict[str, Any] | None = None
        self._tasks: list[dict[str, Any]] = []
        self._latest_file: str | None = None

    # ------------------------------------------------------------------
    # 数据源
    # ------------------------------------------------------------------

    def list_sources(self) -> list[dict[str, Any]]:
        return _SOURCES

    def get_source(self, source_id: str) -> dict[str, Any] | None:
        return next((s for s in _SOURCES if s["id"] == source_id), None)

    # ------------------------------------------------------------------
    # 采集任务
    # ------------------------------------------------------------------

    def run_task(self, source_ids: list[str], keywords: list[str], max_pages: int) -> dict[str, Any]:
        from adapters import get_adapter
        from jd_crawler import crawl
        from contract_exporter import export

        all_records: list[dict[str, Any]] = []
        total_pii = 0
        total_dup = 0

        # 逐数据源采集（每个 source_id 对应一个 adapter）
        for source_id in source_ids:
            if not self.get_source(source_id):
                continue
            try:
                adapter = get_adapter(source_id)
                records, dropped_pii, dropped_dup = crawl(
                    adapter, max_pages, datetime.now(timezone.utc).strftime("%Y-%m"), drop_pii=True
                )
            except Exception as exc:  # noqa: BLE001
                return {"id": uuid.uuid4().hex[:12], "status": "failed", "error": str(exc)}
            all_records.extend(records)
            total_pii += dropped_pii
            total_dup += dropped_dup

        task_id = uuid.uuid4().hex[:12]

        # 导出契约版 xlsx 并拿到 report
        report: dict[str, Any] = {}
        if all_records:
            self._output_dir.mkdir(parents=True, exist_ok=True)
            out_xlsx = self._output_dir / f"collected_{task_id}.xlsx"
            out_df, report = export(all_records, str(out_xlsx))
            records = out_df.to_dict(orient="records")
            self._latest_file = str(out_xlsx)
        else:
            records = []

        self._result = {"records": records, "report": report, "keywords": keywords}

        task = {
            "id": task_id,
            "source_ids": source_ids,
            "keywords": keywords,
            "max_pages": max_pages,
            "status": "completed",
            "collected_count": len(records),
            "dropped_pii": total_pii,
            "dropped_dup": total_dup,
            "report": report,
        }
        self._tasks.append(task)
        return task

    def list_tasks(self) -> list[dict[str, Any]]:
        return self._tasks

    def get_latest_collected_file(self) -> str | None:
        """返回最近一次采集导出的契约版 xlsx 路径，供数据清洗直接消费。"""
        return self._latest_file

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        return next((t for t in self._tasks if t["id"] == task_id), None)

    # ------------------------------------------------------------------
    # 原始数据
    # ------------------------------------------------------------------

    def list_raw_data(self, page: int, page_size: int, keyword: str | None = None) -> tuple[list[dict], int]:
        records = (self._result or {}).get("records", [])
        if keyword:
            kw = keyword.lower()
            records = [
                r for r in records
                if kw in str(r.get("job_title_raw", "")).lower()
                or kw in str(r.get("company_raw", "")).lower()
                or kw in str(r.get("raw_skills", "")).lower()
                or kw in str(r.get("raw_text", "")).lower()
            ]
        total = len(records)
        start = (page - 1) * page_size
        return [self._to_raw_item(r) for r in records[start : start + page_size]], total

    def get_raw_data(self, item_id: str) -> dict[str, Any] | None:
        records = (self._result or {}).get("records", [])
        for r in records:
            if _clean(r.get("jd_id")) == item_id:
                return self._to_raw_item(r)
        return None

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _to_raw_item(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _clean(row.get("jd_id")) or uuid.uuid4().hex[:12],
            "source_name": _clean(row.get("source_platform")),
            "title": _clean(row.get("job_title_raw")),
            "content": _clean(row.get("raw_text")) or _clean(row.get("responsibilities")),
            "url": _clean(row.get("url")) or None,
            "crawled_at": _clean(row.get("crawled_at")),
            "raw_metadata": {
                "company": _clean(row.get("company_raw")),
                "industry": _clean(row.get("industry_raw")),
                "city": _clean(row.get("city_raw")),
                "raw_skills": _clean(row.get("raw_skills")),
                "tech_stack": _clean(row.get("tech_stack")),
                "education": _clean(row.get("education_required_raw")),
                "experience": _clean(row.get("experience_required_raw")),
            },
        }


_service: DataCollectionService | None = None


def get_collection_service() -> DataCollectionService:
    global _service
    if _service is None:
        _service = DataCollectionService()
    return _service
