"""2.4 候选、人工审核和能力变更日志的轻量持久化。"""

from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Any

from app.discovery.models import AbilityChange, NewJobCandidate


class DiscoveryStateStore:
    """使用原子替换的 JSON 存储；生产环境可替换为 MySQL/MongoDB 实现。"""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = RLock()

    def list_candidates(self) -> list[NewJobCandidate]:
        with self._lock:
            state = self._read()
            return [NewJobCandidate.model_validate(item) for item in state["candidates"].values()]

    def get_candidate(self, candidate_id: str) -> NewJobCandidate | None:
        with self._lock:
            value = self._read()["candidates"].get(candidate_id)
            return NewJobCandidate.model_validate(value) if value else None

    def save_candidate(self, candidate: NewJobCandidate) -> None:
        with self._lock:
            state = self._read()
            state["candidates"][candidate.candidate_id] = candidate.model_dump(mode="json")
            self._write(state)

    def save_discovered_candidates(self, candidates: list[NewJobCandidate]) -> None:
        """保存新一轮结果，但保留已经发生的人工审核与人工优化。"""

        with self._lock:
            state = self._read()
            for candidate in candidates:
                previous_raw = state["candidates"].get(candidate.candidate_id)
                if previous_raw:
                    previous = NewJobCandidate.model_validate(previous_raw)
                    if previous.status.value != "pending" or previous.reviewed_at:
                        candidate.status = previous.status
                        candidate.reviewer = previous.reviewer
                        candidate.review_comment = previous.review_comment
                        candidate.reviewed_at = previous.reviewed_at
                    # 人工优化过的定义不被定时重跑结果覆盖。
                    if previous.reviewer and previous.updated_at > previous.discovered_at:
                        candidate.name = previous.name
                        candidate.description = previous.description
                        candidate.core_responsibilities = previous.core_responsibilities
                        candidate.required_skills = previous.required_skills
                        candidate.bonus_skills = previous.bonus_skills
                        candidate.industry_scenarios = previous.industry_scenarios
                        candidate.updated_at = previous.updated_at
                state["candidates"][candidate.candidate_id] = candidate.model_dump(mode="json")
            self._write(state)

    def list_changes(self, job_id: str | None = None) -> list[AbilityChange]:
        with self._lock:
            changes = [
                AbilityChange.model_validate(item)
                for item in self._read()["changes"].values()
            ]
        if job_id:
            changes = [change for change in changes if change.job_id == job_id]
        return sorted(changes, key=lambda item: (item.created_at, item.change_id), reverse=True)

    def get_change(self, change_id: str) -> AbilityChange | None:
        with self._lock:
            value = self._read()["changes"].get(change_id)
            return AbilityChange.model_validate(value) if value else None

    def save_changes(self, changes: list[AbilityChange]) -> None:
        with self._lock:
            state = self._read()
            for change in changes:
                previous = state["changes"].get(change.change_id)
                if previous:
                    reviewed = AbilityChange.model_validate(previous)
                    change.review_status = reviewed.review_status
                    change.reviewed_by = reviewed.reviewed_by
                    change.reviewed_at = reviewed.reviewed_at
                    change.review_comment = reviewed.review_comment
                    change.created_at = reviewed.created_at
                state["changes"][change.change_id] = change.model_dump(mode="json")
            self._write(state)

    def save_change(self, change: AbilityChange) -> None:
        with self._lock:
            state = self._read()
            state["changes"][change.change_id] = change.model_dump(mode="json")
            self._write(state)

    def _read(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {"schema_version": "1.0.0", "candidates": {}, "changes": {}}
        try:
            with self.path.open("r", encoding="utf-8") as stream:
                value = json.load(stream)
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"无法读取 2.4 状态文件 {self.path}: {exc}") from exc
        if not isinstance(value, dict):
            raise RuntimeError(f"2.4 状态文件顶层必须是对象: {self.path}")
        value.setdefault("schema_version", "1.0.0")
        value.setdefault("candidates", {})
        value.setdefault("changes", {})
        return value

    def _write(self, value: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
        temporary.replace(self.path)
