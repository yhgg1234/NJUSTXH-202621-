"""真实 Neo4j 联调；默认跳过，设置 RUN_NEO4J_INTEGRATION=1 后启用。"""

import json
import os
from pathlib import Path

import pytest

from app.graph.models import GraphImportRequest
from app.graph.repository import Neo4jGraphRepository
from app.graph.service import GraphService


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_NEO4J_INTEGRATION") != "1",
    reason="set RUN_NEO4J_INTEGRATION=1 to test against Neo4j",
)


def test_sample_import_and_query_against_neo4j():
    sample_path = Path(__file__).parents[2] / "data" / "demo" / "graph_import_sample.json"
    payload = GraphImportRequest.model_validate(json.loads(sample_path.read_text(encoding="utf-8")))
    repository = Neo4jGraphRepository()
    service = GraphService(repository)

    try:
        repository.verify_connectivity()
        assert len(service.initialize_schema()) == 12
        result = service.import_graph(payload)
        assert result.nodes_upserted == 5
        assert result.relationships_upserted == 4

        subgraph = service.get_subgraph(
            job_id="job:ai-agent-engineer",
            tech_stack=None,
            level=None,
            industry=None,
            limit=10,
        )
        assert any(node["id"] == "job:ai-agent-engineer" for node in subgraph["nodes"])
        assert any(link["type"] == "REQUIRES_SKILL" for link in subgraph["links"])
        assert service.get_stats()["node_count"] >= 5
    finally:
        with repository.driver.session() as session:
            session.run(
                "MATCH (n:GraphEntity {last_batch_id: $batch_id}) DETACH DELETE n",
                batch_id=payload.batch_id,
            ).consume()
        repository.close()

