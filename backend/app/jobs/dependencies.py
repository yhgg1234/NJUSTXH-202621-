"""子任务 3.1 的 FastAPI 依赖。"""

from fastapi import Depends

from app.graph.dependencies import get_graph_service
from app.graph.service import GraphService
from app.jobs.service import JobEvolutionService


def get_job_evolution_service(
    graph_service: GraphService = Depends(get_graph_service),
) -> JobEvolutionService:
    """以 2.3 图谱服务作为 3.1 的只读数据源。"""

    return JobEvolutionService(graph_service)
