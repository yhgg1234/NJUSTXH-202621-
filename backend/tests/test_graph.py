"""子任务 2.3 图谱服务与 API 测试，不依赖真实 Neo4j。"""

from fastapi.testclient import TestClient

from app.graph.dependencies import get_graph_service
from app.graph.models import GraphImportRequest, GraphNode, GraphRelationship
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
        stats_response = client.get("/api/graph/stats")
    finally:
        app.dependency_overrides.clear()

    assert import_response.status_code == 200
    assert import_response.json()["relationships_upserted"] == 1
    assert len(subgraph_response.json()["nodes"]) == 2
    assert stats_response.json()["node_count"] == 2


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

