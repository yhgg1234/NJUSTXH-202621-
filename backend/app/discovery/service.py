"""子任务 2.4：新岗位发现、人工审核与既有岗位能力变更。"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha1
import json
import logging
from math import fsum
from pathlib import Path
import re
from statistics import median
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from app.config import settings
from app.discovery.data_source import (
    NormalizedJobRecord,
    NormalizedRecordReader,
    NormalizedSkill,
)
from app.discovery.models import (
    AbilityChange,
    AbilityChangeAnalyzeRequest,
    AbilityChangeResponse,
    AbilityChangeType,
    AdoptResult,
    BatchAdoptRequest,
    BatchRejectRequest,
    BatchResult,
    CandidateEditRequest,
    CandidateReviewRequest,
    CandidateSkill,
    CandidateStatus,
    ChangeReviewRequest,
    DiscoverRequest,
    DiscoverResponse,
    DiscoverStats,
    DiscoveryEvaluationRequest,
    DiscoveryEvaluationResponse,
    Evidence,
    EvidenceType,
    EvaluationMetric,
    NewJobCandidate,
    QualityReport,
    utc_now,
)
from app.discovery.state import DiscoveryStateStore
from app.graph.models import (
    GraphImportRequest,
    GraphNode,
    GraphRelationship,
    NodeType,
    RelationshipType,
)


ALGORITHM_VERSION = "skill-community-novelty-v1"
CHANGE_ALGORITHM_VERSION = "adjacent-period-diff-v1"


class DiscoveryDataError(ValueError):
    """输入数据不满足可验证发现的最低条件。"""


class GraphPort(Protocol):
    """2.4 对 2.3 的最小同步服务契约。"""

    def get_subgraph(self, **filters: Any) -> dict[str, Any]: ...

    def get_job_evolution_rows(
        self, *, job_id: str, start: date | None, end: date | None, granularity: str
    ) -> list[dict[str, Any]]: ...

    def import_graph(self, request: GraphImportRequest): ...

    def get_stats(self) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ExistingJobProfile:
    id: str
    name: str
    skill_ids: frozenset[str]


@dataclass
class _SeedGroup:
    key: str
    records: list[NormalizedJobRecord]
    skill_ids: set[str]
    title_tokens: set[str]


class DiscoveryService:
    def __init__(
        self,
        graph: GraphPort,
        reader: NormalizedRecordReader,
        store: DiscoveryStateStore,
    ) -> None:
        self._graph = graph
        self._reader = reader
        self._store = store

    # ── 新岗位发现 ──────────────────────────────────────────────

    def discover(self, request: DiscoverRequest) -> DiscoverResponse:
        loaded = self._reader.load(request.time_range)
        if not loaded.records:
            detail = "; ".join(loaded.quality.warnings) or "没有有效的 normalized_records"
            raise DiscoveryDataError(detail)

        profiles = self._existing_profiles()
        if not profiles:
            raise DiscoveryDataError(
                "2.3 图谱中没有可对照的 Job—Skill 画像，无法验证岗位 novelty；"
                "请先导入 graph_import_batch.json。"
            )

        known_job_ids = set(profiles)
        seed_groups = self._seed_groups(loaded.records, known_job_ids)
        clusters = self._community_clusters(
            seed_groups, request.cluster_similarity_threshold
        )
        candidates = []
        for records in clusters:
            candidate = self._build_candidate(records, profiles, request)
            if candidate is not None:
                candidates.append(candidate)

        candidates.sort(
            key=lambda item: (
                -item.emergence_confidence,
                -item.supporting_jd_count,
                item.name,
            )
        )
        candidates = candidates[: request.max_candidates]
        self._store.save_discovered_candidates(candidates)
        # 从持久化中重新读取，确保历史审核状态及人工优化生效。
        candidates = [
            self._store.get_candidate(item.candidate_id) or item for item in candidates
        ]
        self._save_quality_report(loaded.quality, request, len(candidates))
        skill_ids = {skill for profile in profiles.values() for skill in profile.skill_ids}
        return DiscoverResponse(
            candidates=candidates,
            total_scanned_jobs=len(profiles),
            total_scanned_skills=len(skill_ids),
            total_scanned_records=len(loaded.records),
            algorithm=ALGORITHM_VERSION,
            data_quality=loaded.quality,
        )

    def _existing_profiles(self) -> dict[str, ExistingJobProfile]:
        result = self._graph.get_subgraph(
            job_id=None,
            tech_stack=None,
            level=None,
            industry=None,
            period=None,
            as_of=None,
            include_history=False,
            limit=5000,
        )
        nodes = result.get("nodes") or []
        links = result.get("links") or []
        jobs: dict[str, str] = {}
        skills: set[str] = set()
        for node in nodes:
            node_type = _enum_value(node.get("type"))
            if node_type == "Job":
                jobs[str(node.get("id"))] = str(node.get("label") or node.get("id"))
            elif node_type == "Skill":
                skills.add(str(node.get("id")))
        job_skills: dict[str, set[str]] = defaultdict(set)
        for link in links:
            if _enum_value(link.get("type")) not in {"REQUIRES_SKILL", "BONUS_SKILL"}:
                continue
            source = str(link.get("source") or "")
            target = str(link.get("target") or "")
            if source in jobs and target in skills:
                job_skills[source].add(target)
        return {
            job_id: ExistingJobProfile(
                id=job_id,
                name=name,
                skill_ids=frozenset(job_skills.get(job_id, set())),
            )
            for job_id, name in jobs.items()
        }

    def _seed_groups(
        self, records: list[NormalizedJobRecord], known_job_ids: set[str]
    ) -> list[_SeedGroup]:
        grouped: dict[str, list[NormalizedJobRecord]] = defaultdict(list)
        for record in records:
            key = record.job_id or f"raw:{_normalize_title(record.raw_name)}"
            grouped[key].append(record)

        seeds = []
        for key, items in grouped.items():
            # 已经稳定对齐到正式图谱岗位且没有新候选标记的记录不属于新岗位候选。
            if key in known_job_ids and not any(item.is_new_candidate for item in items):
                continue
            skill_ids = {skill.id for item in items for skill in item.skills}
            title_tokens = set().union(
                *(_title_tokens(item.raw_name) for item in items)
            )
            seeds.append(
                _SeedGroup(
                    key=key,
                    records=items,
                    skill_ids=skill_ids,
                    title_tokens=title_tokens,
                )
            )
        return seeds

    def _community_clusters(
        self, seeds: list[_SeedGroup], threshold: float
    ) -> list[list[NormalizedJobRecord]]:
        """在技能—岗位二部图投影上用连通分量形成候选社区。"""

        parents = list(range(len(seeds)))

        def find(index: int) -> int:
            while parents[index] != index:
                parents[index] = parents[parents[index]]
                index = parents[index]
            return index

        def union(left: int, right: int) -> None:
            left_root, right_root = find(left), find(right)
            if left_root != right_root:
                parents[right_root] = left_root

        for left in range(len(seeds)):
            for right in range(left + 1, len(seeds)):
                if seeds[left].key == seeds[right].key:
                    union(left, right)
                    continue
                skill_similarity = _jaccard(seeds[left].skill_ids, seeds[right].skill_ids)
                title_similarity = _jaccard(
                    seeds[left].title_tokens, seeds[right].title_tokens
                )
                if skill_similarity >= threshold and title_similarity >= 0.2:
                    union(left, right)

        communities: dict[int, list[NormalizedJobRecord]] = defaultdict(list)
        for index, seed in enumerate(seeds):
            communities[find(index)].extend(seed.records)
        return list(communities.values())

    def _build_candidate(
        self,
        records: list[NormalizedJobRecord],
        profiles: dict[str, ExistingJobProfile],
        request: DiscoverRequest,
    ) -> NewJobCandidate | None:
        if len(records) < request.min_frequency:
            return None
        companies = {item.company for item in records if item.company != "未标注公司"}
        sources = {item.source_channel for item in records if item.source_channel}
        if len(companies) < request.min_companies or len(sources) < request.min_sources:
            return None

        skill_ids = {skill.id for item in records for skill in item.skills}
        ranked_profiles = sorted(
            (
                (_jaccard(skill_ids, set(profile.skill_ids)), profile)
                for profile in profiles.values()
            ),
            key=lambda item: (-item[0], item[1].name),
        )
        closest_similarity, closest = ranked_profiles[0]
        novelty = round(1 - closest_similarity, 4)
        if novelty < request.novelty_threshold:
            return None

        period_counts = Counter(
            _period_key(item.published_at, request.granularity) for item in records
        )
        periods = sorted(period_counts, key=lambda item: _period_index(item, request.granularity))
        earliest, latest = periods[0], periods[-1]
        trend = _trend_score([period_counts[period] for period in periods])
        average_quality = fsum(item.confidence for item in records) / len(records)
        diversity = min(1.0, 0.5 * len(companies) / request.min_companies + 0.5 * len(sources) / request.min_sources)
        support = min(1.0, len(records) / max(request.min_frequency * 2, 1))
        confidence = round(
            min(1.0, 0.5 * novelty + 0.18 * trend + 0.12 * diversity + 0.1 * support + 0.1 * average_quality),
            4,
        )
        if confidence < request.min_confidence:
            return None

        name = _most_common(
            [item.canonical_name or item.raw_name for item in records]
        )[:200]
        canonical_ids = [item.job_id for item in records if item.job_id]
        standardized_id = _most_common(canonical_ids) if canonical_ids else _job_id(name)
        if not standardized_id.startswith("job:") or len(standardized_id) > 160:
            standardized_id = _job_id(standardized_id)
        if standardized_id in profiles:
            standardized_id = _job_id(f"{name}:{'|'.join(sorted(skill_ids))}")
        candidate_id = "cand:" + standardized_id.removeprefix("job:")
        responsibilities = _top_texts(
            [text for item in records for text in item.responsibilities], limit=6
        )
        industries = [
            name for name, _ in Counter(
                industry for item in records for industry in item.industries
            ).most_common(5)
        ]
        required_skills, bonus_skills = _candidate_skills(records, latest)
        source_ids = sorted({item.source_id for item in records})
        descriptions = _top_texts(
            [item.description for item in records if item.description], limit=2
        )
        description = _definition_description(
            name,
            responsibilities,
            required_skills,
            bonus_skills,
            industries,
            descriptions,
        )
        evidence = [
            Evidence(
                type=EvidenceType.COMMUNITY_CLUSTER,
                description=(
                    f"{len(records)} 条去重 JD 形成稳定技能组合社区，"
                    f"覆盖 {len(companies)} 家公司。"
                ),
                confidence=min(1.0, support * 0.5 + diversity * 0.5),
                supporting_ids=source_ids[:100],
            ),
            Evidence(
                type=EvidenceType.SKILL_NOVELTY,
                description=(
                    f"与最相近既有岗位“{closest.name}”的技能 Jaccard 相似度为 "
                    f"{closest_similarity:.3f}，novelty 为 {novelty:.3f}。"
                ),
                confidence=novelty,
                supporting_ids=[closest.id] + [skill.id for skill in required_skills + bonus_skills],
            ),
            Evidence(
                type=EvidenceType.MULTI_SOURCE_SUPPORT,
                description=f"证据来自 {len(sources)} 个渠道、{len(companies)} 家公司。",
                confidence=diversity,
                supporting_ids=source_ids[:100],
            ),
        ]
        if len(periods) >= 2:
            evidence.append(
                Evidence(
                    type=EvidenceType.JD_FREQUENCY_SURGE,
                    description=(
                        f"{periods[-2]} 至 {latest} 的 JD 数由 "
                        f"{period_counts[periods[-2]]} 变为 {period_counts[latest]}。"
                    ),
                    confidence=trend,
                    supporting_ids=[
                        item.source_id
                        for item in records
                        if _period_key(item.published_at, request.granularity) == latest
                    ][:100],
                )
            )
        derived_from = [profile.id for _, profile in ranked_profiles[:3]]
        return NewJobCandidate(
            candidate_id=candidate_id,
            name=name,
            standardized_id=standardized_id,
            description=description,
            core_responsibilities=responsibilities,
            required_skills=required_skills,
            bonus_skills=bonus_skills,
            industry_scenarios=industries,
            derived_from=derived_from,
            estimated_emergence=earliest,
            latest_period=latest,
            emergence_confidence=confidence,
            novelty_score=novelty,
            trend_score=trend,
            closest_existing_job_id=closest.id,
            closest_existing_job_name=closest.name,
            closest_similarity=round(closest_similarity, 4),
            supporting_jd_count=len(records),
            latest_period_jd_count=period_counts[latest],
            company_count=len(companies),
            source_count=len(sources),
            period_counts=dict(sorted(period_counts.items())),
            source_ids=source_ids,
            evidence_chain=evidence,
            algorithm=ALGORITHM_VERSION,
        )

    # ── 人工审核与图谱写回 ──────────────────────────────────────

    def get_candidate(self, candidate_id: str) -> NewJobCandidate | None:
        return self._store.get_candidate(candidate_id)

    def edit_candidate(
        self, candidate_id: str, request: CandidateEditRequest
    ) -> NewJobCandidate:
        candidate = self._required_candidate(candidate_id)
        if candidate.status != CandidateStatus.PENDING:
            raise DiscoveryDataError("只有待审核候选可以优化定义")
        updates = request.model_dump(
            exclude={"reviewer", "review_comment"}, exclude_none=True
        )
        for field, value in updates.items():
            setattr(candidate, field, value)
        candidate.reviewer = request.reviewer
        candidate.review_comment = request.review_comment
        candidate.updated_at = utc_now()
        self._store.save_candidate(candidate)
        return candidate

    def adopt(
        self, candidate_id: str, review: CandidateReviewRequest
    ) -> AdoptResult:
        candidate = self._required_candidate(candidate_id)
        if candidate.status == CandidateStatus.ADOPTED:
            return AdoptResult(
                candidate_id=candidate_id, success=False, message="已采纳，请勿重复操作"
            )
        if review.create_graph_nodes:
            self._graph.import_graph(self._graph_batch(candidate))
        candidate.status = CandidateStatus.ADOPTED
        candidate.reviewer = review.reviewer
        candidate.review_comment = review.comment
        candidate.reviewed_at = utc_now()
        candidate.updated_at = candidate.reviewed_at
        self._store.save_candidate(candidate)
        return AdoptResult(
            candidate_id=candidate_id,
            success=True,
            created_job_id=candidate.standardized_id if review.create_graph_nodes else None,
            message="已采纳并写入 2.3 图谱" if review.create_graph_nodes else "已标记为采纳",
        )

    def reject(
        self, candidate_id: str, review: CandidateReviewRequest
    ) -> AdoptResult:
        candidate = self._required_candidate(candidate_id)
        candidate.status = CandidateStatus.REJECTED
        candidate.reviewer = review.reviewer
        candidate.review_comment = review.comment
        candidate.reviewed_at = utc_now()
        candidate.updated_at = candidate.reviewed_at
        self._store.save_candidate(candidate)
        return AdoptResult(candidate_id=candidate_id, success=True, message="已否决并记录审核意见")

    def batch_adopt(self, request: BatchAdoptRequest) -> BatchResult:
        review = CandidateReviewRequest(
            reviewer=request.reviewer,
            comment=request.comment,
            create_graph_nodes=request.create_graph_nodes,
        )
        results = [self._safe_review(item, review, True) for item in request.candidate_ids]
        ok = sum(item.success for item in results)
        return BatchResult(results=results, summary=f"成功采纳 {ok}/{len(results)} 个候选新岗位")

    def batch_reject(self, request: BatchRejectRequest) -> BatchResult:
        review = CandidateReviewRequest(
            reviewer=request.reviewer,
            comment=request.comment,
            create_graph_nodes=False,
        )
        results = [self._safe_review(item, review, False) for item in request.candidate_ids]
        ok = sum(item.success for item in results)
        return BatchResult(results=results, summary=f"成功否决 {ok}/{len(results)} 个候选新岗位")

    def _safe_review(
        self, candidate_id: str, review: CandidateReviewRequest, adopt: bool
    ) -> AdoptResult:
        try:
            return self.adopt(candidate_id, review) if adopt else self.reject(candidate_id, review)
        except Exception as exc:  # 批量操作逐条报告，不让单条失败回滚其他审核结论。
            return AdoptResult(candidate_id=candidate_id, success=False, message=str(exc))

    def _graph_batch(self, candidate: NewJobCandidate) -> GraphImportRequest:
        observed_at = utc_now()
        period_start = _period_start(candidate.latest_period)
        nodes: list[GraphNode] = [
            GraphNode(
                id=candidate.standardized_id,
                type=NodeType.JOB,
                name=candidate.name,
                properties={
                    "description": candidate.description,
                    "core_responsibilities": candidate.core_responsibilities,
                    "industry_scenarios": candidate.industry_scenarios,
                    "discovery_algorithm": candidate.algorithm,
                    "discovery_candidate_id": candidate.candidate_id,
                },
                confidence=candidate.emergence_confidence,
                source_ids=candidate.source_ids,
                observed_at=observed_at,
                valid_from=period_start,
            )
        ]
        relationships: list[GraphRelationship] = []
        for skill in candidate.required_skills + candidate.bonus_skills:
            nodes.append(
                GraphNode(
                    id=skill.id,
                    type=NodeType.SKILL,
                    name=skill.name,
                    aliases=skill.aliases,
                    confidence=min(1.0, max(0.0, skill.importance)),
                    source_ids=skill.evidence_ids,
                    observed_at=observed_at,
                )
            )
            relationship_type = (
                RelationshipType.REQUIRES_SKILL
                if skill.required
                else RelationshipType.BONUS_SKILL
            )
            latest_count = min(skill.latest_period_count, candidate.latest_period_jd_count)
            ratio = (
                latest_count / candidate.latest_period_jd_count
                if candidate.latest_period_jd_count
                else 0.0
            )
            relationships.append(
                GraphRelationship(
                    id=_relationship_id(
                        candidate.standardized_id,
                        relationship_type.value,
                        skill.id,
                        candidate.latest_period,
                    ),
                    type=relationship_type,
                    from_id=candidate.standardized_id,
                    to_id=skill.id,
                    properties={
                        "period_key": candidate.latest_period,
                        "period_start": period_start,
                        "skill_jd_count": latest_count,
                        "job_jd_count": candidate.latest_period_jd_count,
                        "demand_ratio": round(ratio, 4),
                        "importance": skill.importance,
                        **({"proficiency": skill.proficiency} if skill.proficiency else {}),
                        **({"years": skill.years} if skill.years is not None else {}),
                    },
                    confidence=candidate.emergence_confidence,
                    evidence_ids=skill.evidence_ids or candidate.source_ids,
                    observed_at=observed_at,
                    valid_from=period_start,
                )
            )
        for industry in candidate.industry_scenarios:
            industry_id = _industry_id(industry)
            nodes.append(
                GraphNode(
                    id=industry_id,
                    type=NodeType.INDUSTRY,
                    name=industry,
                    confidence=candidate.emergence_confidence,
                    source_ids=candidate.source_ids,
                )
            )
            relationships.append(
                GraphRelationship(
                    id=_relationship_id(
                        candidate.standardized_id,
                        "APPLIES_TO_INDUSTRY",
                        industry_id,
                    ),
                    type=RelationshipType.APPLIES_TO_INDUSTRY,
                    from_id=candidate.standardized_id,
                    to_id=industry_id,
                    confidence=candidate.emergence_confidence,
                    evidence_ids=candidate.source_ids,
                    observed_at=observed_at,
                )
            )
        return GraphImportRequest(
            batch_id=(
                "task-2.4-adopt-"
                + sha1(candidate.candidate_id.encode("utf-8")).hexdigest()[:12]
                + f"-{observed_at:%Y%m%d%H%M%S}"
            ),
            producer="task-2.4-human-reviewed",
            nodes=nodes,
            relationships=relationships,
        )

    def _required_candidate(self, candidate_id: str) -> NewJobCandidate:
        candidate = self._store.get_candidate(candidate_id)
        if candidate is None:
            raise DiscoveryDataError("候选新岗位不存在")
        return candidate

    def get_stats(self) -> DiscoverStats:
        candidates = self._store.list_candidates()
        counts = Counter(item.status.value for item in candidates)
        average = (
            fsum(item.emergence_confidence for item in candidates) / len(candidates)
            if candidates
            else 0.0
        )
        return DiscoverStats(
            total_candidates=len(candidates),
            adopted_count=counts[CandidateStatus.ADOPTED.value],
            rejected_count=counts[CandidateStatus.REJECTED.value],
            pending_count=counts[CandidateStatus.PENDING.value],
            avg_confidence=round(average, 4),
            by_status={status.value: counts[status.value] for status in CandidateStatus},
        )

    def history(self) -> list[NewJobCandidate]:
        return sorted(
            self._store.list_candidates(),
            key=lambda item: (item.updated_at, item.candidate_id),
            reverse=True,
        )

    # ── 既有岗位能力变更日志 ────────────────────────────────────

    def analyze_ability_changes(
        self, request: AbilityChangeAnalyzeRequest
    ) -> AbilityChangeResponse:
        rows = self._graph.get_job_evolution_rows(
            job_id=request.job_id,
            start=None,
            end=None,
            granularity=request.granularity,
        )
        snapshots: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        for row in rows:
            period = str(row.get("period") or "")
            skill_id = str(row.get("skill_id") or "")
            if not period or not skill_id:
                continue
            snapshots[period][skill_id] = _change_metric(row)
        warnings = []
        if request.from_period not in snapshots:
            warnings.append(f"缺少起始周期 {request.from_period} 的图谱快照")
        if request.to_period not in snapshots:
            warnings.append(f"缺少目标周期 {request.to_period} 的图谱快照")
        before = snapshots.get(request.from_period, {})
        after = snapshots.get(request.to_period, {})
        changes: list[AbilityChange] = []
        for skill_id in sorted(set(before) | set(after)):
            old, new = before.get(skill_id), after.get(skill_id)
            if old is None and new is not None:
                kind, delta = AbilityChangeType.ADDED, new["demand_ratio"]
            elif old is not None and new is None:
                kind, delta = AbilityChangeType.REMOVED, -old["demand_ratio"]
            elif old is not None and new is not None:
                delta = round(new["demand_ratio"] - old["demand_ratio"], 4)
                if delta >= request.change_threshold:
                    kind = AbilityChangeType.INCREASED
                elif delta <= -request.change_threshold:
                    kind = AbilityChangeType.DECREASED
                else:
                    continue
            else:
                continue
            evidence_ids = sorted(
                set((old or {}).get("evidence_ids", []))
                | set((new or {}).get("evidence_ids", []))
            )
            entity_name = str((new or old or {}).get("skill_name") or skill_id)
            change = AbilityChange(
                change_id=(
                    f"change:{request.job_id}:{request.from_period}:"
                    f"{request.to_period}:{skill_id}"
                ),
                job_id=request.job_id,
                from_period=request.from_period,
                to_period=request.to_period,
                change_type=kind,
                entity_id=skill_id,
                entity_name=entity_name,
                before=old,
                after=new,
                delta=delta,
                evidence_ids=evidence_ids,
                algorithm=CHANGE_ALGORITHM_VERSION,
            )
            changes.append(change)
        changes.sort(key=lambda item: (-abs(item.delta), item.entity_name))
        self._store.save_changes(changes)
        changes = [self._store.get_change(item.change_id) or item for item in changes]
        if not changes and not warnings:
            warnings.append("两个周期之间没有超过阈值的能力变化")
        return AbilityChangeResponse(
            job_id=request.job_id,
            from_period=request.from_period,
            to_period=request.to_period,
            changes=changes,
            warnings=warnings,
        )

    def list_ability_changes(self, job_id: str | None = None) -> list[AbilityChange]:
        return self._store.list_changes(job_id)

    def review_ability_change(
        self, change_id: str, request: ChangeReviewRequest
    ) -> AbilityChange:
        change = self._store.get_change(change_id)
        if change is None:
            raise DiscoveryDataError("能力变更日志不存在")
        change.review_status = request.status
        change.reviewed_by = request.reviewer
        change.reviewed_at = utc_now()
        change.review_comment = request.comment
        self._store.save_change(change)
        return change

    def evaluate(
        self, request: DiscoveryEvaluationRequest
    ) -> DiscoveryEvaluationResponse:
        """使用人工金标准计算可复现指标，不用模型置信度冒充准确率。"""

        new_job_metric = None
        if request.expected_new_job_ids:
            predicted = {
                item.standardized_id
                for item in self._store.list_candidates()
                if item.status != CandidateStatus.REJECTED
            }
            new_job_metric = _evaluation_metric(
                predicted, set(request.expected_new_job_ids)
            )
        change_metric = None
        if request.expected_ability_changes:
            predicted_changes = {
                (
                    item.job_id,
                    item.from_period,
                    item.to_period,
                    item.entity_id,
                    item.change_type.value,
                )
                for item in self._store.list_changes()
                if item.review_status.value != "rejected"
            }
            expected_changes = {
                (
                    item.job_id,
                    item.from_period,
                    item.to_period,
                    item.entity_id,
                    item.change_type.value,
                )
                for item in request.expected_ability_changes
            }
            change_metric = _evaluation_metric(predicted_changes, expected_changes)
        return DiscoveryEvaluationResponse(
            new_job_discovery=new_job_metric,
            ability_changes=change_metric,
        )

    def _save_quality_report(
        self, quality: Any, request: DiscoverRequest, candidate_count: int
    ) -> None:
        """将数据质量统计导出为 quality_report.json，用于验收审计。"""
        report = QualityReport(
            algorithm=ALGORITHM_VERSION,
            request={
                "novelty_threshold": request.novelty_threshold,
                "min_frequency": request.min_frequency,
                "min_companies": request.min_companies,
                "min_sources": request.min_sources,
                "cluster_similarity_threshold": request.cluster_similarity_threshold,
                "min_confidence": request.min_confidence,
                "granularity": request.granularity,
                **(
                    {"time_range": [str(item) for item in request.time_range]}
                    if request.time_range
                    else {}
                ),
            },
            data_quality=quality,
            candidates_found=candidate_count,
            candidates_adopted=0,
        )
        path = Path(settings.DISCOVERY_QUALITY_REPORT_PATH)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".tmp")
            with temporary.open("w", encoding="utf-8") as stream:
                json.dump(
                    report.model_dump(mode="json"),
                    stream,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            temporary.replace(path)
        except OSError:
            logging.warning("无法写入 quality_report.json: %s", path)


def _candidate_skills(
    records: list[NormalizedJobRecord], latest_period: str
) -> tuple[list[CandidateSkill], list[CandidateSkill]]:
    occurrences: dict[str, list[tuple[NormalizedJobRecord, NormalizedSkill]]] = defaultdict(list)
    for record in records:
        unique = {skill.id: skill for skill in record.skills}
        for skill in unique.values():
            if skill.requirement_type != "mentioned":
                occurrences[skill.id].append((record, skill))
    required: list[CandidateSkill] = []
    bonus: list[CandidateSkill] = []
    for skill_id, values in occurrences.items():
        support_count = len(values)
        support_ratio = support_count / len(records)
        if support_ratio < 0.2:
            continue
        required_count = sum(skill.requirement_type == "required" for _, skill in values)
        required_ratio = required_count / support_count
        is_required = required_ratio >= 0.5
        confidences = [skill.confidence for _, skill in values]
        names = [skill.name for _, skill in values]
        proficiencies = [skill.proficiency for _, skill in values if skill.proficiency]
        years = [skill.min_years for _, skill in values if skill.min_years is not None]
        evidence_ids = sorted({record.source_id for record, _ in values})
        aliases = sorted(
            {
                alias
                for _, skill in values
                for alias in (skill.raw_name, *skill.aliases)
                if alias and alias != _most_common(names)
            }
        )
        latest_count = sum(
            _period_key(record.published_at, "quarterly") == latest_period
            or _period_key(record.published_at, "monthly") == latest_period
            for record, _ in values
        )
        definition = CandidateSkill(
            id=skill_id,
            name=_most_common(names)[:200],
            required=is_required,
            importance=round(min(1.0, 0.7 * support_ratio + 0.3 * required_ratio), 4),
            support_count=support_count,
            support_ratio=round(support_ratio, 4),
            latest_period_count=latest_count,
            proficiency=_most_common(proficiencies) if proficiencies else None,
            years=round(float(median(years)), 2) if years else None,
            aliases=aliases,
            evidence_ids=evidence_ids,
        )
        (required if is_required else bonus).append(definition)
    required.sort(key=lambda item: (-item.importance, item.name))
    bonus.sort(key=lambda item: (-item.importance, item.name))
    return required, bonus


def _definition_description(
    name: str,
    responsibilities: list[str],
    required_skills: list[CandidateSkill],
    bonus_skills: list[CandidateSkill],
    industries: list[str],
    source_descriptions: list[str],
) -> str:
    responsibility = "；".join(responsibilities[:3]) or "承担相关技术方案设计与交付"
    required = "、".join(skill.name for skill in required_skills[:6]) or "待人工补充"
    bonus = "、".join(skill.name for skill in bonus_skills[:4]) or "无稳定加分技能"
    scenarios = "、".join(industries) or "待根据证据补充"
    evidence_summary = source_descriptions[0] if source_descriptions else ""
    return (
        f"{name}主要负责{responsibility}。必备技能包括{required}；"
        f"加分技能包括{bonus}；典型行业应用场景为{scenarios}。"
        + (f" 数据源摘要：{evidence_summary[:300]}" if evidence_summary else "")
    )


def _change_metric(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "skill_name": str(row.get("skill_name") or row.get("skill_id")),
        "relationship_type": str(row.get("relationship_type") or ""),
        "skill_jd_count": _integer(row.get("skill_jd_count")),
        "job_jd_count": _integer(row.get("job_jd_count")),
        "demand_ratio": _number(row.get("demand_ratio")),
        "importance": _number(row.get("importance")),
        "confidence": _number(row.get("confidence"), 1.0),
        "evidence_ids": [str(item) for item in (row.get("evidence_ids") or [])],
    }


def _title_tokens(value: str) -> set[str]:
    normalized = _normalize_title(value)
    if len(normalized) < 2:
        return {normalized} if normalized else set()
    return {normalized[index : index + 2] for index in range(len(normalized) - 1)}


def _normalize_title(value: str) -> str:
    normalized = re.sub(r"[\s/_\-（）()]+", "", value.lower())
    for suffix in ("工程师", "开发", "研发", "高级", "资深", "初级", "中级"):
        normalized = normalized.replace(suffix, "")
    return normalized


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _period_key(value: datetime, granularity: str) -> str:
    if granularity == "monthly":
        return f"{value.year:04d}-{value.month:02d}"
    return f"{value.year:04d}Q{(value.month - 1) // 3 + 1}"


def _period_index(value: str, granularity: str) -> int:
    if granularity == "monthly":
        year, month = value.split("-", 1)
        return int(year) * 12 + int(month) - 1
    return int(value[:4]) * 4 + int(value[-1]) - 1


def _period_start(value: str) -> datetime:
    if "Q" in value:
        year, quarter = int(value[:4]), int(value[-1])
        month = (quarter - 1) * 3 + 1
    else:
        year, month = (int(item) for item in value.split("-", 1))
    return datetime(year, month, 1, tzinfo=ZoneInfo("Asia/Shanghai"))


def _trend_score(counts: list[int]) -> float:
    if len(counts) < 2:
        return 0.0
    previous, latest = counts[-2], counts[-1]
    growth = (latest - previous) / max(previous, 1)
    return round(min(1.0, max(0.0, growth / 2)), 4)


def _most_common(values: list[str]) -> str:
    if not values:
        return ""
    return Counter(values).most_common(1)[0][0]


def _top_texts(values: list[str], limit: int) -> list[str]:
    normalized = [re.sub(r"\s+", " ", value).strip() for value in values if value.strip()]
    return [value for value, _ in Counter(normalized).most_common(limit)]


def _job_id(seed: str) -> str:
    return "job:candidate-" + sha1(seed.encode("utf-8")).hexdigest()[:16]


def _industry_id(name: str) -> str:
    return "industry:candidate-" + sha1(name.encode("utf-8")).hexdigest()[:16]


def _relationship_id(*parts: str) -> str:
    candidate = "|".join(parts)
    if len(candidate) <= 160:
        return candidate
    return "rel:task-2.4:" + sha1(candidate.encode("utf-8")).hexdigest()


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value or ""))


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return round(min(1.0, max(0.0, float(value))), 4)
    except (TypeError, ValueError):
        return default


def _integer(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _evaluation_metric(predicted: set[Any], expected: set[Any]) -> EvaluationMetric:
    true_positive = len(predicted & expected)
    false_positive = len(predicted - expected)
    false_negative = len(expected - predicted)
    precision = true_positive / len(predicted) if predicted else 0.0
    recall = true_positive / len(expected) if expected else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return EvaluationMetric(
        true_positive=true_positive,
        false_positive=false_positive,
        false_negative=false_negative,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        meets_80_percent=f1 >= 0.8,
    )
