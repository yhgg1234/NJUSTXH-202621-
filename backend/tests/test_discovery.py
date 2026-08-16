"""子任务 2.4 的真实数据发现、图谱写回和变更日志测试。"""

import json

from fastapi.testclient import TestClient

from app.discovery.data_source import NormalizedRecordReader
from app.discovery.dependencies import get_discovery_service
from app.discovery.models import (
    AbilityChangeAnalyzeRequest,
    CandidateReviewRequest,
    DiscoverRequest,
    DiscoveryEvaluationRequest,
)
from app.discovery.service import DiscoveryService
from app.discovery.state import DiscoveryStateStore
from app.main import app


class FakeDiscoveryGraph:
    def __init__(self):
        self.imports = []
        self.evolution_rows = []

    def get_subgraph(self, **kwargs):
        return {
            "nodes": [
                {"id": "job:backend-engineer", "label": "后端开发工程师", "type": "Job"},
                {"id": "skill:python", "label": "Python", "type": "Skill"},
                {"id": "skill:docker", "label": "Docker", "type": "Skill"},
            ],
            "links": [
                {
                    "id": "backend-python",
                    "source": "job:backend-engineer",
                    "target": "skill:python",
                    "type": "REQUIRES_SKILL",
                },
                {
                    "id": "backend-docker",
                    "source": "job:backend-engineer",
                    "target": "skill:docker",
                    "type": "BONUS_SKILL",
                },
            ],
        }

    def import_graph(self, request):
        self.imports.append(request)
        return {"nodes_upserted": len(request.nodes), "relationships_upserted": len(request.relationships)}

    def get_job_evolution_rows(self, **kwargs):
        return self.evolution_rows

    def get_stats(self):
        return {"node_count": 3, "relationship_count": 2}


def _normalized_record(index: int) -> dict:
    second_period = index >= 2
    platform = "boss" if index % 2 == 0 else "liepin"
    company = "甲科技" if index % 2 == 0 else "乙智能"
    return {
        "schema_version": "1.0.0",
        "jd_id": f"{platform}:agentops-{index}",
        "source_id": f"source:{platform}:agentops-{index}",
        "document_type": "job_description",
        "source_platform": platform,
        "published_at": f"2025-{'04' if second_period else '01'}-{index + 1:02d}T09:00:00+08:00",
        "crawled_at": "2025-07-01T09:00:00+08:00",
        "content_hash": f"sha256:{index:064d}",
        "job": {
            "raw_name": "智能体运维工程师",
            "canonical_id": "job:agent-operations-engineer",
            "canonical_name": "智能体运维工程师",
            "description": "负责智能体运行监控、工具调用链路治理和故障处置",
            "alignment_confidence": 0.94,
            "is_new_candidate": True,
        },
        "skills": [
            {
                "raw_name": "Python",
                "canonical_id": "skill:python",
                "canonical_name": "Python",
                "requirement_type": "required",
                "confidence": 0.98,
                "evidence": ["熟悉 Python"],
            },
            {
                "raw_name": "RAG",
                "canonical_id": "skill:rag",
                "canonical_name": "RAG",
                "requirement_type": "required",
                "confidence": 0.95,
                "evidence": ["负责 RAG 链路监控"],
            },
            {
                "raw_name": "LangChain",
                "canonical_id": "skill:langchain",
                "canonical_name": "LangChain",
                "requirement_type": "preferred",
                "confidence": 0.9,
                "evidence": ["有 LangChain 经验优先"],
            },
        ],
        "industries": [{"canonical_id": "industry:ai", "name": "人工智能"}],
        "company": {"canonical_id": f"company:{index % 2}", "name": company},
        "responsibilities": ["监控智能体运行状态", "治理工具调用链路", "处置线上故障"],
    }


def _service(tmp_path):
    data_file = tmp_path / "normalized_records.jsonl"
    data_file.write_text(
        "\n".join(json.dumps(_normalized_record(index), ensure_ascii=False) for index in range(6)),
        encoding="utf-8",
    )
    graph = FakeDiscoveryGraph()
    service = DiscoveryService(
        graph,
        NormalizedRecordReader(data_file),
        DiscoveryStateStore(tmp_path / "discovery-state.json"),
    )
    return service, graph


def test_discovery_uses_normalized_records_and_graph_novelty(tmp_path):
    service, _ = _service(tmp_path)

    result = service.discover(DiscoverRequest())

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.name == "智能体运维工程师"
    assert candidate.supporting_jd_count == 6
    assert candidate.company_count == 2
    assert candidate.source_count == 2
    assert candidate.novelty_score > 0.5
    assert candidate.closest_existing_job_id == "job:backend-engineer"
    assert {skill.name for skill in candidate.required_skills} == {"Python", "RAG"}
    assert {skill.name for skill in candidate.bonus_skills} == {"LangChain"}
    assert candidate.core_responsibilities
    assert candidate.industry_scenarios == ["人工智能"]
    assert result.data_quality.valid_records == 6


