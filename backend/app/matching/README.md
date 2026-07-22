# 子任务 3.3：人岗匹配诊断与差距分析

本模块负责将结构化简历画像与岗位能力要求进行对比，输出多维度匹配分、技能差距分析、多岗位对比和学习路径规划。模块按任务书要求引入大模型，但核心匹配分数由可解释规则和岗位能力图谱数据计算；科大讯飞 Spark Lite 主要用于生成报告摘要、改进建议和学习路径文本。

## 当前实现范围

| 能力 | 接口 | 状态 |
|---|---|---|
| 单岗位匹配诊断 | `POST /api/matching/match` | 已实现 |
| 匹配报告查询 | `GET /api/matching/match/{match_id}` | 已实现 |
| 多岗位对比 | `POST /api/matching/multi-match` | 已实现 |
| 差距分析 | `POST /api/matching/gap-analysis` | 已实现 |
| 学习路径规划 | `POST /api/matching/learning-path` | 已实现 |
| 匹配历史 | `GET /api/matching/history` | 已实现 |
| 匹配选项 | `GET /api/matching/options` | 已实现，返回可匹配的简历和岗位 |

3.3 启动时会优先加载 `data/processed/resumes/*.json` 中的 3.2 结构化简历；目录为空时才回退到内置演示简历，便于并行开发。岗位画像会优先从 2.3 知识图谱的 `get_subgraph(job_id=...)` 读取，并转换为 3.3 的 `JobProfile`；当 Neo4j 未启动、图谱中没有该岗位或岗位缺少技能关系时，才回退到内置演示岗位数据。

每个 JSON 可以是一份简历对象，也可以是简历对象数组。加载器兼容上游可能出现的 `null` 学历专业、项目角色和工作年限：它们只会在内存中转为 3.3 的默认值，不改写原始 JSON。姓名为空、解析为“基本信息/相关技能”或包含联系方式时，前端显示为“候选人 + 简历编号”，避免出现空白选项或暴露联系方式。

## Spark Lite 配置

使用科大讯飞 Spark Lite HTTP 接口。复制 `.env.example` 为 `.env` 后填写：

```env
LLM_API_URL=https://spark-api-open.xf-yun.com/v1/chat/completions
LLM_API_KEY=你的HTTP服务APIPassword
LLM_MODEL=lite
```

注意：

1. `LLM_API_KEY` 填 HTTP 服务认证信息中的 `APIPassword`，不是 WebSocket 的 `APPID / APISecret / APIKey`。
2. 不要把 `.env` 提交到 Git。
3. 未配置 `LLM_API_KEY`、网络不可用或 Spark Lite 返回异常时，模块会自动降级为模板化建议，核心评分和差距分析仍可正常运行。
4. 前端只在点击“开始诊断”后请求模型；一次完整诊断会分别生成匹配建议、差距摘要和学习路径，通常产生 3 次 Spark Lite 调用。

## 匹配算法

综合分采用四维加权：

```text
综合分 = 技能匹配 55% + 经验匹配 20% + 学历匹配 10% + 行业/项目匹配 15%
```

技能匹配会考虑：

- 必备技能与加分技能权重
- 技能名称或 `normalized_id` 命中
- 熟练度是否达到岗位要求
- 技能年限是否达到岗位要求

差距项分为三类：

- `matched`：岗位要求且简历已具备
- `missing`：岗位要求但简历未命中
- `surplus`：简历具备但目标岗位未明确要求

LLM 不参与最终分数计算，只根据结构化结果生成自然语言建议，便于结果可复现和验收。

## 3.2 简历解析模块输入要求

3.2 模块最终应向 3.3 提供如下结构。字段名可通过接口适配层映射，但语义应保持一致。

```json
{
  "id": "resume-001",
  "name": "张三",
  "education": [
    {
      "school": "南京某高校",
      "degree": "本科",
      "major": "软件工程"
    }
  ],
  "skills": [
    {
      "name": "Python",
      "normalized_id": "skill:python",
      "proficiency": "熟悉",
      "years": 2,
      "evidence": ["企业知识库问答系统", "后端开发经历"]
    }
  ],
  "projects": [
    {
      "name": "企业知识库问答系统",
      "role": "后端开发",
      "description": "基于 FastAPI 和向量检索构建知识库问答 Demo。",
      "tech_stacks": ["Python", "FastAPI", "RAG"],
      "achievements": ["完成接口设计与检索链路"]
    }
  ],
  "industries": ["人工智能", "互联网"],
  "certificates": ["CET-6"],
  "years_of_experience": 2,
  "confidence": 0.91
}
```

对 3.2 的关键要求：

