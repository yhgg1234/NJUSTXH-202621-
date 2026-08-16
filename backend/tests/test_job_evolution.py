"""子任务 3.1 的演化分析服务与 API 测试。"""

from datetime import date

from fastapi.testclient import TestClient

from app.jobs.dependencies import get_job_evolution_service
from app.jobs.models import JobEvolutionQuery, TimeGranularity
from app.jobs.service import JobEvolutionService
from app.graph.repository import Neo4jGraphRepository
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
    assert result.timeline[0].changes_from_previous == []
    change_types = {item.skill_name: item.change_type.value for item in result.timeline[2].changes_from_previous}
    assert change_types["RAG"] == "added"
    assert change_types["Java"] == "removed"
    assert result.hot_trends[0].skill_name == "RAG"
    assert result.cold_trends[0].skill_name == "Java"
    assert result.prediction.available is False
    assert result.data_quality.period_count == 4
    assert reader.last_query["granularity"] == "monthly"


def test_quarterly_analysis_rolls_up_published_at_monthly_snapshots():
    rows = [
        _row("2023-07", "2023-07-01T00:00:00+08:00", "skill:python", "Python", 2, jd_count=4),
        _row("2023-08", "2023-08-01T00:00:00+08:00", "skill:python", "Python", 3, jd_count=5),
        _row("2023-09", "2023-09-01T00:00:00+08:00", "skill:python", "Python", 1, jd_count=1),
        _row("2023-10", "2023-10-01T00:00:00+08:00", "skill:python", "Python", 1, jd_count=2),
    ]

    result = JobEvolutionService(FakeEvolutionReader(rows)).analyze(
        JobEvolutionQuery(
            job_id="job:backend-engineer",
            granularity=TimeGranularity.QUARTERLY,
        )
    )

    assert [point.period for point in result.timeline] == ["2023Q3", "2023Q4"]
    assert result.timeline[0].jd_count == 10
    assert result.timeline[0].skill_set[0].skill_jd_count == 6
    assert result.timeline[0].skill_set[0].demand_ratio == 0.6
    assert result.timeline[1].jd_count == 2
    assert any("仅覆盖 1-2 个月" in warning for warning in result.data_quality.warnings)


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


def test_prediction_requires_latest_six_periods_to_be_consecutive():
    rows = [
        _row(
            f"{year}Q1",
            f"{year}-01-01T00:00:00+08:00",
            "skill:python",
            "Python",
            20 + index * 10,
        )
        for index, year in enumerate(range(2019, 2025))
    ]

    result = JobEvolutionService(FakeEvolutionReader(rows)).analyze(
        JobEvolutionQuery(job_id="job:backend-engineer")
    )

    assert result.prediction.available is False
    assert "连续" in result.prediction.reason
    assert any("时间周期不连续" in warning for warning in result.data_quality.warnings)


def test_top_n_uses_stable_cross_period_skill_selection():
    rows = [
        _row("2024Q1", "2024-01-01T00:00:00+08:00", "skill:a", "A", 90),
        _row("2024Q1", "2024-01-01T00:00:00+08:00", "skill:b", "B", 80),
        _row("2024Q2", "2024-04-01T00:00:00+08:00", "skill:a", "A", 10),
        _row("2024Q2", "2024-04-01T00:00:00+08:00", "skill:b", "B", 80),
    ]

    result = JobEvolutionService(FakeEvolutionReader(rows)).analyze(
        JobEvolutionQuery(job_id="job:backend-engineer", top_n=1)
    )

    assert [[skill.skill_id for skill in point.skill_set] for point in result.timeline] == [
        ["skill:a"],
        ["skill:a"],
    ]
    assert result.timeline[1].skill_set[0].demand_ratio == 0.1


def test_duplicate_semantic_rows_are_not_double_counted_and_are_reported():
    duplicate = _row(
        "2024Q1", "2024-01-01T00:00:00+08:00", "skill:python", "Python", 40
    )
    result = JobEvolutionService(FakeEvolutionReader([duplicate, dict(duplicate)])).analyze(
        JobEvolutionQuery(job_id="job:backend-engineer")
    )

    metric = result.timeline[0].skill_set[0]
    assert metric.skill_jd_count == 40
    assert metric.demand_ratio == 0.4
    assert any("重复关系" in warning for warning in result.data_quality.warnings)


def test_duplicate_skill_names_with_different_ids_are_reported():
    rows = [
        _row("2024Q1", "2024-01-01T00:00:00+08:00", "skill:c++", "C++", 40),
        _row("2024Q1", "2024-01-01T00:00:00+08:00", "skill:cplusplus", "C++", 20),
    ]

    result = JobEvolutionService(FakeEvolutionReader(rows)).analyze(
        JobEvolutionQuery(job_id="job:backend-engineer")
    )

    assert any("同名技能对应多个标准 ID" in warning for warning in result.data_quality.warnings)


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


def test_get_evolution_api_accepts_prediction_horizon():
    reader = FakeEvolutionReader(_four_period_rows())
    app.dependency_overrides[get_job_evolution_service] = lambda: JobEvolutionService(reader)
    try:
        response = TestClient(app).get(
            "/api/jobs/job:backend-engineer/evolution-timeline",
            params={"prediction_horizon_months": 9},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["prediction"]["horizon_months"] == 9


class _CaptureResult(list):
    pass


class _CaptureSession:
    def __init__(self, driver):
        self.driver = driver

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def run(self, query, **parameters):
        self.driver.query = query
        self.driver.parameters = parameters
        return _CaptureResult()


class _CaptureDriver:
    def session(self, **kwargs):
        return _CaptureSession(self)


def test_evolution_repository_reads_only_matching_periodic_relationships():
    driver = _CaptureDriver()
    repository = object.__new__(Neo4jGraphRepository)
    repository.driver = driver

    rows = repository.get_job_evolution_rows(
        job_id="job:backend-engineer",
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        granularity="quarterly",
    )

    assert rows == []
    assert "r.period_key IS NOT NULL" in driver.query
    assert "r.period_key AS period" in driver.query
    assert "required_jd_count" in driver.query
    assert "r.observed_at" not in driver.query
    assert "quarterly" in driver.query
    assert driver.parameters["end"] == "2024-12-31"
