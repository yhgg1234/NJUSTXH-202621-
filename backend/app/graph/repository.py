"""Neo4j 数据访问层。所有动态标签/关系类型均来自枚举白名单。"""

from collections.abc import Iterable
from typing import Any

from neo4j import Driver, GraphDatabase

from app.config import settings
from app.graph.models import GraphNode, GraphRelationship, NodeType, RelationshipType


def _compact(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}


def _json_compatible(value: Any) -> Any:
    """将 Neo4j 时间类型递归转换为 REST 可序列化值。"""
    if isinstance(value, dict):
        return {key: _json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_compatible(item) for item in value]
    iso_format = getattr(value, "iso_format", None)
    if callable(iso_format):
        return iso_format()
    return value


def _node_parameters(node: GraphNode, batch_id: str) -> dict[str, Any]:
    base = {
        "id": node.id,
        "name": node.name,
        "aliases": node.aliases,
        "confidence": node.confidence,
        "source_ids": node.source_ids,
        "observed_at": node.observed_at,
        "valid_from": node.valid_from,
        "valid_to": node.valid_to,
        "last_batch_id": batch_id,
    }
    base.update(node.properties)
    return _compact(base)


def _relationship_parameters(rel: GraphRelationship, batch_id: str) -> dict[str, Any]:
    base = {
        "id": rel.id,
        "confidence": rel.confidence,
        "evidence_ids": rel.evidence_ids,
        "observed_at": rel.observed_at,
        "valid_from": rel.valid_from,
        "valid_to": rel.valid_to,
        "last_batch_id": batch_id,
    }
    base.update(rel.properties)
    return _compact(base)


class Neo4jGraphRepository:
    """知识图谱仓储；driver 可注入，便于测试。"""

    def __init__(self, driver: Driver | None = None) -> None:
        self.driver = driver or GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )

    def close(self) -> None:
        self.driver.close()

    def verify_connectivity(self) -> None:
        self.driver.verify_connectivity()

    def initialize_schema(self) -> list[str]:
        statements = [
            f"CREATE CONSTRAINT {node_type.value.lower()}_id_unique IF NOT EXISTS "
            f"FOR (n:{node_type.value}) REQUIRE n.id IS UNIQUE"
            for node_type in NodeType
        ]
        statements.extend(
            [
                "CREATE INDEX graph_name IF NOT EXISTS FOR (n:GraphEntity) ON (n.name)",
                "CREATE INDEX job_level IF NOT EXISTS FOR (n:Job) ON (n.level)",
                "CREATE INDEX observed_at IF NOT EXISTS FOR (n:GraphEntity) ON (n.observed_at)",
            ]
        )
        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            for statement in statements:
                session.run(statement).consume()
        return statements

    def upsert_nodes(self, nodes: Iterable[GraphNode], batch_id: str) -> int:
        grouped: dict[NodeType, list[dict[str, Any]]] = {}
        for node in nodes:
            grouped.setdefault(node.type, []).append(_node_parameters(node, batch_id))

        total = 0
        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            for node_type, rows in grouped.items():
                query = (
                    f"UNWIND $rows AS row MERGE (n:GraphEntity:{node_type.value} {{id: row.id}}) "
                    "ON CREATE SET n.created_at = datetime() "
                    "SET n += row, n.updated_at = datetime() RETURN count(n) AS count"
                )
                total += session.run(query, rows=rows).single()["count"]
        return total

    def upsert_relationships(
        self, relationships: Iterable[GraphRelationship], batch_id: str
    ) -> int:
        grouped: dict[RelationshipType, list[dict[str, Any]]] = {}
        for rel in relationships:
            row = {
                "from_id": rel.from_id,
                "to_id": rel.to_id,
                "properties": _relationship_parameters(rel, batch_id),
            }
            grouped.setdefault(rel.type, []).append(row)

        total = 0
        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            for relationship_type, rows in grouped.items():
                query = (
                    "UNWIND $rows AS row "
                    "MATCH (source:GraphEntity {id: row.from_id}) "
                    "MATCH (target:GraphEntity {id: row.to_id}) "
                    f"MERGE (source)-[r:{relationship_type.value} {{id: row.properties.id}}]->(target) "
                    "ON CREATE SET r.created_at = datetime() "
                    "SET r += row.properties, r.updated_at = datetime() RETURN count(r) AS count"
                )
                total += session.run(query, rows=rows).single()["count"]
        return total

    def find_missing_node_ids(self, node_ids: set[str]) -> set[str]:
        if not node_ids:
            return set()
        query = "MATCH (n:GraphEntity) WHERE n.id IN $ids RETURN collect(n.id) AS ids"
        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            found = set(session.run(query, ids=list(node_ids)).single()["ids"])
        return node_ids - found

    def get_subgraph(
        self,
        *,
        job_id: str | None,
        tech_stack: str | None,
        level: str | None,
        industry: str | None,
        limit: int,
    ) -> dict[str, Any]:
        query = """
        MATCH (job:Job)
        WHERE ($job_id IS NULL OR job.id = $job_id)
          AND ($level IS NULL OR job.level = $level)
          AND ($industry IS NULL OR EXISTS {
            MATCH (job)-[:APPLIES_TO_INDUSTRY]->(i:Industry) WHERE i.name = $industry
          })
          AND ($tech_stack IS NULL OR EXISTS {
            MATCH (job)-[:REQUIRES_SKILL|BONUS_SKILL]->(:Skill)-[:BELONGS_TO_STACK]->(t:TechStack)
            WHERE t.name = $tech_stack
          })
        WITH job LIMIT $limit
        OPTIONAL MATCH path=(job)-[r]-(neighbor:GraphEntity)
        WITH collect(DISTINCT job) + collect(DISTINCT neighbor) AS raw_nodes,
             collect(DISTINCT r) AS relationships
        UNWIND raw_nodes AS node
        WITH collect(DISTINCT node) AS nodes, relationships
        RETURN [node IN nodes WHERE node IS NOT NULL | {
                 id: node.id, label: node.name,
                 type: [label IN labels(node) WHERE label <> 'GraphEntity'][0],
                 properties: properties(node)
               }] AS nodes,
               [rel IN relationships WHERE rel IS NOT NULL | {
                 id: rel.id, source: startNode(rel).id, target: endNode(rel).id,
                 type: type(rel), properties: properties(rel)
               }] AS links
        """
        parameters = {
            "job_id": job_id,
            "tech_stack": tech_stack,
            "level": level,
            "industry": industry,
            "limit": limit,
        }
        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            record = session.run(query, **parameters).single()
        result = {
            "nodes": record["nodes"] if record else [],
            "links": record["links"] if record else [],
        }
        return _json_compatible(result)

    def get_stats(self) -> dict[str, Any]:
        query = """
        CALL () { MATCH (n:GraphEntity) RETURN count(n) AS node_count }
        CALL () { MATCH (:GraphEntity)-[r]->(:GraphEntity) RETURN count(r) AS relationship_count }
        CALL () {
          MATCH (n:GraphEntity) UNWIND [x IN labels(n) WHERE x <> 'GraphEntity'] AS label
          WITH label, count(*) AS type_count
          RETURN collect({type: label, count: type_count}) AS nodes_by_type
        }
        RETURN node_count, relationship_count, nodes_by_type
        """
        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            record = session.run(query).single()
        result = dict(record) if record else {
            "node_count": 0,
            "relationship_count": 0,
            "nodes_by_type": [],
        }
        return _json_compatible(result)
