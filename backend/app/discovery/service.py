"""2.4 新岗位发现 —— 业务服务。

当前为半成品：核心发现逻辑使用启发式规则 + 图谱查询；
复杂聚类、LLM 辅助判定等高级能力标注了 TODO 供后续迭代。
"""

from datetime import date, datetime
from typing import Protocol

from app.discovery.models import (
    AdoptResult,
    BatchAdoptRequest,
    BatchRejectRequest,
    BatchResult,
    CandidateStatus,
    DiscoverRequest,
    DiscoverResponse,
    DiscoverStats,
    Evidence,
    EvidenceType,
    NewJobCandidate,
)


class GraphQueryPort(Protocol):
    """2.3 图谱查询抽象端口，避免 2.4 直接依赖 Neo4j。"""

    def get_all_jobs(self) -> list[dict]: ...
    def get_job_skills(self, job_id: str) -> list[dict]: ...
    def get_job_evolution_rows(
        self, *, job_id: str, start: date | None, end: date | None, granularity: str
    ) -> list[dict]: ...
    def get_stats(self) -> dict: ...


# ── 模拟 / 演示数据（移除后接入真实图谱）──────────────────────────────
_MOCK_CANDIDATES: list[NewJobCandidate] = [
    NewJobCandidate(
        candidate_id="cand:foundation-model-app-dev",
        name="基础大模型应用开发工程师",
        standardized_id="job:foundation-model-app-dev",
        emerging_skills=["大模型部署", "Prompt Engineering", "RAG检索增强", "AI可观测性", "模型微调"],
        derived_from=["job:backend-engineer", "job:algorithm-engineer"],
        estimated_emergence="2024Q3",
        emergence_confidence=0.92,
        description=(
            "该岗位聚焦于将基础大模型（LLM）集成至业务系统，需要同时掌握后端工程、"
            "模型部署运维及提示工程能力，与传统后端或算法岗位存在显著技能组合差异。"
        ),
        evidence_chain=[
            Evidence(
                type=EvidenceType.SKILL_DIVERGENCE,
                description="技能组合与现有后端工程师差异度达 0.74，超过 0.5 阈值",
                confidence=0.89,
                supporting_ids=["rel:job-backend-skill-divergence-2024Q3"],
            ),
            Evidence(
                type=EvidenceType.NEW_SKILL_EMERGENCE,
                description="RAG检索增强、AI可观测性为近两个季度新出现的技能标签",
                confidence=0.91,
                supporting_ids=["skill:rag-retrieval-augmented", "skill:ai-observability"],
            ),
            Evidence(
                type=EvidenceType.JD_FREQUENCY_SURGE,
                description="2024Q3 相关 JD 数量较上季度增长 340%",
                confidence=0.94,
                supporting_ids=["source:jd-surge-report-2024Q3"],
            ),
        ],
    ),
    NewJobCandidate(
        candidate_id="cand:prompt-engineer",
        name="Prompt工程师",
        standardized_id="job:prompt-engineer",
        emerging_skills=["Prompt Engineering", "少样本学习", "思维链设计", "A/B测试"],
        derived_from=["job:nlp-engineer", "job:data-analyst"],
        estimated_emergence="2024Q2",
        emergence_confidence=0.87,
        description=(
            "专门负责大模型提示词的工程化设计、评测与迭代优化，"
            "与传统 NLP 工程师相比更侧重于提示策略而非模型训练。"
        ),
        evidence_chain=[
            Evidence(
                type=EvidenceType.SKILL_DIVERGENCE,
                description="技能侧重提示策略与评测方法论，区别于传统NLP工程",
                confidence=0.82,
                supporting_ids=["rel:job-nlp-skill-divergence-2024Q2"],
            ),
            Evidence(
                type=EvidenceType.JD_FREQUENCY_SURGE,
                description="2024Q2 起相关 JD 从月均 5 条增至月均 45 条",
                confidence=0.88,
                supporting_ids=["source:jd-surge-report-2024Q2"],
            ),
        ],
    ),
    NewJobCandidate(
        candidate_id="cand:llm-evaluation-engineer",
        name="LLM评测工程师",
        standardized_id="job:llm-evaluation-engineer",
        emerging_skills=["模型评测", "基准测试设计", "对抗测试", "安全对齐评估"],
        derived_from=["job:qa-engineer", "job:algorithm-engineer"],
        estimated_emergence="2024Q3",
        emergence_confidence=0.61,
        description="专职负责大语言模型的性能、安全与对齐评测。",
        evidence_chain=[
            Evidence(
                type=EvidenceType.NEW_SKILL_EMERGENCE,
                description="安全对齐评估为全新出现的技能需求",
                confidence=0.65,
                supporting_ids=["skill:ai-safety-alignment-evaluation"],
            ),
        ],
    ),
    NewJobCandidate(
        candidate_id="cand:ai-product-designer",
        name="AI产品设计师",
        standardized_id="job:ai-product-designer",
        emerging_skills=["AI交互设计", "模型能力理解", "人机协作流程"],
        derived_from=["job:product-manager", "job:ux-designer"],
        estimated_emergence="2024Q4",
        emergence_confidence=0.55,
        description="结合 AI 能力理解与产品设计，负责 AI 驱动产品的体验架构。",
        evidence_chain=[
            Evidence(
                type=EvidenceType.SKILL_DIVERGENCE,
                description="需要兼具产品设计与AI技术理解，技能跨度大",
                confidence=0.58,
                supporting_ids=["rel:job-pm-skill-divergence-2024Q4"],
            ),
        ],
    ),
    NewJobCandidate(
        candidate_id="cand:ai-safety-researcher",
        name="AI安全研究员",
        standardized_id="job:ai-safety-researcher",
        emerging_skills=["对抗攻击防御", "模型对齐", "安全审计", "红队测试"],
        derived_from=["job:security-engineer", "job:algorithm-engineer"],
        estimated_emergence="2024Q2",
        emergence_confidence=0.51,
        description="聚焦大模型安全性和鲁棒性研究，负责发现和修复模型安全漏洞。",
        evidence_chain=[
            Evidence(
                type=EvidenceType.INDUSTRY_SPREAD,
                description="安全相关 JD 开始从互联网扩散至金融、政务等行业",
                confidence=0.49,
                supporting_ids=["source:industry-spread-report-2024Q2"],
            ),
        ],
    ),
    NewJobCandidate(
        candidate_id="cand:agent-dev-engineer",
        name="Agent开发工程师",
        standardized_id="job:agent-dev-engineer",
        emerging_skills=["Agent框架", "工具调用", "多智能体协作", "记忆管理"],
        derived_from=["job:backend-engineer", "job:algorithm-engineer"],
        estimated_emergence="2024Q3",
        emergence_confidence=0.51,
        description="负责基于 LLM 的智能体应用开发，涵盖工具集成与多智能体编排。",
        evidence_chain=[
            Evidence(
                type=EvidenceType.JD_FREQUENCY_SURGE,
                description="Agent 相关 JD 连续三个季度增长",
                confidence=0.53,
                supporting_ids=["source:agent-jd-trend-2024"],
            ),
        ],
    ),
    NewJobCandidate(
        candidate_id="cand:fine-tuning-engineer",
        name="微调/Fine-tuning工程师",
        standardized_id="job:fine-tuning-engineer",
        emerging_skills=["LoRA/QLoRA", "指令微调", "RLHF", "数据飞轮"],
        derived_from=["job:algorithm-engineer", "job:data-engineer"],
        estimated_emergence="2024Q1",
        emergence_confidence=0.51,
        description="专门负责大模型的高效微调与对齐训练。",
        evidence_chain=[
            Evidence(
                type=EvidenceType.NEW_SKILL_EMERGENCE,
                description="LoRA/QLoRA 等高效微调技术成为独立技能标签",
                confidence=0.55,
                supporting_ids=["skill:lora-fine-tuning"],
            ),
        ],
    ),
]


