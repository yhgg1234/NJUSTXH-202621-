"""子任务 3.1：岗位能力动态演化分析服务。"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from math import fsum
from typing import Any, Protocol

from app.jobs.models import (
    EvolutionDataQuality,
    EvolutionPrediction,
    JobEvolutionPoint,
    JobEvolutionQuery,
    JobEvolutionResponse,
    SkillChange,
    SkillChangeType,
    SkillMetric,
    SkillTrend,
)


class EvolutionDataReader(Protocol):
    """3.1 对 2.3 的最小读取契约。"""

    def get_job_evolution_rows(
        self,
        *,
        job_id: str,
        start: date | None,
        end: date | None,
        granularity: str,
    ) -> list[dict[str, Any]]: ...


class JobEvolutionService:
    """将周期化岗位—技能关系转换为可解释的演化结果。"""

    def __init__(self, reader: EvolutionDataReader) -> None:
        self.reader = reader

    def analyze(self, query: JobEvolutionQuery) -> JobEvolutionResponse:
        start, end = query.time_range if query.time_range else (None, None)
        rows = self.reader.get_job_evolution_rows(
            job_id=query.job_id,
            start=start,
            end=end,
            granularity=query.granularity.value,
        )
        return self._build_response(query, rows)

    def _build_response(
        self, query: JobEvolutionQuery, rows: list[dict[str, Any]]
    ) -> JobEvolutionResponse:
        job_title = next(
            (str(row.get("job_name")) for row in rows if row.get("job_name")),
            query.job_id,
        )
        snapshots = self._aggregate_rows(rows)
        ordered_periods = sorted(
            snapshots,
            key=lambda period: (
                snapshots[period]["period_start"] is None,
                snapshots[period]["period_start"] or date.max,
                period,
            ),
        )

        timeline: list[JobEvolutionPoint] = []
        previous_metrics: dict[str, SkillMetric] = {}
        full_snapshot_metrics: list[dict[str, SkillMetric]] = []
        total_jd_count = 0
        for period in ordered_periods:
            snapshot = snapshots[period]
            metrics = self._finalize_metrics(snapshot["skills"])
            full_snapshot_metrics.append(metrics)
            current_jd_count = int(snapshot["job_jd_count"])
            total_jd_count += current_jd_count
            changes = self._changes_between(
                previous_metrics, metrics, query.change_threshold
            )
            displayed_skills = sorted(
                metrics.values(), key=lambda item: (-item.demand_ratio, item.skill_name)
            )[: query.top_n]
            timeline.append(
                JobEvolutionPoint(
                    period=period,
                    period_start=snapshot["period_start"],
                    skill_set=displayed_skills,
                    jd_count=current_jd_count,
                    changes_from_previous=changes,
                )
            )
            previous_metrics = metrics

        quality = self._quality_report(timeline, rows, total_jd_count)
        trends = self._build_trends(full_snapshot_metrics, query.top_n)
        prediction = self._predict(full_snapshot_metrics, query.prediction_horizon_months)
        return JobEvolutionResponse(
            job_id=query.job_id,
            job_title=job_title,
            timeline=timeline,
            hot_trends=trends["hot"],
            cold_trends=trends["cold"],
            prediction=prediction,
            data_quality=quality,
        )

    def _aggregate_rows(self, rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        snapshots: dict[str, dict[str, Any]] = {}
        for row in rows:
            period = str(row.get("period") or "").strip()
            skill_id = str(row.get("skill_id") or "").strip()
            if not period or not skill_id:
                continue
            snapshot = snapshots.setdefault(
                period,
                {
                    "period_start": _to_date(row.get("period_start")),
                    "job_jd_count": 0,
                    "skills": {},
                },
            )
            period_start = _to_date(row.get("period_start"))
            if period_start and (
                snapshot["period_start"] is None or period_start < snapshot["period_start"]
            ):
                snapshot["period_start"] = period_start

            job_jd_count = _to_int(row.get("job_jd_count"))
            snapshot["job_jd_count"] = max(snapshot["job_jd_count"], job_jd_count)
            skill = snapshot["skills"].setdefault(
                skill_id,
                {
                    "skill_id": skill_id,
                    "skill_name": str(row.get("skill_name") or skill_id),
                    "required": row.get("relationship_type") != "BONUS_SKILL",
                    "skill_jd_count": 0,
                    "job_jd_count": 0,
                    "raw_ratios": [],
                    "importance": 0.0,
                    "confidence_values": [],
                    "evidence_ids": set(),
                },
            )
            skill["required"] = skill["required"] or row.get("relationship_type") != "BONUS_SKILL"
            skill["job_jd_count"] = max(skill["job_jd_count"], job_jd_count)
            skill["skill_jd_count"] += _to_int(
                row.get("skill_jd_count", row.get("frequency", 0))
            )
            if row.get("demand_ratio") is not None:
                skill["raw_ratios"].append(_to_float(row.get("demand_ratio")))
            skill["importance"] = max(skill["importance"], _to_float(row.get("importance")))
            skill["confidence_values"].append(_to_float(row.get("confidence"), default=1.0))
            evidence_ids = row.get("evidence_ids") or []
            if isinstance(evidence_ids, str):
                evidence_ids = [evidence_ids]
            skill["evidence_ids"].update(str(item) for item in evidence_ids if item)
        return snapshots

    def _finalize_metrics(self, raw_skills: dict[str, dict[str, Any]]) -> dict[str, SkillMetric]:
        metrics: dict[str, SkillMetric] = {}
        for skill_id, value in raw_skills.items():
            job_jd_count = value["job_jd_count"]
            if job_jd_count > 0:
                demand_ratio = min(1.0, value["skill_jd_count"] / job_jd_count)
            elif value["raw_ratios"]:
                demand_ratio = min(1.0, max(value["raw_ratios"]))
            else:
                demand_ratio = 0.0
            importance = value["importance"] or demand_ratio
            confidence_values = value["confidence_values"] or [1.0]
            metrics[skill_id] = SkillMetric(
                skill_id=skill_id,
                skill_name=value["skill_name"],
                required=value["required"],
                skill_jd_count=value["skill_jd_count"],
                job_jd_count=job_jd_count,
                demand_ratio=round(demand_ratio, 4),
                importance=round(min(1.0, importance), 4),
                confidence=round(fsum(confidence_values) / len(confidence_values), 4),
                evidence_ids=sorted(value["evidence_ids"]),
            )
        return metrics

    def _changes_between(
        self,
        previous: dict[str, SkillMetric],
        current: dict[str, SkillMetric],
        threshold: float,
    ) -> list[SkillChange]:
        changes: list[SkillChange] = []
        for skill_id in sorted(set(previous) | set(current)):
            old = previous.get(skill_id)
            new = current.get(skill_id)
            if old is None and new is not None:
                changes.append(
                    SkillChange(
                        skill_id=skill_id,
                        skill_name=new.skill_name,
                        change_type=SkillChangeType.ADDED,
                        current_demand_ratio=new.demand_ratio,
                        delta=new.demand_ratio,
                        evidence_ids=new.evidence_ids,
                    )
                )
            elif new is None and old is not None:
                changes.append(
                    SkillChange(
                        skill_id=skill_id,
                        skill_name=old.skill_name,
                        change_type=SkillChangeType.REMOVED,
                        previous_demand_ratio=old.demand_ratio,
                        delta=-old.demand_ratio,
                        evidence_ids=old.evidence_ids,
                    )
                )
            elif old is not None and new is not None:
                delta = round(new.demand_ratio - old.demand_ratio, 4)
                if delta >= threshold:
                    change_type = SkillChangeType.INCREASED
                elif delta <= -threshold:
                    change_type = SkillChangeType.DECREASED
                else:
                    continue
                changes.append(
                    SkillChange(
                        skill_id=skill_id,
                        skill_name=new.skill_name,
                        change_type=change_type,
                        previous_demand_ratio=old.demand_ratio,
                        current_demand_ratio=new.demand_ratio,
                        delta=delta,
                        evidence_ids=sorted(set(old.evidence_ids) | set(new.evidence_ids)),
                    )
                )
        return sorted(changes, key=lambda item: (-abs(item.delta), item.skill_name))

    def _build_trends(
        self, snapshots: list[dict[str, SkillMetric]], top_n: int
    ) -> dict[str, list[SkillTrend]]:
        if len(snapshots) < 2:
            return {"hot": [], "cold": []}
        skill_ids = set().union(*(snapshot.keys() for snapshot in snapshots))
        trends: list[SkillTrend] = []
        for skill_id in skill_ids:
            series = [snapshot.get(skill_id) for snapshot in snapshots]
            observed = [item for item in series if item is not None]
            if not observed:
                continue
            # 未出现在某一期等价于该期需求占比为 0；否则被移除的技能不会进入冷趋势。
            first_ratio = series[0].demand_ratio if series[0] else 0.0
            latest_ratio = series[-1].demand_ratio if series[-1] else 0.0
            latest_named = next((item for item in reversed(observed)), observed[0])
            trends.append(
                SkillTrend(
                    skill_id=skill_id,
                    skill_name=latest_named.skill_name,
                    first_demand_ratio=first_ratio,
                    latest_demand_ratio=latest_ratio,
                    delta=round(latest_ratio - first_ratio, 4),
                )
            )
        hot = sorted(
            (item for item in trends if item.delta > 0),
            key=lambda item: (-item.delta, item.skill_name),
        )[:top_n]
        cold = sorted(
            (item for item in trends if item.delta < 0),
            key=lambda item: (item.delta, item.skill_name),
        )[:top_n]
        return {"hot": hot, "cold": cold}

    def _predict(
        self, snapshots: list[dict[str, SkillMetric]], horizon_months: int
    ) -> EvolutionPrediction:
        minimum_periods = 6
        if len(snapshots) < minimum_periods:
            return EvolutionPrediction(
                available=False,
                horizon_months=horizon_months,
                reason=f"当前仅有 {len(snapshots)} 个时间周期，至少需要 {minimum_periods} 期才提供趋势外推。",
            )
        skill_ids = set().union(*(snapshot.keys() for snapshot in snapshots))
        candidates: list[tuple[float, str]] = []
        for skill_id in skill_ids:
            values = [snapshot.get(skill_id, _EMPTY_METRIC).demand_ratio for snapshot in snapshots]
            slope = _linear_slope(values)
            if slope <= 0:
                continue
            latest = values[-1]
            projected = min(1.0, latest + slope * min(horizon_months, len(values)))
            name = next(
                (snapshot[skill_id].skill_name for snapshot in reversed(snapshots) if skill_id in snapshot),
                skill_id,
            )
            candidates.append((projected - latest, name))
        rising_skills = [name for _, name in sorted(candidates, reverse=True)[:5]]
        return EvolutionPrediction(
            available=True,
            model="linear-trend-baseline",
            horizon_months=horizon_months,
            reason="基于周期需求占比的线性趋势外推，仅供探索，不代表因果预测。",
            rising_skills=rising_skills,
        )

    def _quality_report(
        self,
        timeline: list[JobEvolutionPoint],
        rows: list[dict[str, Any]],
        total_jd_count: int,
    ) -> EvolutionDataQuality:
        warnings: list[str] = []
        if not timeline:
            warnings.append("未找到可用的周期化岗位—技能关系，请先导入带 period_key 和样本量的历史数据。")
        if 0 < len(timeline) < 4:
            warnings.append("时间周期少于 4 期，只适合快照对比，不能作为完整演化结论。")
        if any(point.jd_count == 0 for point in timeline):
            warnings.append("部分周期缺少岗位 JD 总量，需求占比可能退化为抽取频次。")
        if rows and any(not _to_date(row.get("period_start")) for row in rows):
            warnings.append("部分关系缺少可解析的周期起点；请检查 period_start/valid_from 的 ISO-8601 格式。")
        if rows and not any(row.get("evidence_ids") for row in rows):
            warnings.append("当前结果缺少证据来源，变化项无法完成数据溯源。")
        return EvolutionDataQuality(
            period_count=len(timeline), total_jd_count=total_jd_count, warnings=warnings
        )


_EMPTY_METRIC = SkillMetric(skill_id="", skill_name="")


def _to_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return default


def _to_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                return None
    return None


def _linear_slope(values: list[float]) -> float:
    """无需额外依赖的最小二乘斜率。"""
    count = len(values)
    if count < 2:
        return 0.0
    mean_x = (count - 1) / 2
    mean_y = fsum(values) / count
    denominator = fsum((index - mean_x) ** 2 for index in range(count))
    if denominator == 0:
        return 0.0
    numerator = fsum(
        (index - mean_x) * (value - mean_y) for index, value in enumerate(values)
    )
    return numerator / denominator