1. 技能必须尽量提供标准化 `normalized_id`，例如 `skill:python`，避免同义词影响匹配。
2. `proficiency` 建议统一为 `了解 / 熟悉 / 精通 / 专家`。
3. `evidence` 应指出技能来自哪段工作、项目或证书，便于报告解释。
4. `years_of_experience` 建议由工作经历时间自动计算，并允许人工修正。
5. 项目经历中的 `tech_stacks` 会参与行业/项目匹配分。

## 岗位与图谱输入要求

岗位管理或知识图谱模块应向 3.3 提供如下岗位画像：

```json
{
  "id": "job:ai-agent-engineer",
  "title": "AI Agent开发工程师",
  "description": "负责基于大模型的 Agent 应用、工具调用和业务系统集成。",
  "skills": [
    {
      "name": "Python",
      "normalized_id": "skill:python",
      "required": true,
      "proficiency": "熟悉",
      "years": 2,
      "importance": 0.95,
      "aliases": ["Python语言"]
    }
  ],
  "education_required": "本科及以上",
  "experience_years": [2, 5],
  "industries": ["人工智能", "互联网"],
  "tech_stacks": ["Python", "RAG", "LangChain", "Agent"],
  "certificates": []
}
```

对岗位/图谱模块的关键要求：

1. 必备技能使用 `required=true`，加分技能使用 `required=false`。
2. `importance` 范围为 0-1，可来自 JD 频次、图谱关系权重或人工标注。
3. `aliases` 用于技能同义词匹配。
4. `experience_years` 使用 `[最低要求, 偏好年限]`。
5. 图谱中的 `REQUIRES_SKILL`、`BONUS_SKILL`、`REQUIRES_EDUCATION`、`APPLIES_TO_INDUSTRY` 可直接映射为上述字段。

## 与 2.3 图谱模块的对接方式

当前 3.3 会通过 2.3 的服务层读取子图：

```python
get_graph_service().get_subgraph(job_id=job_id, limit=120)
```

子图到岗位画像的映射规则：

| 图谱结构 | 3.3 字段 |
|---|---|
| `Job` 节点 `id/name/description` | `JobProfile.id/title/description` |
| `Job -[:REQUIRES_SKILL]-> Skill` | 必备技能 |
| `Job -[:BONUS_SKILL]-> Skill` | 加分技能 |
| 关系属性 `importance` | 技能权重 |
| 关系属性 `frequency` | 无 `importance` 时折算为技能权重 |
| 关系属性 `proficiency` | 目标熟练度 |
| 关系属性 `years` | 技能年限要求 |
| `Skill.aliases` | 技能别名匹配 |
| `Skill -[:BELONGS_TO_STACK]-> TechStack` | 岗位技术栈 |
| `Job -[:APPLIES_TO_INDUSTRY]-> Industry` | 岗位行业 |
| `Job -[:REQUIRES_CERTIFICATE]-> Certificate` | 证书要求 |
| `Job -[:REQUIRES_EDUCATION]-> Education` | 学历要求 |

因此 2.3/2.2 导图时建议在关系 `properties` 中尽量提供：

```json
{
  "importance": 0.95,
  "frequency": 18,
  "proficiency": "熟悉",
  "years": 2
}
```

如果图谱中只有 `frequency` 而没有 `importance`，3.3 会按频次折算一个 0.1-1.0 的权重。

## API 示例

单岗位匹配：

```json
POST /api/matching/match
{
  "resume_id": "resume-001",
  "job_id": "job:ai-agent-engineer"
}
```

差距分析：

```json
POST /api/matching/gap-analysis
{
  "resume_id": "resume-001",
  "job_id": "job:ai-agent-engineer"
}
```

学习路径：

```json
POST /api/matching/learning-path
{
  "resume_id": "resume-001",
  "job_id": "job:ai-agent-engineer",
  "target_months": 6
}
```

多岗位对比：

```json
POST /api/matching/multi-match
{
  "resume_id": "resume-001",
  "job_ids": ["job:ai-agent-engineer", "job:data-analyst", "job:backend-engineer"]
}
```

## 验收对应关系

| 任务书要求 | 模块实现 |
|---|---|
| 多维度匹配算法 | 四维加权评分 |
| 技能缺失/过剩/匹配 | `SkillGap.status` 三分类 |
| 每个差距项有建议 | `SkillGap.suggestion` |
| 大模型生成改进建议 | Spark Lite 生成 recommendations / summary / learning path |
| 学习路径至少 3 阶段 | `LearningPathResponse.phases` 固定校验 3 阶段 |
| 多目标岗位对比 | `/multi-match` |
| 展示清晰易懂 | 前端 `MatchReport.vue` 诊断工作台 |
