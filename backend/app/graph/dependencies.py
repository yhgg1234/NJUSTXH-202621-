"""FastAPI 依赖。"""

from functools import lru_cache

from app.graph.repository import Neo4jGraphRepository
from app.graph.service import GraphService


@lru_cache
def get_graph_repository() -> Neo4jGraphRepository:
    return Neo4jGraphRepository()


def get_graph_service() -> GraphService:
    return GraphService(get_graph_repository())

