"""3.3 与 2.3 图谱子图适配测试。"""

from app.matching.graph_adapter import load_job_profile_from_graph
from app.matching import graph_adapter


class FakeGraphService:
    def get_subgraph(self, **kwargs):
        assert kwargs["job_id"] == "job:test"
        return {
            "nodes": [
                {
                    "id": "job:test",
                    "label": "测试岗位",
                    "type": "Job",
                    "properties": {"description": "来自图谱的岗位"},
                },
                {
                    "id": "skill:python",
                    "label": "Python",
                    "type": "Skill",
                    "properties": {"aliases": ["Python语言"]},
                },
                {
                    "id": "stack:backend",
                    "label": "后端开发",
                    "type": "TechStack",
                    "properties": {},
                },
                {
                    "id": "industry:ai",
                    "label": "人工智能",
                    "type": "Industry",
                    "properties": {},
                },
            ],
            "links": [
                {
                    "id": "rel-1",
                    "source": "job:test",
                    "target": "skill:python",
                    "type": "REQUIRES_SKILL",
                    "properties": {"importance": 0.8, "proficiency": "熟悉", "years": 2},
                },
                {
                    "id": "rel-2",
                    "source": "skill:python",
                    "target": "stack:backend",
                    "type": "BELONGS_TO_STACK",
                    "properties": {},
                },
                {
                    "id": "rel-3",
                    "source": "job:test",
                    "target": "industry:ai",
                    "type": "APPLIES_TO_INDUSTRY",
                    "properties": {},
                },
            ],
        }


def test_load_job_profile_from_graph(monkeypatch):
    monkeypatch.setattr(graph_adapter, "get_graph_service", lambda: FakeGraphService())

    profile = load_job_profile_from_graph("job:test")

    assert profile is not None
    assert profile.title == "测试岗位"
    assert profile.skills[0].name == "Python"
    assert profile.skills[0].aliases == ["Python语言"]
    assert profile.skills[0].importance == 0.8
    assert profile.tech_stacks == ["后端开发"]
    assert profile.industries == ["人工智能"]
