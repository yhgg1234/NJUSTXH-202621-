"""3.3 人岗匹配诊断与差距分析服务。"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.matching.llm import SparkLiteClient
from app.matching.graph_adapter import list_graph_jobs
from app.matching.resume_loader import display_resume_name, load_mongodb_resumes, load_processed_resumes
from app.matching.models import (
    DemoOptionsResponse,
    DimensionScore,
    GapAnalysisReport,
    JobCompareItem,
    JobCompareResponse,
    JobProfile,
    JobSkillRequirement,
    LearningPathResponse,
    LearningPhase,
    MatchReport,
    ResumeEducationProfile,
    ResumeProfile,
    ResumeProjectProfile,
    ResumeSkillProfile,
    SkillGap,
)


WEIGHTS = {
    "skill": 0.55,
    "experience": 0.20,
    "education": 0.10,
    "industry": 0.15,
}

LEVEL_SCORE = {
    "了解": 1,
    "熟悉": 2,
    "掌握": 2,
    "精通": 3,
    "专家": 4,
}

DEGREE_SCORE = {
    "中专": 1,
    "大专": 2,
    "专科": 2,
    "本科": 3,
    "学士": 3,
    "硕士": 4,
    "研究生": 4,
    "博士": 5,
}


class MatchingService:
    """人岗匹配应用服务。

    启动时优先加载 data/processed/resumes 的 3.2 结构化结果；目录为空时
    使用内置演示数据，保证并行开发阶段仍可运行。
    """

    def __init__(
        self,
        llm_client: SparkLiteClient | None = None,
        resumes: dict[str, ResumeProfile] | None = None,
        jobs: dict[str, JobProfile] | None = None,
    ) -> None:
        self.llm_client = llm_client or SparkLiteClient()
        self.reports: dict[str, MatchReport] = {}
        self.history: list[MatchReport] = []
        if resumes is None:
            file_resumes = load_processed_resumes()
            mongo_resumes = load_mongodb_resumes()
            loaded_resumes = {**file_resumes, **mongo_resumes}
        else:
            loaded_resumes = resumes
            file_resumes = {}
            mongo_resumes = {}
        self.resumes = loaded_resumes or _demo_resumes()
        self.resume_data_source = "mongodb" if mongo_resumes else ("processed" if file_resumes else "demo")
        self.graph_jobs: dict[str, JobProfile] = list_graph_jobs()
        self.jobs = self.graph_jobs or (jobs or _demo_jobs())

    def demo_options(self) -> DemoOptionsResponse:
        # 懒刷新 MongoDB 简历，让新上传的简历立即出现在选项中
        mongo_resumes = load_mongodb_resumes()
        if mongo_resumes:
            self.resumes = {**self.resumes, **mongo_resumes}
        return DemoOptionsResponse(
            resumes=[
                {"id": item.id, "name": display_resume_name(item)}
                for item in self.resumes.values()
            ],
            jobs=[{"id": item.id, "title": item.title} for item in self.jobs.values()],
        )

    async def match(self, resume_id: str, job_id: str) -> MatchReport:
        resume, job = self._get_pair(resume_id, job_id)
        dimensions = self._score_dimensions(resume, job)
        score_map = {item.dimension: item.score for item in dimensions}
        total_score = round(sum(item.score * item.weight for item in dimensions), 1)
        level = _assessment_level(total_score)
        recommendations, llm_generated = await self._build_recommendations(
            resume, job, dimensions, total_score
        )
        report = MatchReport(
            match_id=f"match-{uuid4().hex[:12]}",
            resume_id=resume.id,
            resume_name=display_resume_name(resume),
            job_id=job.id,
            job_title=job.title,
            total_score=total_score,
            skill_score=score_map["skill"],
            experience_score=score_map["experience"],
            education_score=score_map["education"],
            industry_score=score_map["industry"],
            dimensions=dimensions,
            overall_assessment=_assessment_text(total_score, dimensions),
            assessment_level=level,
            recommendations=recommendations,
            llm_generated=llm_generated,
            data_source=self.resume_data_source,
            matched_at=datetime.now(timezone.utc).isoformat(),
        )
        self.reports[report.match_id] = report
        self.history.insert(0, report)
        self.history = self.history[:30]
        return report

    def get_report(self, match_id: str) -> MatchReport:
        if match_id not in self.reports:
            raise KeyError(match_id)
        return self.reports[match_id]

    async def gap_analysis(self, resume_id: str, job_id: str) -> GapAnalysisReport:
        resume, job = self._get_pair(resume_id, job_id)
        gaps = self._skill_gaps(resume, job)
        summary, llm_generated = await self._build_gap_summary(resume, job, gaps)
        return GapAnalysisReport(
            resume_id=resume.id,
            job_id=job.id,
            job_title=job.title,
            skill_gaps=gaps,
            total_missing=sum(1 for item in gaps if item.status == "missing"),
            total_matched=sum(1 for item in gaps if item.status == "matched"),
            total_surplus=sum(1 for item in gaps if item.status == "surplus"),
            summary=summary,
            llm_generated=llm_generated,
        )

    async def learning_path(
        self,
        resume_id: str,
        job_id: str,
        target_months: int,
    ) -> LearningPathResponse:
        resume, job = self._get_pair(resume_id, job_id)
        gaps = [item for item in self._skill_gaps(resume, job) if item.status == "missing"]
        llm_path = await self._build_llm_learning_path(resume, job, gaps, target_months)
        if llm_path:
            return llm_path
        return _template_learning_path(resume.id, job, gaps, target_months, False)

    async def multi_match(self, resume_id: str, job_ids: list[str]) -> JobCompareResponse:
        comparisons: list[JobCompareItem] = []
        for job_id in job_ids:
            report = await self.match(resume_id, job_id)
            skill_dimension = next(item for item in report.dimensions if item.dimension == "skill")
            comparisons.append(
                JobCompareItem(
                    job_id=report.job_id,
                    job_title=report.job_title,
                    match_score=report.total_score,
                    assessment_level=report.assessment_level,
                    advantages=skill_dimension.matched_items[:4],
                    disadvantages=skill_dimension.missing_items[:4],
                )
            )
        comparisons.sort(key=lambda item: item.match_score, reverse=True)
        best = comparisons[0]
        return JobCompareResponse(
            resume_id=resume_id,
            comparisons=comparisons,
            best_match_job_id=best.job_id,
            recommendation=(
                f"当前最推荐投递「{best.job_title}」，综合匹配度 {best.match_score} 分；"
                f"建议优先补齐 {', '.join(best.disadvantages[:2]) or '关键项目证据'}。"
            ),
        )

    def list_history(self) -> list[MatchReport]:
        return self.history

    def _get_pair(self, resume_id: str, job_id: str) -> tuple[ResumeProfile, JobProfile]:
        if resume_id not in self.resumes:
            raise KeyError(f"resume not found: {resume_id}")
        return self.resumes[resume_id], self._get_job(job_id)

    def _get_job(self, job_id: str) -> JobProfile:
        if job_id not in self.jobs:
            raise KeyError(f"job not found: {job_id}")
        return self.jobs[job_id]

    def _score_dimensions(self, resume: ResumeProfile, job: JobProfile) -> list[DimensionScore]:
        skill_dimension = self._score_skills(resume, job)
        experience_dimension = self._score_experience(resume, job)
        education_dimension = self._score_education(resume, job)
        industry_dimension = self._score_industry(resume, job)
        return [skill_dimension, experience_dimension, education_dimension, industry_dimension]

    def _score_skills(self, resume: ResumeProfile, job: JobProfile) -> DimensionScore:
        gaps = self._skill_gaps(resume, job)
        matched = [item for item in gaps if item.status == "matched"]
        missing = [item for item in gaps if item.status == "missing"]
        surplus = [item for item in gaps if item.status == "surplus"]

        weighted_total = sum(_skill_weight(skill) for skill in job.skills) or 1.0
        weighted_score = 0.0
        resume_lookup = _resume_skill_lookup(resume)
        for skill in job.skills:
            match = _find_resume_skill(resume_lookup, skill)
            if not match:
                continue
            level_score = _level_ratio(match.proficiency, skill.proficiency)
            years_score = _years_ratio(match.years, skill.years)
            weighted_score += _skill_weight(skill) * (0.75 + 0.15 * level_score + 0.10 * years_score)

        score = round(min(100.0, weighted_score / weighted_total * 100), 1)
        return DimensionScore(
            dimension="skill",
            label="技能匹配",
            score=score,
            weight=WEIGHTS["skill"],
            matched_items=[item.skill_name for item in matched],
            missing_items=[item.skill_name for item in missing],
            surplus_items=[item.skill_name for item in surplus],
            explanation="基于必备/加分技能、熟练度和年限进行加权评分。",
        )

    def _score_experience(self, resume: ResumeProfile, job: JobProfile) -> DimensionScore:
        if not job.experience_years:
            score = 80.0 if resume.years_of_experience else 60.0
            missing: list[str] = []
        else:
            minimum, preferred = job.experience_years
            if resume.years_of_experience >= preferred:
                score = 100.0
            elif resume.years_of_experience >= minimum:
                span = max(preferred - minimum, 1)
                score = 82.0 + (resume.years_of_experience - minimum) / span * 18.0
            else:
                score = max(35.0, resume.years_of_experience / max(minimum, 1) * 75.0)
            missing = [] if resume.years_of_experience >= minimum else [f"{minimum} 年以上相关经验"]
        projects = [project.name for project in resume.projects[:3]]
        return DimensionScore(
            dimension="experience",
            label="经验匹配",
            score=round(score, 1),
            weight=WEIGHTS["experience"],
            matched_items=projects,
            missing_items=missing,
            explanation="基于工作年限、相关项目经历和岗位年限要求评分。",
        )

    def _score_education(self, resume: ResumeProfile, job: JobProfile) -> DimensionScore:
        required = _degree_rank(job.education_required or "")
        current = max((_degree_rank(item.degree) for item in resume.education), default=0)
        if required == 0:
            score = 85.0
            missing = []
        elif current >= required:
            score = 100.0
            missing = []
        else:
            score = max(45.0, current / required * 80.0) if current else 45.0
            missing = [job.education_required or "目标学历要求"]
        matched = [item.degree for item in resume.education if item.degree]
        return DimensionScore(
            dimension="education",
            label="学历匹配",
            score=round(score, 1),
            weight=WEIGHTS["education"],
            matched_items=matched,
            missing_items=missing,
            explanation="基于简历最高学历与岗位最低学历要求评分。",
        )

    def _score_industry(self, resume: ResumeProfile, job: JobProfile) -> DimensionScore:
        resume_terms = {_norm(item) for item in resume.industries}
        project_terms = {_norm(stack) for project in resume.projects for stack in project.tech_stacks}
        job_industries = {_norm(item) for item in job.industries}
        job_stacks = {_norm(item) for item in job.tech_stacks}
        industry_hits = resume_terms & job_industries
        stack_hits = project_terms & job_stacks
        total = len(job_industries) + len(job_stacks)
        hit_count = len(industry_hits) + len(stack_hits)
        score = 65.0 if total == 0 else min(100.0, 45.0 + hit_count / total * 55.0)
        return DimensionScore(
            dimension="industry",
            label="行业/项目匹配",
            score=round(score, 1),
            weight=WEIGHTS["industry"],
            matched_items=list(industry_hits | stack_hits),
            missing_items=list((job_industries | job_stacks) - (industry_hits | stack_hits)),
            explanation="基于行业背景、技术栈和项目主题与目标岗位的重合度评分。",
        )

    def _skill_gaps(self, resume: ResumeProfile, job: JobProfile) -> list[SkillGap]:
        resume_lookup = _resume_skill_lookup(resume)
        gaps: list[SkillGap] = []
        matched_keys: set[str] = set()

        for skill in job.skills:
            match = _find_resume_skill(resume_lookup, skill)
            importance = "required" if skill.required else "bonus"
            if match:
                matched_keys.add(_skill_key(match))
                gaps.append(
                    SkillGap(
                        skill_name=skill.name,
                        status="matched",
                        importance=importance,
                        current_level=match.proficiency,
                        required_level=skill.proficiency,
                        evidence="; ".join(match.evidence) or "简历技能列表命中",
                        suggestion="继续用项目成果或量化指标证明该能力。",
                    )
                )
            else:
                gaps.append(
                    SkillGap(
                        skill_name=skill.name,
                        status="missing",
                        importance=importance,
                        current_level=None,
                        required_level=skill.proficiency,
                        evidence="目标岗位要求该技能，但简历结构化结果未命中。",
                        suggestion=f"补齐 {skill.name} 的基础知识，并完成一个可展示的岗位相关项目。",
                    )
                )

        job_keys = {_norm(skill.normalized_id or skill.name) for skill in job.skills}
        for skill in resume.skills:
            key = _skill_key(skill)
            if key not in matched_keys and key not in job_keys:
                gaps.append(
                    SkillGap(
                        skill_name=skill.name,
                        status="surplus",
                        importance="bonus",
                        current_level=skill.proficiency,
                        evidence="简历具备该技能，但目标岗位未明确要求。",
                        suggestion="可作为差异化优势保留，若篇幅有限可弱化描述。",
                    )
                )
        return gaps

    async def _build_recommendations(
        self,
        resume: ResumeProfile,
        job: JobProfile,
        dimensions: list[DimensionScore],
        total_score: float,
    ) -> tuple[list[str], bool]:
        missing = next(item for item in dimensions if item.dimension == "skill").missing_items
        payload = {
            "resume_name": resume.name,
            "job_title": job.title,
            "total_score": total_score,
            "dimension_scores": {item.label: item.score for item in dimensions},
            "missing_skills": missing,
            "request": "返回 JSON：{\"recommendations\": [\"建议1\", \"建议2\", \"建议3\"]}",
        }
        data = await self.llm_client.chat_json(
            "你是人岗匹配诊断助手，只返回合法 JSON，不要输出 Markdown。",
            payload,
        )
        if data and isinstance(data.get("recommendations"), list):
            return [str(item) for item in data["recommendations"][:5]], True
        return _template_recommendations(job, missing), False

    async def _build_gap_summary(
        self,
        resume: ResumeProfile,
        job: JobProfile,
        gaps: list[SkillGap],
    ) -> tuple[str, bool]:
        payload = {
            "resume_name": resume.name,
            "job_title": job.title,
            "gaps": [item.model_dump() for item in gaps],
            "request": "返回 JSON：{\"summary\": \"不超过120字的差距分析总结\"}",
        }
        data = await self.llm_client.chat_json(
            "你是职业能力差距分析助手，只返回合法 JSON，不要输出 Markdown。",
            payload,
        )
        if data and data.get("summary"):
            return str(data["summary"]), True
        missing = [item.skill_name for item in gaps if item.status == "missing"]
        matched = [item.skill_name for item in gaps if item.status == "matched"]
        return (
            f"已匹配 {len(matched)} 项核心能力，主要差距集中在 "
            f"{', '.join(missing[:4]) or '岗位项目证据'}，建议按优先级补齐。"
        ), False

    async def _build_llm_learning_path(
        self,
        resume: ResumeProfile,
        job: JobProfile,
        gaps: list[SkillGap],
        target_months: int,
    ) -> LearningPathResponse | None:
        payload = {
            "resume_name": resume.name,
            "job_title": job.title,
            "target_months": target_months,
            "missing_skills": [item.skill_name for item in gaps],
            "request": (
                "返回 JSON，字段为 phases 和 overall_suggestions。phases 必须正好 3 个，"
                "每个阶段包含 title、topics、courses、projects、certificates、milestones。"
            ),
        }
        data = await self.llm_client.chat_json(
            "你是学习路径规划助手，只返回合法 JSON，不要输出 Markdown。",
            payload,
            temperature=0.4,
        )
        if not data or not isinstance(data.get("phases"), list):
            return None
        phases: list[LearningPhase] = []
        weeks = max(4, target_months * 4 // 3)
        for index, item in enumerate(data["phases"][:3], start=1):
            if not isinstance(item, dict):
                return None
            phases.append(
                LearningPhase(
                    phase=index,
                    title=str(item.get("title") or f"阶段 {index}"),
                    duration_weeks=weeks,
                    topics=[str(value) for value in item.get("topics", [])],
                    courses=[str(value) for value in item.get("courses", [])],
                    projects=[str(value) for value in item.get("projects", [])],
                    certificates=[str(value) for value in item.get("certificates", [])],
                    milestones=[str(value) for value in item.get("milestones", [])],
                )
            )
        if len(phases) < 3:
            return None
        return LearningPathResponse(
            resume_id=resume.id,
            job_id=job.id,
            job_title=job.title,
            total_months=target_months,
            phases=phases,
            overall_suggestions=[str(value) for value in data.get("overall_suggestions", [])],
            llm_generated=True,
        )


def _template_learning_path(
    resume_id: str,
    job: JobProfile,
    gaps: list[SkillGap],
    target_months: int,
    llm_generated: bool,
) -> LearningPathResponse:
    missing = [item.skill_name for item in gaps] or ["岗位核心项目能力"]
    duration = max(4, target_months * 4 // 3)
    first = missing[:2]
    second = missing[2:4] or missing[:2]
    third = missing[4:6] or missing[:2]
    return LearningPathResponse(
        resume_id=resume_id,
        job_id=job.id,
        job_title=job.title,
        total_months=target_months,
        phases=[
            LearningPhase(
                phase=1,
                title="基础补齐",
                duration_weeks=duration,
                topics=first,
                courses=[f"{skill} 入门与核心概念" for skill in first],
                projects=[f"完成一个包含 {', '.join(first)} 的最小实践 Demo"],
                milestones=["能够解释核心概念并写入简历技能证据"],
            ),
            LearningPhase(
                phase=2,
                title="核心能力强化",
                duration_weeks=duration,
                topics=second,
                courses=[f"{skill} 工程化应用" for skill in second],
                projects=[f"围绕「{job.title}」复刻一个真实业务场景项目"],
                milestones=["形成项目 README、架构图和可运行演示"],
            ),
            LearningPhase(
                phase=3,
                title="项目实战与作品集",
                duration_weeks=duration,
                topics=third,
                courses=["岗位 JD 复盘与面试题整理"],
                projects=[f"整合 {job.title} 端到端作品集并部署演示"],
                certificates=["按岗位需要选择云计算、AI 或项目管理相关认证"],
                milestones=["完成作品集、量化指标和面试讲述稿"],
            ),
        ],
        overall_suggestions=[
            "优先补齐必备技能，再补充加分技能。",
            "每个差距项至少准备一个项目证据，避免只停留在技能名罗列。",
            "学习路径完成后重新运行匹配诊断，观察技能缺口变化。",
        ],
        llm_generated=llm_generated,
    )


def _template_recommendations(job: JobProfile, missing: list[str]) -> list[str]:
    if not missing:
        return [
            f"当前与「{job.title}」匹配度较高，建议强化项目指标和业务成果描述。",
            "补充与岗位技术栈相关的部署、测试和性能优化证据。",
            "准备 1-2 个可演示项目，提升面试中的可信度。",
        ]
    return [
        f"优先补齐 {', '.join(missing[:3])} 等必备能力。",
        f"围绕「{job.title}」完成一个端到端项目，并在简历中写清职责、技术栈和结果。",
        "将学习成果转化为证据：代码仓库、演示链接、性能指标或业务效果。",
    ]


def _assessment_level(score: float) -> str:
    if score >= 85:
        return "高度匹配"
    if score >= 70:
        return "基本匹配"
    if score >= 55:
        return "存在明显差距"
    return "暂不匹配"


def _assessment_text(score: float, dimensions: list[DimensionScore]) -> str:
    weakest = min(dimensions, key=lambda item: item.score)
    strongest = max(dimensions, key=lambda item: item.score)
    return (
        f"综合匹配度 {score} 分，{_assessment_level(score)}。"
        f"优势维度为{strongest.label}，短板维度为{weakest.label}。"
    )


def _skill_weight(skill: JobSkillRequirement) -> float:
    required_factor = 1.0 if skill.required else 0.55
    return max(0.1, skill.importance) * required_factor


def _level_ratio(current: str | None, required: str | None) -> float:
    if not required:
        return 1.0
    current_rank = LEVEL_SCORE.get(current or "", 1)
    required_rank = LEVEL_SCORE.get(required, 1)
    return min(1.0, current_rank / max(required_rank, 1))


def _years_ratio(current: float | None, required: float | None) -> float:
    if not required:
        return 1.0
    return min(1.0, (current or 0.0) / required)


def _degree_rank(text: str) -> int:
    for key, value in DEGREE_SCORE.items():
        if key in text:
            return value
    return 0


def _resume_skill_lookup(resume: ResumeProfile) -> dict[str, ResumeSkillProfile]:
    lookup: dict[str, ResumeSkillProfile] = {}
    for skill in resume.skills:
        lookup[_skill_key(skill)] = skill
        lookup[_norm(skill.name)] = skill
    return lookup


def _find_resume_skill(
    lookup: dict[str, ResumeSkillProfile],
    required: JobSkillRequirement,
) -> ResumeSkillProfile | None:
    candidates = [required.normalized_id, required.name, *required.aliases]
    for candidate in candidates:
        if candidate and _norm(candidate) in lookup:
            return lookup[_norm(candidate)]
    return None


def _skill_key(skill: ResumeSkillProfile) -> str:
    return _norm(skill.normalized_id or skill.name)


def _norm(text: str | None) -> str:
    return (text or "").strip().lower().replace(" ", "").replace("_", "-")


def _demo_resumes() -> dict[str, ResumeProfile]:
    items = [
        ResumeProfile(
            id="resume-001",
            name="张同学 - 后端/AI应用方向",
            education=[ResumeEducationProfile(school="南京某高校", degree="本科", major="软件工程")],
            years_of_experience=2.0,
            industries=["人工智能", "互联网"],
            skills=[
                ResumeSkillProfile(name="Python", normalized_id="skill:python", proficiency="熟悉", years=2, evidence=["企业知识库问答系统"]),
                ResumeSkillProfile(name="FastAPI", normalized_id="skill:fastapi", proficiency="熟悉", years=1, evidence=["后端接口开发"]),
                ResumeSkillProfile(name="RAG", normalized_id="skill:rag", proficiency="了解", years=0.5, evidence=["知识库问答 Demo"]),
                ResumeSkillProfile(name="MySQL", normalized_id="skill:mysql", proficiency="熟悉", years=2),
                ResumeSkillProfile(name="Vue", normalized_id="skill:vue", proficiency="了解", years=1),
            ],
            projects=[
                ResumeProjectProfile(
                    name="企业知识库问答系统",
                    role="后端开发",
                    description="基于 FastAPI 和向量检索构建知识库问答 Demo。",
                    tech_stacks=["Python", "FastAPI", "RAG", "MySQL"],
                )
            ],
            certificates=["CET-6"],
            confidence=0.91,
        ),
        ResumeProfile(
            id="resume-002",
            name="李同学 - 数据分析方向",
            education=[ResumeEducationProfile(school="南京某高校", degree="硕士", major="数据科学")],
            years_of_experience=1.0,
            industries=["金融科技"],
            skills=[
                ResumeSkillProfile(name="Python", normalized_id="skill:python", proficiency="精通", years=3),
                ResumeSkillProfile(name="机器学习", normalized_id="skill:machine-learning", proficiency="熟悉", years=2),
                ResumeSkillProfile(name="数据可视化", normalized_id="skill:data-visualization", proficiency="熟悉", years=2),
                ResumeSkillProfile(name="SQL", normalized_id="skill:sql", proficiency="熟悉", years=2),
            ],
            projects=[
                ResumeProjectProfile(
                    name="金融风控特征分析",
                    role="算法与分析",
                    tech_stacks=["Python", "机器学习", "数据可视化", "SQL"],
                )
            ],
            confidence=0.9,
        ),
    ]
    return {item.id: item for item in items}


def _demo_jobs() -> dict[str, JobProfile]:
    items = [
        JobProfile(
            id="job:ai-agent-engineer",
            title="AI Agent开发工程师",
            description="负责基于大模型的 Agent 应用、工具调用和业务系统集成。",
            skills=[
                JobSkillRequirement(name="Python", normalized_id="skill:python", required=True, proficiency="熟悉", years=2, importance=0.95),
                JobSkillRequirement(name="LangChain", normalized_id="skill:langchain", required=True, proficiency="熟悉", years=1, importance=0.9),
                JobSkillRequirement(name="RAG", normalized_id="skill:rag", required=True, proficiency="熟悉", importance=0.85, aliases=["检索增强生成"]),
                JobSkillRequirement(name="Agent工具调用", normalized_id="skill:agent-tool-use", required=True, proficiency="了解", importance=0.8),
                JobSkillRequirement(name="FastAPI", normalized_id="skill:fastapi", required=False, proficiency="熟悉", importance=0.55),
                JobSkillRequirement(name="向量数据库", normalized_id="skill:vector-db", required=False, proficiency="了解", importance=0.5, aliases=["Milvus", "FAISS"]),
            ],
            education_required="本科及以上",
            experience_years=(2, 5),
            industries=["人工智能", "互联网"],
            tech_stacks=["Python", "RAG", "LangChain", "Agent"],
        ),
        JobProfile(
            id="job:data-analyst",
            title="数据分析师",
            description="负责业务指标分析、可视化看板、统计建模与数据洞察。",
            skills=[
                JobSkillRequirement(name="SQL", normalized_id="skill:sql", required=True, proficiency="熟悉", importance=0.95),
                JobSkillRequirement(name="Python", normalized_id="skill:python", required=True, proficiency="熟悉", importance=0.85),
                JobSkillRequirement(name="数据可视化", normalized_id="skill:data-visualization", required=True, proficiency="熟悉", importance=0.8),
                JobSkillRequirement(name="机器学习", normalized_id="skill:machine-learning", required=False, proficiency="了解", importance=0.45),
            ],
            education_required="本科及以上",
            experience_years=(1, 3),
            industries=["金融科技", "互联网"],
            tech_stacks=["Python", "SQL", "数据可视化"],
        ),
        JobProfile(
            id="job:backend-engineer",
            title="Python后端开发工程师",
            description="负责业务后端接口、数据库设计、服务部署和性能优化。",
            skills=[
                JobSkillRequirement(name="Python", normalized_id="skill:python", required=True, proficiency="熟悉", years=2, importance=0.9),
                JobSkillRequirement(name="FastAPI", normalized_id="skill:fastapi", required=True, proficiency="熟悉", importance=0.75),
                JobSkillRequirement(name="MySQL", normalized_id="skill:mysql", required=True, proficiency="熟悉", importance=0.7),
                JobSkillRequirement(name="Docker", normalized_id="skill:docker", required=False, proficiency="了解", importance=0.45),
            ],
            education_required="本科及以上",
            experience_years=(2, 4),
            industries=["互联网"],
            tech_stacks=["Python", "FastAPI", "MySQL", "Docker"],
        ),
    ]
    return {item.id: item for item in items}