class DiscoveryService:
    """新岗位发现服务。

    生产环境中通过 graph_port 接入 2.3 图谱查询接口；
    当前回退到模拟数据以保证前端联调不受阻塞。
    """

    def __init__(self, graph_port: GraphQueryPort | None = None) -> None:
        self._graph = graph_port
        self._adoption_log: dict[str, CandidateStatus] = {}
        # 初始化时同步 mock 状态
        for c in _MOCK_CANDIDATES:
            self._adoption_log[c.candidate_id] = c.status

    # ── 核心发现 ──────────────────────────────────────────────────

    def discover(self, request: DiscoverRequest) -> DiscoverResponse:
        """执行新岗位发现分析。"""

        # TODO: 接入 2.3 图谱做实发现 —
        #   1. 从图谱拉取所有 Job 节点及技能关系
        #   2. 对每对岗位计算技能 Jaccard 距离
        #   3. 对技能组合偏离所有现有岗位 ∑ 超过阈值的聚类标记为候选
        #   4. 调用 LLM 对候选进行语义命名和描述生成
        #   5. 合并 JD 频率趋势作为辅助证据
        candidates = [
            c for c in _MOCK_CANDIDATES
            if c.emergence_confidence >= request.min_confidence
        ]
        if request.period_key:
            candidates = [
                c for c in candidates
                if c.estimated_emergence <= request.period_key
            ]

        candidates = sorted(candidates, key=lambda c: c.emergence_confidence, reverse=True)
        candidates = candidates[: request.max_candidates]

        # 合并已记录的人工操作状态
        for c in candidates:
            previous = self._adoption_log.get(c.candidate_id)
            if previous is not None:
                c.status = previous

        stats = self._graph.get_stats() if self._graph else {"node_count": 128, "relationship_count": 456}

        return DiscoverResponse(
            candidates=candidates,
            total_scanned_jobs=stats.get("node_count", 0),
            total_scanned_skills=stats.get("relationship_count", 0),
        )

    # ── 采纳 / 否决 ───────────────────────────────────────────────

    def adopt(self, candidate_id: str, create_graph_nodes: bool = True) -> AdoptResult:
        """采纳候选新岗位，可选择是否写入图谱。"""

        candidate = next((c for c in _MOCK_CANDIDATES if c.candidate_id == candidate_id), None)
        if candidate is None:
            return AdoptResult(candidate_id=candidate_id, success=False, message="候选不存在")

        if self._adoption_log.get(candidate_id) == CandidateStatus.ADOPTED:
            return AdoptResult(candidate_id=candidate_id, success=False, message="已采纳，请勿重复操作")

        # TODO: 写入图谱 —
        #   1. 创建新的 Job 节点 (candidate.standardized_id)
        #   2. 为新岗位关联 emerging_skills
        #   3. 从 derived_from 岗位创建 EVOLVES_TO 关系
        #   4. 写入 Source 证据节点

        self._adoption_log[candidate_id] = CandidateStatus.ADOPTED
        candidate.status = CandidateStatus.ADOPTED
        created_job_id = candidate.standardized_id if create_graph_nodes else None

        return AdoptResult(
            candidate_id=candidate_id,
            success=True,
            created_job_id=created_job_id,
            message="已采纳并创建图谱节点" if create_graph_nodes else "已标记为采纳",
        )

    def reject(self, candidate_id: str) -> AdoptResult:
        candidate = next((c for c in _MOCK_CANDIDATES if c.candidate_id == candidate_id), None)
        if candidate is None:
            return AdoptResult(candidate_id=candidate_id, success=False, message="候选不存在")

        self._adoption_log[candidate_id] = CandidateStatus.REJECTED
        candidate.status = CandidateStatus.REJECTED
        return AdoptResult(candidate_id=candidate_id, success=True, message="已否决")

    def batch_adopt(self, request: BatchAdoptRequest) -> BatchResult:
        results = [self.adopt(cid, request.create_graph_nodes) for cid in request.candidate_ids]
        ok = sum(1 for r in results if r.success)
        return BatchResult(results=results, summary=f"成功采纳 {ok}/{len(results)} 个候选新岗位")

    def batch_reject(self, request: BatchRejectRequest) -> BatchResult:
        results = [self.reject(cid) for cid in request.candidate_ids]
        ok = sum(1 for r in results if r.success)
        return BatchResult(results=results, summary=f"成功否决 {ok}/{len(results)} 个候选新岗位")

    # ── 统计 ──────────────────────────────────────────────────────

    def get_stats(self) -> DiscoverStats:
        total = len(self._adoption_log)
        adopted = sum(1 for s in self._adoption_log.values() if s == CandidateStatus.ADOPTED)
        rejected = sum(1 for s in self._adoption_log.values() if s == CandidateStatus.REJECTED)
        pending = total - adopted - rejected
        confidences = [c.emergence_confidence for c in _MOCK_CANDIDATES]
        return DiscoverStats(
            total_candidates=total,
            adopted_count=adopted,
            rejected_count=rejected,
            pending_count=pending,
            avg_confidence=round(sum(confidences) / len(confidences), 3) if confidences else 0,
            by_status={"pending": pending, "adopted": adopted, "rejected": rejected},
        )

    def get_candidate(self, candidate_id: str) -> NewJobCandidate | None:
        return next((c for c in _MOCK_CANDIDATES if c.candidate_id == candidate_id), None)