def test_adopt_writes_reviewed_definition_to_graph_before_marking_adopted(tmp_path):
    service, graph = _service(tmp_path)
    candidate = service.discover(DiscoverRequest()).candidates[0]

    result = service.adopt(
        candidate.candidate_id,
        CandidateReviewRequest(reviewer="评审员", comment="定义和证据通过"),
    )

    assert result.success is True
    assert result.created_job_id == candidate.standardized_id
    assert len(graph.imports) == 1
    batch = graph.imports[0]
    assert batch.producer == "task-2.4-human-reviewed"
    assert any(node.id == candidate.standardized_id for node in batch.nodes)
    assert any(rel.evidence_ids for rel in batch.relationships)
    assert all(
        rel.type.value != "EVOLVES_TO" for rel in batch.relationships
    )
    assert service.get_candidate(candidate.candidate_id).status.value == "adopted"


def test_existing_job_changes_have_complete_auditable_contract(tmp_path):
    service, graph = _service(tmp_path)
    graph.evolution_rows = [
        {
            "period": "2025Q1", "skill_id": "skill:java", "skill_name": "Java",
            "relationship_type": "REQUIRES_SKILL", "skill_jd_count": 60,
            "job_jd_count": 100, "demand_ratio": 0.6, "importance": 0.7,
            "confidence": 0.95, "evidence_ids": ["source:q1-java"],
        },
        {
            "period": "2025Q2", "skill_id": "skill:java", "skill_name": "Java",
            "relationship_type": "REQUIRES_SKILL", "skill_jd_count": 35,
            "job_jd_count": 100, "demand_ratio": 0.35, "importance": 0.5,
            "confidence": 0.94, "evidence_ids": ["source:q2-java"],
        },
        {
            "period": "2025Q2", "skill_id": "skill:rag", "skill_name": "RAG",
            "relationship_type": "BONUS_SKILL", "skill_jd_count": 20,
            "job_jd_count": 100, "demand_ratio": 0.2, "importance": 0.4,
            "confidence": 0.9, "evidence_ids": ["source:q2-rag"],
        },
    ]

    result = service.analyze_ability_changes(
        AbilityChangeAnalyzeRequest(
            job_id="job:backend-engineer", from_period="2025Q1", to_period="2025Q2"
        )
    )

    assert {change.change_type.value for change in result.changes} == {"decreased", "added"}
    rag = next(change for change in result.changes if change.entity_id == "skill:rag")
    assert rag.change_id.startswith("change:job:backend-engineer")
    assert rag.from_period == "2025Q1" and rag.to_period == "2025Q2"
    assert rag.after["demand_ratio"] == 0.2
    assert rag.algorithm == "adjacent-period-diff-v1"
    assert rag.evidence_ids == ["source:q2-rag"]
    assert rag.review_status.value == "pending"


def test_evaluation_uses_gold_labels_instead_of_candidate_confidence(tmp_path):
    service, _ = _service(tmp_path)
    candidate = service.discover(DiscoverRequest()).candidates[0]

    result = service.evaluate(
        DiscoveryEvaluationRequest(
            expected_new_job_ids=[candidate.standardized_id]
        )
    )

    assert result.new_job_discovery.precision == 1.0
    assert result.new_job_discovery.recall == 1.0
    assert result.new_job_discovery.f1 == 1.0
    assert result.new_job_discovery.meets_80_percent is True


def test_static_batch_and_history_routes_are_not_shadowed(tmp_path):
    service, _ = _service(tmp_path)
    candidate = service.discover(DiscoverRequest()).candidates[0]
    app.dependency_overrides[get_discovery_service] = lambda: service
    try:
        client = TestClient(app)
        batch = client.post(
            "/api/jobs/discover-new/batch/reject",
            json={
                "candidate_ids": [candidate.candidate_id],
                "reviewer": "评审员",
                "comment": "测试否决",
            },
        )
        history = client.get("/api/jobs/discover-new/history")
        ability_history = client.get("/api/jobs/ability-changes")
    finally:
        app.dependency_overrides.clear()

    assert batch.status_code == 200
    assert batch.json()["results"][0]["success"] is True
    assert history.status_code == 200
    assert history.json()["history"][0]["candidate_id"] == candidate.candidate_id
    assert ability_history.status_code == 200
    assert ability_history.json() == []
