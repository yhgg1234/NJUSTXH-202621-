"""子任务 3.1 的演化分析服务与 API 测试。"""

from datetime import date

from fastapi.testclient import TestClient

from app.jobs.dependencies import get_job_evolution_service
from app.jobs.models import JobEvolutionQuery, TimeGranularity
from app.jobs.service import JobEvolutionService
from app.main import app


class FakeEvolutionReader:
    def __init__(self, rows):
        self.rows = rows
        self.last_query = None

    def get_job_evolution_rows(self, **kwargs):
        self.last_query = kwargs
        return self.rows


def _row(period, start, skill_id, skill_name, count, *, jd_count=100, relation="REQUIRES_SKILL"):
    return {
        "period": period,
        "period_start": start,
        "job_id": "job:backend-engineer",
        "job_name": "后端开发工程师",
        "skill_id": skill_id,
        "skill_name": skill_name,
        "relationship_type": relation,
        "skill_jd_count": count,
        "job_jd_count": jd_count,
        "importance": count / jd_count,
        "confidence": 0.9,
        "evidence_ids": [f"source:{period}:{skill_id}"],
    }


def _four_period_rows():
    return [
        _row("2024Q1", "2024-01-01T00:00:00+08:00", "skill:python", "Python", 50),
        _row("2024Q1", "2024-01-01T00:00:00+08:00", "skill:java", "Java", 45),
        _row("2024Q2", "2024-04-01T00:00:00+08:00", "skill:python", "Python", 62),
        _row("2024Q2", "2024-04-01T00:00:00+08:00", "skill:java", "Java", 30),
        _row("2024Q3", "2024-07-01T00:00:00+08:00", "skill:python", "Python", 74),
        _row("2024Q3", "2024-07-01T00:00:00+08:00", "skill:rag", "RAG", 28),
        _row("2024Q4", "2024-10-01T00:00:00+08:00", "skill:python", "Python", 81),
        _row("2024Q4", "2024-10-01T00:00:00+08:00", "skill:rag", "RAG", 46),
    ]


def test_evolution_builds_snapshots_changes_and_quality_warning():
    reader = FakeEvolutionReader(_four_period_rows())
    result = JobEvolutionService(reader).analyze(
        JobEvolutionQuery(
            job_id="job:backend-engineer",
            granularity=TimeGranularity.QUARTERLY,
            time_range=(date(2024, 1, 1), date(2024, 12, 31)),
        )
    )

    assert [item.period for item in result.timeline] == ["2024Q1", "2024Q2", "2024Q3", "2024Q4"]
    assert result.timeline[0].skill_set[0].demand_ratio == 0.5
    change_types = {item.skill_name: item.change_type.value for item in result.timeline[2].changes_from_previous}
    assert change_types["RAG"] == "added"
    assert change_types["Java"] == "removed"
    assert result.hot_trends[0].skill_name == "Python"
    assert result.cold_trends[0].skill_name == "Java"
    assert result.prediction.available is False
    assert result.data_quality.period_count == 4
    assert reader.last_query["granularity"] == "quarterly"


def test_evolution_enables_baseline_prediction_after_six_periods():
    rows = []
    for index in range(6):
        month = 1 + index
        rows.append(
            _row(
                f"2024-{month:02d}",
                f"2024-{month:02d}-01T00:00:00+08:00",
                "skill:python",
                "Python",
                20 + index * 10,
            )
        )
    result = JobEvolutionService(FakeEvolutionReader(rows)).analyze(
        JobEvolutionQuery(job_id="job:backend-engineer", granularity=TimeGranularity.MONTHLY)
    )

    assert result.prediction.available is True
    assert result.prediction.model == "linear-trend-baseline"
    assert "Python" in result.prediction.rising_skills


def test_evolution_api_uses_injected_service():
    reader = FakeEvolutionReader(_four_period_rows())
    app.dependency_overrides[get_job_evolution_service] = lambda: JobEvolutionService(reader)
    try:
        response = TestClient(app).post(
            "/api/jobs/evolution",
            json={
                "job_id": "job:backend-engineer",
                "granularity": "quarterly",
                "time_range": ["2024-01-01", "2024-12-31"],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["data_quality"]["period_count"] == 4
