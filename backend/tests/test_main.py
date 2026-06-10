"""
基础测试：验证 FastAPI 应用可正常启动并响应健康检查
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root():
    """测试根路由"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_health_check():
    """测试健康检查接口"""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["backend"] == "running"
