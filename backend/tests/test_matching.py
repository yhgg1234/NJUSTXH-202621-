"""人岗匹配诊断接口测试。"""

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.matching.llm import SparkLiteClient
from app.matching.service import MatchingService
from app.routers import matching as matching_router


client = TestClient(app)


@pytest.fixture(autouse=True)
def use_demo_service(monkeypatch):
    """接口回归测试与本机是否存在真实简历数据相互独立。"""
    monkeypatch.setattr("app.matching.service.load_job_profile_from_graph", lambda _job_id: None)
    monkeypatch.setattr(
        matching_router,
        "service",
        MatchingService(
            llm_client=SparkLiteClient(api_url="", api_key=""),
            resumes={},
            jobs=None,
        ),
    )


def test_matching_options():
    response = client.get("/api/matching/options")
    assert response.status_code == 200
    data = response.json()
    assert data["resumes"]
    assert data["jobs"]


def test_legacy_demo_options_endpoint_is_compatible():
    response = client.get("/api/matching/demo-options")
    assert response.status_code == 200


def test_match_resume_to_job():
    response = client.post(
        "/api/matching/match",
        json={"resume_id": "resume-001", "job_id": "job:ai-agent-engineer"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_score"] > 0
    assert data["skill_score"] > 0
    assert data["dimensions"]
    assert data["assessment_level"]


def test_gap_analysis_covers_three_statuses():
    response = client.post(
        "/api/matching/gap-analysis",
        json={"resume_id": "resume-001", "job_id": "job:ai-agent-engineer"},
    )
    assert response.status_code == 200
    data = response.json()
    statuses = {item["status"] for item in data["skill_gaps"]}
    assert {"matched", "missing", "surplus"}.issubset(statuses)
    assert data["total_missing"] >= 1


def test_learning_path_has_three_phases():
    response = client.post(
        "/api/matching/learning-path",
        json={
            "resume_id": "resume-001",
            "job_id": "job:ai-agent-engineer",
            "target_months": 6,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_months"] == 6
    assert len(data["phases"]) == 3


def test_multi_match_returns_best_job():
    response = client.post(
        "/api/matching/multi-match",
        json={
            "resume_id": "resume-001",
            "job_ids": [
                "job:ai-agent-engineer",
                "job:data-analyst",
                "job:backend-engineer",
            ],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["comparisons"]) == 3
    assert data["best_match_job_id"]
