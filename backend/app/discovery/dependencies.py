"""2.4 新岗位发现 —— FastAPI 依赖注入。"""

from functools import lru_cache

from app.discovery.service import DiscoveryService


@lru_cache
def get_discovery_service() -> DiscoveryService:
    return DiscoveryService()
