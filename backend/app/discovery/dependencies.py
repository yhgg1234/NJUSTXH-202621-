"""子任务 2.4 的 FastAPI 依赖注入。"""

from functools import lru_cache

from fastapi import Depends

from app.config import settings
from app.discovery.data_source import NormalizedRecordReader
from app.discovery.service import DiscoveryService
from app.discovery.state import DiscoveryStateStore
from app.graph.dependencies import get_graph_service
from app.graph.service import GraphService


@lru_cache
def get_normalized_record_reader() -> NormalizedRecordReader:
    return NormalizedRecordReader(settings.DISCOVERY_NORMALIZED_PATH)


@lru_cache
def get_discovery_state_store() -> DiscoveryStateStore:
    return DiscoveryStateStore(settings.DISCOVERY_STATE_PATH)


def get_discovery_service(
    graph_service: GraphService = Depends(get_graph_service),
    reader: NormalizedRecordReader = Depends(get_normalized_record_reader),
    store: DiscoveryStateStore = Depends(get_discovery_state_store),
) -> DiscoveryService:
    """2.4 直接复用 2.3 服务，不通过额外 HTTP 或中间导出文件。"""

    return DiscoveryService(graph_service, reader, store)
