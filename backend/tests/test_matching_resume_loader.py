"""3.2 结构化简历到 3.3 人岗匹配的数据加载测试。"""

import json

from app.matching.resume_loader import display_resume_name, load_processed_resumes


def test_loader_normalizes_nullable_3_2_fields(tmp_path):
    payload = {
        "id": "resume-nullable",
        "name": "基本信息",
        "education": [{"school": "某大学", "degree": "本科", "major": None}],
        "skills": [
            {
                "name": "Python",
                "normalized_id": "skill:python",
                "proficiency": "熟悉",
                "years": 2,
                "evidence": ["项目经验"],
            }
        ],
        "projects": [
            {
                "name": "数据分析项目",
                "role": None,
                "description": None,
                "tech_stacks": ["Python"],
                "achievements": [],
            }
        ],
        "industries": ["互联网"],
        "certificates": [],
        "years_of_experience": None,
        "confidence": 0.8,
    }
    (tmp_path / "resume.json").write_text(json.dumps(payload), encoding="utf-8")

    profiles = load_processed_resumes(tmp_path)

    profile = profiles["resume-nullable"]
    assert profile.education[0].major == ""
    assert profile.projects[0].role == ""
    assert profile.years_of_experience == 0
    assert display_resume_name(profile) == "候选人 nullable"


def test_loader_accepts_batch_json(tmp_path):
    payload = [
        {"id": "resume-a", "name": "甲", "skills": []},
        {"id": "resume-b", "name": "乙", "skills": []},
    ]
    (tmp_path / "batch.json").write_text(json.dumps(payload), encoding="utf-8")

    profiles = load_processed_resumes(tmp_path)

    assert list(profiles) == ["resume-a", "resume-b"]
