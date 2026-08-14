"""子任务 2.3 图谱服务与 API 测试，不依赖真实 Neo4j。"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.graph.dependencies import get_graph_service
from app.graph.models import GraphImportRequest, GraphNode, GraphRelationship
from app.graph.repository import Neo4jGraphRepository
from app.graph.service import GraphService
from app.main import app


class FakeGraphRepository:
    def __init__(self) -> None:
        self.nodes = {}
        self.relationships = {}

    def initialize_schema(self):
        return ["constraint", "index"]

    def upsert_nodes(self, nodes, batch_id):
        for node in nodes:
            self.nodes[node.id] = node
        return len(nodes)

    def upsert_relationships(self, relationships, batch_id):
        for relationship in relationships:
            self.relationships[relationship.id] = relationship
        return len(relationships)

    def delete_stale_skill_snapshot_relationships(self, relationships):
        scopes = {}
        for relationship in relationships:
            period_key = relationship.properties.get("period_key")
            if period_key:
                scopes.setdefault((relationship.from_id, period_key), set()).add(
                    relationship.id
                )
        stale_ids = [
            relationship_id
            for relationship_id, relationship in self.relationships.items()
            if relationship.properties.get("period_key")
            and (
                relationship.from_id,
                relationship.properties["period_key"],
            )
            in scopes
            and relationship_id
            not in scopes[
                (
                    relationship.from_id,
                    relationship.properties["period_key"],
                )
            ]
        ]
        for relationship_id in stale_ids:
            del self.relationships[relationship_id]
        return len(stale_ids)

    def find_missing_node_ids(self, node_ids):
        return set(node_ids) - set(self.nodes)

    def get_subgraph(self, **kwargs):
        return {
            "nodes": [
                {"id": node.id, "label": node.name, "type": node.type, "properties": {}}
                for node in self.nodes.values()
            ],
            "links": [
                {
                    "id": rel.id,
                    "source": rel.from_id,
                    "target": rel.to_id,
                    "type": rel.type,
                    "properties": {},
                }
                for rel in self.relationships.values()
            ],
        }

    def get_filter_options(self):
        def options(node_type):
            return sorted(
                [
                    {"value": node.id, "label": node.name}
                    for node in self.nodes.values()
                    if node.type.value == node_type
                ],
                key=lambda item: (item["label"], item["value"]),
            )

        levels = sorted(
            {
                str(node.properties["level"])
                for node in self.nodes.values()
                if node.type.value == "Job" and node.properties.get("level")
            }
        )
        periods = sorted(
            {
                str(relationship.properties["period_key"])
                for relationship in self.relationships.values()
                if relationship.properties.get("period_key")
            },
            reverse=True,
        )
        return {
            "jobs": options("Job"),
            "tech_stacks": [
                {"value": item["label"], "label": item["label"]}
                for item in options("TechStack")
            ],
            "levels": [{"value": value, "label": value} for value in levels],
            "industries": [
                {"value": item["label"], "label": item["label"]}
                for item in options("Industry")
            ],
            "periods": [{"value": value, "label": value} for value in periods],
        }

    def get_stats(self):
        return {
            "node_count": len(self.nodes),
            "relationship_count": len(self.relationships),
            "nodes_by_type": [],
        }


def sample_request():
    return GraphImportRequest(
        batch_id="test-batch",
        nodes=[
            GraphNode(id="job:ai-agent", type="Job", name="AI Agent开发工程师"),
            GraphNode(id="skill:python", type="Skill", name="Python"),
        ],
        relationships=[
            GraphRelationship(
                id="job:ai-agent|REQUIRES_SKILL|skill:python",
                type="REQUIRES_SKILL",
                from_id="job:ai-agent",
                to_id="skill:python",
                properties={"importance": 0.95},
            )
        ],
    )


def test_service_imports_nodes_before_same_batch_relationships():
    repository = FakeGraphRepository()
    result = GraphService(repository).import_graph(sample_request())

    assert result.nodes_upserted == 2
    assert result.relationships_upserted == 1
    assert "job:ai-agent" in repository.nodes


def test_import_rejects_missing_external_endpoint_without_partial_write():
    repository = FakeGraphRepository()
    payload = GraphImportRequest(
        batch_id="bad-batch",
        relationships=[
            GraphRelationship(
                id="missing-rel",
                type="REQUIRES_SKILL",
                from_id="job:missing",
                to_id="skill:missing",
            )
        ],
    )

    client = TestClient(app)
    app.dependency_overrides[get_graph_service] = lambda: GraphService(repository)
    try:
        response = client.post("/api/graph/import", json=payload.model_dump(mode="json"))
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert repository.nodes == {}
    assert set(response.json()["detail"]["missing_node_ids"]) == {
        "job:missing",
        "skill:missing",
    }


def test_graph_api_import_query_and_stats():
    repository = FakeGraphRepository()
    client = TestClient(app)
    app.dependency_overrides[get_graph_service] = lambda: GraphService(repository)
    try:
        import_response = client.post(
            "/api/graph/import", json=sample_request().model_dump(mode="json")
        )
        subgraph_response = client.get("/api/graph/subgraph?job_id=job:ai-agent")
        options_response = client.get("/api/graph/filter-options")
        stats_response = client.get("/api/graph/stats")
    finally:
        app.dependency_overrides.clear()

    assert import_response.status_code == 200
    assert import_response.json()["relationships_upserted"] == 1
    assert len(subgraph_response.json()["nodes"]) == 2
    assert options_response.json()["jobs"] == [
        {"value": "job:ai-agent", "label": "AI Agent开发工程师"}
    ]
    assert stats_response.json()["node_count"] == 2


def test_task_2_2_1000_records_can_be_imported_through_graph_api():
    """使用 2.2 的千条联调批次验证 2.3 完整导入契约。"""

    data_dir = Path(__file__).parents[2] / "data" / "demo" / "task_2_2_1000"
    graph_payload = json.loads(
        (data_dir / "graph_import_batch.json").read_text(encoding="utf-8")
    )
    normalized_records = [
        json.loads(line)
        for line in (data_dir / "normalized_records.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    payload = GraphImportRequest.model_validate(graph_payload)

    source_nodes = {
        node.id: node for node in payload.nodes if node.type.value == "Source"
    }
    periodic_relationships = [
        relationship
        for relationship in payload.relationships
        if relationship.type.value in {"REQUIRES_SKILL", "BONUS_SKILL"}
        and relationship.properties.get("period_key")
    ]
    cpp_skills = [
        skill
        for record in normalized_records
        for skill in record.get("skills", [])
        if skill.get("raw_name", "").strip().lower()
        in {"c++", "cpp", "cplusplus"}
    ]
    cpp_nodes = [
        node
        for node in payload.nodes
        if node.id in {"skill:c++", "skill:cpp", "skill:cplusplus"}
    ]

    assert len(normalized_records) == 1000
    assert len(payload.nodes) == 1304
    assert len(payload.relationships) == 2377
    assert len(periodic_relationships) == 513
    assert cpp_skills
    assert {skill["canonical_id"] for skill in cpp_skills} == {"skill:c++"}
    assert [(node.id, node.name) for node in cpp_nodes] == [("skill:c++", "C++")]
    assert {item.properties["period_key"] for item in periodic_relationships} == {
        "2023-07",
        "2023-08",
        "2023-09",
        "2023-10",
    }
    assert all(
        source_nodes[record["source_id"]].properties["published_at"]
        == record["published_at"]
        for record in normalized_records
    )

    repository = FakeGraphRepository()
    client = TestClient(app)
    app.dependency_overrides[get_graph_service] = lambda: GraphService(repository)
    try:
        response = client.post(
            "/api/graph/import", json=payload.model_dump(mode="json")
        )
        options_response = client.get("/api/graph/filter-options")
        stats_response = client.get("/api/graph/stats")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "batch_id": payload.batch_id,
        "nodes_upserted": 1304,
        "relationships_upserted": 2377,
    }
    assert stats_response.json()["node_count"] == 1304
    assert stats_response.json()["relationship_count"] == 2377
    options = options_response.json()
    assert len(options["jobs"]) == 20
    assert len(options["tech_stacks"]) == 2
    assert {item["value"] for item in options["levels"]} == {
        "unknown",
        "mid",
        "senior",
    }
    assert len(options["industries"]) == 9
    assert [item["value"] for item in options["periods"]] == [
        "2023-10",
        "2023-09",
        "2023-08",
        "2023-07",
    ]


def test_reserved_properties_are_rejected():
    response = TestClient(app).post(
        "/api/graph/import",
        json={
            "batch_id": "reserved-property",
            "nodes": [
                {
                    "id": "skill:python",
                    "type": "Skill",
                    "name": "Python",
                    "properties": {"id": "overridden"},
                }
            ],
        },
    )
    assert response.status_code == 422


def test_periodic_skill_relationship_requires_consistent_time_and_counts():
    payload = {
        "id": "job:backend|REQUIRES_SKILL|skill:python|2024Q1",
        "type": "REQUIRES_SKILL",
        "from_id": "job:backend",
        "to_id": "skill:python",
        "properties": {
            "period_key": "2024Q1",
            "period_start": "2024-01-01T00:00:00+08:00",
            "skill_jd_count": 61,
            "job_jd_count": 100,
            "demand_ratio": 0.5,
        },
        "evidence_ids": ["source:2024q1"],
    }
    response = TestClient(app).put(
        "/api/graph/relationships/job:backend|REQUIRES_SKILL|skill:python|2024Q1",
        json=payload,
    )
    assert response.status_code == 422


def test_periodic_import_replaces_stale_relationships_in_same_job_period():
    repository = FakeGraphRepository()
    service = GraphService(repository)
    nodes = [
        GraphNode(id="job:backend", type="Job", name="后端工程师"),
        GraphNode(id="skill:python", type="Skill", name="Python"),
        GraphNode(id="skill:java", type="Skill", name="Java"),
    ]

    def periodic_relationship(skill_id: str, count: int) -> GraphRelationship:
        return GraphRelationship(
            id=f"job:backend|REQUIRES_SKILL|{skill_id}|2024Q1",
            type="REQUIRES_SKILL",
            from_id="job:backend",
            to_id=skill_id,
            properties={
                "period_key": "2024Q1",
                "period_start": "2024-01-01T00:00:00+08:00",
                "skill_jd_count": count,
                "job_jd_count": 100,
                "demand_ratio": count / 100,
            },
            evidence_ids=["source:2024q1"],
        )

    service.import_graph(
        GraphImportRequest(
            batch_id="period-v1",
            nodes=nodes,
            relationships=[
                periodic_relationship("skill:python", 60),
                periodic_relationship("skill:java", 50),
            ],
        )
    )
    service.import_graph(
        GraphImportRequest(
            batch_id="period-v2",
            relationships=[periodic_relationship("skill:python", 70)],
        )
    )

    assert set(repository.relationships) == {
        "job:backend|REQUIRES_SKILL|skill:python|2024Q1"
    }
    assert (
        repository.relationships[
            "job:backend|REQUIRES_SKILL|skill:python|2024Q1"
        ].properties["skill_jd_count"]
        == 70
    )


class _NodeUpsertResult:
    def __init__(self, count):
        self.count = count

    def single(self):
        return {"count": self.count}


class _NodeUpsertSession:
    def __init__(self, driver):
        self.driver = driver

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def run(self, query, **parameters):
        self.driver.query = query
        self.driver.parameters = parameters
        return _NodeUpsertResult(len(parameters["rows"]))


class _NodeUpsertDriver:
    def session(self, **kwargs):
        return _NodeUpsertSession(self)


def test_node_upsert_preserves_existing_aliases_and_source_ids():
    driver = _NodeUpsertDriver()
    repository = Neo4jGraphRepository(driver)

    count = repository.upsert_nodes(
        [
            GraphNode(
                id="skill:python",
                type="Skill",
                name="Python",
                aliases=["Python语言"],
                source_ids=["source:new-jd"],
            )
        ],
        "task-2.4-test",
    )

    assert count == 1
    assert "coalesce(n.aliases, []) + coalesce(row.aliases, [])" in driver.query
    assert "coalesce(n.source_ids, []) + coalesce(row.source_ids, [])" in driver.query
