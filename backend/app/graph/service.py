"""图谱应用服务。"""

from datetime import date
from typing import Protocol

from app.graph.models import GraphImportRequest, GraphImportResult, GraphNode, GraphRelationship


class GraphRepository(Protocol):
    def initialize_schema(self) -> list[str]: ...
    def upsert_nodes(self, nodes: list[GraphNode], batch_id: str) -> int: ...
    def upsert_relationships(self, relationships: list[GraphRelationship], batch_id: str) -> int: ...
    def delete_stale_skill_snapshot_relationships(
        self, relationships: list[GraphRelationship]
    ) -> int: ...
    def find_missing_node_ids(self, node_ids: set[str]) -> set[str]: ...
    def get_subgraph(self, **kwargs): ...
    def get_filter_options(self): ...
    def get_job_evolution_rows(
        self, *, job_id: str, start: date | None, end: date | None, granularity: str
    ): ...
    def get_stats(self): ...


class MissingEndpointError(ValueError):
    def __init__(self, node_ids: set[str]) -> None:
        self.node_ids = node_ids
        super().__init__(f"relationship endpoints do not exist: {', '.join(sorted(node_ids))}")


class GraphService:
    def __init__(self, repository: GraphRepository) -> None:
        self.repository = repository

    def initialize_schema(self) -> list[str]:
        return self.repository.initialize_schema()

    def import_graph(self, request: GraphImportRequest) -> GraphImportResult:
        endpoint_ids = {endpoint for rel in request.relationships for endpoint in (rel.from_id, rel.to_id)}
        incoming_node_ids = {node.id for node in request.nodes}
        missing = self.repository.find_missing_node_ids(endpoint_ids - incoming_node_ids)
        if missing:
            raise MissingEndpointError(missing)
        node_count = self.repository.upsert_nodes(request.nodes, request.batch_id)
        relationship_count = self.repository.upsert_relationships(
            request.relationships, request.batch_id
        )
        # 周期数据以 (job_id, period_key) 为完整快照。先成功写入新关系，再清理
        # 同一范围内本次未提供的旧关系，保证晚到数据重算具备幂等替换语义。
        self.repository.delete_stale_skill_snapshot_relationships(request.relationships)
        return GraphImportResult(
            batch_id=request.batch_id,
            nodes_upserted=node_count,
            relationships_upserted=relationship_count,
        )

    def upsert_node(self, node: GraphNode) -> int:
        return self.repository.upsert_nodes([node], "manual")

    def upsert_relationship(self, relationship: GraphRelationship) -> int:
        missing = self.repository.find_missing_node_ids(
            {relationship.from_id, relationship.to_id}
        )
        if missing:
            raise MissingEndpointError(missing)
        return self.repository.upsert_relationships([relationship], "manual")

    def get_subgraph(self, **filters):
        filters.setdefault("period", None)
        filters.setdefault("as_of", None)
        filters.setdefault("include_history", False)
        return self.repository.get_subgraph(**filters)

    def get_filter_options(self):
        return self.repository.get_filter_options()

    def get_job_evolution_rows(
        self, *, job_id: str, start: date | None, end: date | None, granularity: str
    ):
        """向 3.1 提供已标准化的周期化岗位—技能关系。"""

        return self.repository.get_job_evolution_rows(
            job_id=job_id, start=start, end=end, granularity=granularity
        )

    def get_stats(self):
        return self.repository.get_stats()
