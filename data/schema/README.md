# 2.1 / 2.2 上游数据交付契约（供 2.3、2.4、3.1、3.3 使用）

> 契约版本：`1.0.0`　　状态：冻结基线　　默认时区：`Asia/Shanghai (UTC+08:00)`

本文是 2.1 信息抽取、2.2 实体标准化与下游 2.3、2.4、3.1、3.3 之间的**唯一规范性数据契约**。各模块 README 只解释本模块如何消费这些数据；若描述冲突，以本文为准。

“必须 / MUST”表示验收不通过就不能进入相应下游；“建议 / SHOULD”表示允许为空，但会降低分析或匹配质量。冻结后不得直接删除、改名或改变既有字段语义。任何破坏性变更必须升级契约主版本并提供转换脚本。

## 1. 为什么必须交付三层数据

| 交付层 | 生产者 | 主要消费者 | 不能被其他层替代的原因 |
|---|---|---|---|
| A. `extracted_records`：逐文档抽取结果 | 2.1 | 2.2、质量抽检 | 保留原文、原始名称、模型证据和抽取版本，便于纠错与重跑。 |
| B. `normalized_records`：逐 JD 标准化结果 | 2.2 | 2.4、周期聚合管线 | 新岗位聚类需要逐 JD 的岗位-技能组合、职责和来源，聚合图会丢失这些信息。 |
| C. `graph_import_batches`：图谱节点和关系批次 | 2.2/聚合管线 | 2.3、3.1、3.3 | 2.3 需要稳定实体 ID；3.1 需要周期快照；3.3 需要最新岗位画像。 |

数据流固定为：

```text
采集原文
  -> 2.1 extracted_records（不覆盖原始字段）
  -> 2.2 normalized_records（逐 JD 对齐，保留 source_id）
  -> 周期聚合 / 图谱转换
  -> graph_import_batches
  -> 2.3 Neo4j
       -> 2.4 新岗位发现与变更日志
       -> 3.1 月度/季度演化
       -> 3.3 最新岗位画像
```

## 2. 通用规则

### 2.1 文件与编码

- 权威交换格式为 UTF-8 `JSONL`，一行一条记录；大批量文件建议按 `来源/年份/月` 分区。
- 可以使用 `.xlsx` 交接，但必须“一行一条 JD”，不得合并单元格；数组/对象列必须保存为合法 JSON，不得用分号拼接后丢失层级。
- 时间必须是带时区的 ISO-8601，例如 `2025-04-16T09:30:00+08:00`。禁止只写 `2025年4月`、Excel 序列号或本地无时区时间。
- 数量、比例、布尔值必须使用对应 JSON 类型，不能写成字符串 `"18"`、`"0.6"`、`"是"`。
- 未知标量使用 `null`，未知数组使用 `[]`；禁止使用空字符串、`未知`、`暂无`、`--` 代替空值。

### 2.2 ID 稳定性

| ID | 规则 | 示例 |
|---|---|---|
| `jd_id` | 同一来源内跨批次稳定。优先使用平台外部 ID；否则使用规范化 URL 的 SHA-256。不得使用 Excel 行号。 | `zhaopin:CCL1439887430J40933789215` |
| `source_id` | 固定为 `source:` + `jd_id`；行业报告/技术文章同理。 | `source:zhaopin:CCL1439887430J40933789215` |
| 标准实体 ID | 由 2.2 分配，小写 ASCII slug，跨来源、跨批次、跨年份不变。 | `job:backend-engineer`、`skill:python` |
| `batch_id` | 一个交付批次唯一且可追溯，推荐 `模块-来源-日期-序号`。 | `task-2.2-zhaopin-20250417-01` |
| 周期关系 ID | `岗位ID|关系类型|技能ID|period_key`。同一期重跑必须复用原 ID。 | `job:backend-engineer|REQUIRES_SKILL|skill:python|2025Q2` |

实体名称修正、别名增加不能生成新 ID；只有语义确实不同的实体才能生成新 ID。2.2 必须保存旧名到 `aliases`。若实体发生合并，必须保留 `merged_from_ids` 或单独的映射表，不能静默替换。

### 2.3 去重与溯源

1. 先按 `(source_platform, external_id)` 去重；没有外部 ID 时按规范化 URL 去重；仍无法判断时才使用正文 `content_hash`。
2. `content_hash` 为清除纯排版噪声后的正文 SHA-256，但原始正文不得丢失。
3. 同一 JD 多次抓取时保留首次和末次抓取时间；正文未变化不得重复计入统计。
4. 每个标准实体必须能通过 `source_ids` 回到原文；每条关系必须能通过 `evidence_ids` 回到原文。
5. `published_at` 是资料的业务发布时间，`crawled_at` 是系统采集时间。二者不能互相代替，也不能使用 Excel 创建时间或导出批次时间冒充。

## 3. A 层：2.1 逐文档抽取结果

推荐目录：`data/processed/extracted/YYYY/MM/*.jsonl`。

### 3.1 顶层字段

| 字段 | 类型 | JD 必须 | 说明 |
|---|---|---:|---|
| `schema_version` | string | 是 | 固定为 `1.0.0`。 |
| `document_type` | enum | 是 | `job_description`、`industry_report`、`technical_article`；只有 `job_description` 计入 JD 数。 |
| `jd_id` | string | 是 | 稳定原始记录 ID；非 JD 文档仍使用同一字段承载 document ID。 |
| `source_platform` | string | 是 | 平台/网站/报告发布机构，不使用模糊值“网络”。 |
| `external_id` | string/null | 建议 | 来源平台原始 ID。 |
| `url` | string | 是 | 原始可核验 URL；确无 URL 的离线报告写内部存档 URI。 |
| `published_at` | datetime/null | **是** | 真实发布日期。取不到时显式 `null`，不得猜测；该记录不能参与 3.1 时序统计。 |
| `crawled_at` | datetime | 是 | 本次采集时间。 |
| `first_seen_at` / `last_seen_at` | datetime | 建议 | 识别重复抓取、下架和时滞。 |
| `content_hash` | string | 是 | `sha256:<hex>`。 |
| `language` | string | 是 | 如 `zh-CN`、`en-US`。 |
| `job_title_raw` | string/null | JD 是 | 来源原始岗位名，不做同义词覆盖。 |
| `company_raw` | string/null | 建议 | 来源原始公司名。 |
| `industry_raw` | string/null | 建议 | 来源原始行业。 |
| `city_raw` | string/null | 建议 | 来源原始城市/地区。 |
| `job_level_raw` | string/null | 建议 | 如实习、初级、中级、高级、专家。 |
| `responsibilities` | string/null | 至少一个 | 与 `requirements` 至少一个非空。 |
| `requirements` | string/null | 至少一个 | 保留完整要求文本。 |
| `raw_text` | string | 是 | 可审计的完整正文。 |
| `entities` | array | 是 | 2.1 抽取实体，格式见下。 |
| `relations` | array | 是 | 2.1 抽取关系，格式见下；未抽到时为 `[]`。 |
| `events` | array | 建议 | 事件抽取结果，格式见下。 |
| `extraction_meta` | object | 是 | 模型、Prompt、抽取时间和质量状态。 |

### 3.2 实体、关系与证据

实体 `type` 只能取：`position`、`skill`、`certificate`、`industry`、`tech_stack`、`education`、`company`、`project`。

```json
{
  "mention_id": "m-0003",
  "type": "skill",
  "name": "K8s",
  "aliases": ["Kubernetes"],
  "attributes": {"category": "云与容器"},
  "confidence": 0.96,
  "evidence": {
    "quote": "熟悉 K8s/Docker，有生产环境经验",
    "section": "requirements",
    "start": 128,
    "end": 151
  }
}
```

关系 `type` 只能取：`requires`、`prefers`、`prerequisite`、`same_as`、`related_to`、`belongs_to`、`evolved_from`、`applies_to`。`head_mention_id` 和 `tail_mention_id` 必须引用当前记录的实体；岗位对技能的 `requires` / `prefers` 对 3.3 尤其重要。

```json
{
  "relation_id": "r-0002",
  "head_mention_id": "m-0001",
  "tail_mention_id": "m-0003",
  "type": "requires",
  "properties": {
    "proficiency": "熟悉",
    "min_years": 2
  },
  "confidence": 0.92,
  "evidence": {
    "quote": "熟悉 K8s/Docker，有 2 年生产环境经验",
    "section": "requirements",
    "start": 128,
    "end": 158
  }
}
```

`proficiency` 统一为 `了解 / 熟悉 / 精通 / 专家`；无法判断时省略，不能根据关键词数量臆测。`min_years` 为非负数字。每个实体/关系必须有原文 `quote`；字符偏移取不到时可以省略 `start/end`，但不能省略 `quote` 和 `section`。

事件格式用于保留发布时间或需求变化等信息：

```json
{
  "event_id": "event-0001",
  "type": "job_posted",
  "event_time": "2025-04-16T09:30:00+08:00",
  "participants": ["m-0001", "m-0006"],
  "confidence": 0.98,
  "evidence": {"quote": "发布于 2025-04-16", "section": "metadata"}
}
```

`extraction_meta` 至少包含：

```json
{
  "model": "spark-or-other-model",
  "model_version": "fixed-version-or-date",
  "prompt_version": "jd-extract-v1.2",
  "extracted_at": "2025-04-17T02:20:00+08:00",
  "overall_confidence": 0.91,
  "needs_human_review": false,
  "quality_issues": []
}
```

### 3.3 Excel 交付的固定列

现有 `extracted_result.xlsx` 的业务列可以保留。为冻结接口，至少必须保证以下列存在：

```text
schema_version, document_type, jd_id, source_platform, external_id, url,
published_at, crawled_at, first_seen_at, last_seen_at, content_hash, language,
job_title_raw, company_raw, industry_raw, city_raw, job_level_raw,
responsibilities, requirements, raw_text,
extracted_entities_json, extracted_relations_json, extracted_events_json,
extraction_model, model_version, prompt_version, extracted_at,
overall_confidence, needs_human_review, quality_issues_json
```

其中 `*_json` 列必须能被标准 JSON 解析；`published_at` 为空的历史记录允许交付，但必须在批次质量报告中统计，不能统一填成导出当天。

为避免对现有表反复改列名，当前列允许通过一次固定适配映射到规范字段：

| 现有 Excel 列 | 规范字段/处理方式 |
|---|---|
| `job_title`、`company`、`industry`、`city`、`job_level` | 分别映射到对应的 `*_raw` 字段，无需在原表重复建列。 |
| `responsibilities` + `requirements` | 保持两列，同时由转换程序拼接生成 `raw_text`；若有原始完整正文，应优先使用原文。 |
| `extracted_entities_json` | 作为实体输入，但转换前必须校验其中的类型、置信度和原文证据。 |
| `raw_skills`、`tech_stack`、`certificates`、各 `skill_*` 列 | 作为兼容辅助列，不得替代规范的实体/关系 JSON。 |
| `quality_score`、`needs_human_review` | 保留并映射到 `extraction_meta`。 |

现有表需要一次性补齐或由转换程序生成的关键项是：`document_type`、`published_at`、`crawled_at`、`content_hash`、`extracted_relations_json`、模型/Prompt 版本。除契约主版本升级外，后续不再要求数据同学改变这批固定列。`schema_version`、`language`、`source_id` 等可由稳定转换规则生成，不要求人工逐行填写。

## 4. B 层：2.2 逐 JD 标准化结果

推荐目录：`data/processed/normalized/YYYY/MM/*.jsonl`。一条标准化记录必须对应且只对应一条 A 层记录，保留 `jd_id/source_id`，不能只输出全局实体表。

```json
{
  "schema_version": "1.0.0",
  "jd_id": "zhaopin:CCL1439887430J40933789215",
  "source_id": "source:zhaopin:CCL1439887430J40933789215",
  "document_type": "job_description",
  "published_at": "2025-04-16T09:30:00+08:00",
  "crawled_at": "2025-04-17T02:15:00+08:00",
  "content_hash": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "job": {
    "raw_name": "Python后端研发",
    "canonical_id": "job:backend-engineer",
    "canonical_name": "后端开发工程师",
    "aliases": ["Python后端研发"],
    "level": "mid",
    "description": "负责后端服务、接口与数据能力建设",
    "min_experience_years": 2,
    "preferred_experience_years": 4,
    "education_required": "本科及以上",
    "alignment_confidence": 0.93,
    "is_new_candidate": false
  },
  "skills": [
    {
      "raw_name": "K8s",
      "canonical_id": "skill:kubernetes",
      "canonical_name": "Kubernetes",
      "aliases": ["K8s"],
      "category": "云与容器",
      "requirement_type": "required",
      "proficiency": "熟悉",
      "min_years": 2,
      "confidence": 0.92,
      "evidence": ["熟悉 K8s/Docker，有 2 年生产环境经验"]
    }
  ],
  "tech_stacks": [{"canonical_id": "stack:cloud-native", "name": "云原生"}],
  "industries": [{"canonical_id": "industry:internet", "name": "互联网"}],
  "certificates": [],
  "education": [{"canonical_id": "education:bachelor", "name": "本科及以上"}],
  "company": {"canonical_id": "company:example", "name": "示例公司"},
  "alignment_meta": {
    "ontology_version": "job-ontology-1.0.0",
    "dictionary_version": "synonyms-1.0.0",
    "method": "hybrid",
    "needs_human_review": false,
    "conflicts": []
  }
}
```

### 4.1 2.2 的强制标准化规则

- `level` 枚举固定为 `intern / junior / mid / senior / expert / unknown`。
- `requirement_type` 固定为 `required / preferred / mentioned`。只有前两类进入岗位技能要求；`mentioned` 仅作语境信息。
- 技能必须标准化到“框架/工具/方法”粒度，如 `FastAPI`、`Kubernetes`、`RAG`；不能只保留宽泛的“计算机能力”。
- 同一 JD 内同一 `canonical_id` 只出现一次；多段证据合并到 `evidence`，`required` 优先于 `preferred`。
- 2.2 不得丢弃 `raw_name`、原文证据或 `source_id`。
- 新词无法可靠对齐时，使用候选 ID 并设置 `is_new_candidate=true`、`needs_human_review=true`，不能强行并入相似实体。
- 冲突融合必须记录 `ontology_version`、`dictionary_version`、方法和冲突说明，保证结果可复现。

## 5. C 层：2.2 / 聚合管线到 2.3 的图谱批次

传输接口为 `POST /api/graph/import`，顶层结构固定如下：

```json
{
  "batch_id": "task-2.2-zhaopin-20250417-01",
  "producer": "task-2.2",
  "nodes": [],
  "relationships": []
}
```

完整可运行样例见 [`data/demo/graph_import_sample.json`](../demo/graph_import_sample.json) 和 [`data/demo/job_evolution_sample.json`](../demo/job_evolution_sample.json)。顶层、节点和关系不允许增加未声明字段；扩展业务属性统一放入 `properties`。

### 5.1 节点最低属性

| 节点 | 必须提供 | 强烈建议提供 |
|---|---|---|
| `Job` | `id/type/name/confidence/source_ids` | `aliases`；`properties.description/level/min_experience_years/preferred_experience_years/education_required` |
| `Skill` | `id/type/name/confidence/source_ids` | `aliases`；`properties.category/definition` |
| `TechStack`、`Industry`、`Certificate`、`Education` | `id/type/name/confidence` | `aliases/source_ids` |
| `Company` | `id/type/name/confidence` | `aliases/source_ids` |
| `Source` | `id/type/name/confidence` | `properties.document_type/source_platform/url/content_hash/published_at/crawled_at/jd_id` |

`Source.properties.published_at` 为 `null` 时应省略该属性，但仍保留 `crawled_at`；这样的 Source 不能参与时序聚合。

### 5.2 关系方向与用途

| 关系 | 固定方向 | 下游用途 |
|---|---|---|
| `REQUIRES_SKILL` | Job -> Skill | 3.1 趋势、3.3 必备技能、2.4 能力变更 |
| `BONUS_SKILL` | Job -> Skill | 3.1 趋势、3.3 加分技能、2.4 能力变更 |
| `BELONGS_TO_STACK` | Skill -> TechStack | 2.3 筛选、3.3 项目/技术栈匹配 |
| `APPLIES_TO_INDUSTRY` | Job -> Industry | 2.3 筛选、3.3 行业匹配 |
| `REQUIRES_CERTIFICATE` | Job -> Certificate | 3.3 差距分析 |
| `REQUIRES_EDUCATION` | Job -> Education | 3.3 学历匹配 |
| `PUBLISHED_BY` | Job -> Company | 2.4 跨企业支持度与溯源 |
| `DERIVED_FROM` | 任意实体 -> Source | 全模块证据回链 |
| `PREREQUISITE_OF` | Skill -> Skill | 学习路径 |
| `EVOLVES_TO` | 旧版本 -> 新版本 | 2.4 语义版本变更；普通改名不得使用 |

### 5.3 周期岗位-技能快照

3.1 和 2.4 需要周期化关系。一个数据集必须统一选择 `quarterly` 或 `monthly` 粒度，当前推荐使用季度；不得在一次分析中混用月度与季度快照。调用 3.1 API 时必须传入与数据一致的粒度。

统计前先排除 `published_at=null`、非 JD 文档、重复 JD 和未通过质量审核的记录。对每个 `(job_id, period_key)`：

```text
job_jd_count   = 该周期该岗位的去重有效 JD 数
skill_jd_count = 上述 JD 中 required 或 preferred 包含该技能的去重 JD 数
demand_ratio   = skill_jd_count / job_jd_count
required_ratio = required_jd_count / skill_jd_count（分母为 0 时为 0）
```

同一 `(job_id, skill_id, period_key)` **只能生成一条**岗位-技能关系，避免必备/加分关系重复计数：

- `required_ratio >= 0.5` -> `REQUIRES_SKILL`；
- 否则 -> `BONUS_SKILL`；
- 同时在 `properties` 保留 `required_jd_count`、`preferred_jd_count` 和 `required_ratio`。

周期关系必须包含：

```json
{
  "id": "job:backend-engineer|REQUIRES_SKILL|skill:kubernetes|2025Q2",
  "type": "REQUIRES_SKILL",
  "from_id": "job:backend-engineer",
  "to_id": "skill:kubernetes",
  "properties": {
    "period_key": "2025Q2",
    "period_start": "2025-04-01T00:00:00+08:00",
    "period_end": "2025-07-01T00:00:00+08:00",
    "skill_jd_count": 56,
    "job_jd_count": 120,
    "demand_ratio": 0.4667,
    "required_jd_count": 34,
    "preferred_jd_count": 22,
    "required_ratio": 0.6071,
    "importance": 0.5654,
    "importance_method": "0.7*demand_ratio+0.3*required_ratio",
    "proficiency": "熟悉",
    "years": 2
  },
  "confidence": 0.93,
  "evidence_ids": ["source:jd-001", "source:jd-002"],
  "observed_at": "2025-07-02T00:00:00+08:00",
  "valid_from": "2025-04-01T00:00:00+08:00",
  "valid_to": "2025-07-01T00:00:00+08:00"
}
```

默认 `importance = 0.7 * demand_ratio + 0.3 * required_ratio`。如采用人工标注或模型权重，必须在 `importance_method` 中写明方法和版本，且同一分析区间不能混用不同算法。`proficiency` 取该周期有效证据中的众数，`years` 取最低年限的中位数；没有足够证据时省略，不能填 0 冒充无要求。

晚到数据必须重新计算并覆盖整个周期快照，不能把局部计数累加到旧结果。图谱中若已经采用周期关系，不得再为同一岗位-技能并行维护一条无周期静态关系；3.3 默认读取最新有效周期快照。

## 6. 四个下游的最低数据要求

关键字段的消费关系如下，2.1/2.2 不得因为本模块暂时未实现就删除未来消费者所需字段：

| 字段/结构 | 2.3 | 2.4 | 3.1 | 3.3 |
|---|:---:|:---:|:---:|:---:|
| 稳定 `jd_id/source_id`、URL、正文哈希 | 溯源 | 去重、聚类证据 | 去重计数 | 报告解释 |
| `published_at/crawled_at` | 时态存储 | 新兴性、变化时间 | 周期归属 | 读取最新有效画像 |
| 原始岗位名、职责、要求 | Job 描述 | 新岗位聚类与自动定义 | 标签解释 | 岗位说明 |
| 标准 `job_id/skill_id/aliases` | 图谱主键 | novelty 与同义词消歧 | 跨期对齐 | 技能精确匹配 |
| `required/preferred`、熟练度、年限 | 关系属性 | 能力变化 | 权重与趋势 | 必备/加分、能力差距 |
| 行业、技术栈、学历、证书、公司 | 多维检索 | 场景定义、跨企业支持度 | 分层分析 | 多维匹配 |
| 原文证据、置信度、模型/本体版本 | 质量与审计 | 变更解释、人工审核 | 质量警告 | 可解释报告 |

| 下游 | 最低可运行数据 | 达到任务书目标的数据条件 | 缺失时的后果 |
|---|---|---|---|
| 2.3 图谱 | C 层标准节点/关系；稳定 ID；实体来源 | 覆盖不少于 30 个标准岗位，技能达到框架/工具/方法粒度 | 只能展示零散静态节点，无法可靠检索和更新。 |
| 2.4 新岗位发现 | B 层逐 JD 记录；岗位原名、职责、标准技能组合、公司、行业、`published_at`、source | 候选至少 5 条去重 JD，建议来自至少 2 家公司和 2 个来源；至少两个相邻周期；保留相似岗位与全部证据 | 只有聚合图无法做岗位聚类和 novelty 解释；没有时间无法判断“新兴”。 |
| 2.4 既有岗位更新 | C 层至少两个同粒度周期快照；B 层证据 | 输出新增/删除/增强/减弱技能、变更前后值、变更时间、算法版本、证据 ID 和审核状态 | 只能覆盖当前画像，无法生成完整变更日志。 |
| 3.1 演化 | C 层周期关系；真实发布时间；样本计数 | 至少 4 个连续周期；预测至少 6 个连续周期；推荐每岗位每期不少于 20 条去重 JD | 少于 4 期仅能做快照对比；少于 6 期不展示预测。 |
| 3.3 匹配 | C 层最新 Job 画像、必备/加分技能、标准技能 ID、权重 | 同时提供技能熟练度/年限、岗位经验区间、学历、行业、技术栈、证书和别名 | 缺失维度会使用中性分或降级逻辑，匹配准确率和解释性下降。 |

## 7. 2.4 输出的变更日志契约

2.4 尚未完成时也必须按以下格式设计，避免后续再次要求 2.1/2.2 改数据。每个变更项至少包含：

```json
{
  "change_id": "change:job:backend-engineer:2025Q1:2025Q2:skill:kubernetes",
  "job_id": "job:backend-engineer",
  "from_period": "2025Q1",
  "to_period": "2025Q2",
  "change_type": "increased",
  "entity_id": "skill:kubernetes",
  "before": {"demand_ratio": 0.31, "importance": 0.39},
  "after": {"demand_ratio": 0.47, "importance": 0.57},
  "delta": 0.16,
  "algorithm": "adjacent-period-diff-v1",
  "evidence_ids": ["source:jd-001", "source:jd-002"],
  "review_status": "pending",
  "reviewed_by": null,
  "reviewed_at": null,
  "created_at": "2025-07-03T10:00:00+08:00"
}
```

`change_type` 固定为 `added / removed / increased / decreased / renamed / merged / split`。自动发现的新岗位在人工确认前只能标为候选，不能直接替换正式本体。

## 8. 批次质量报告

2.1 和 2.2 每批数据必须同时交付一个质量报告，至少包含：

```json
{
  "schema_version": "1.0.0",
  "batch_id": "task-2.2-zhaopin-20250417-01",
  "total_records": 500,
  "valid_records": 472,
  "duplicate_records": 11,
  "missing_published_at": 17,
  "missing_job_title": 0,
  "missing_evidence": 8,
  "low_confidence_entities": 21,
  "human_review_required": 26,
  "rejected_records": 28,
  "ontology_version": "job-ontology-1.0.0",
  "dictionary_version": "synonyms-1.0.0",
  "model_version": "fixed-version-or-date",
  "prompt_version": "jd-extract-v1.2",
  "generated_at": "2025-04-17T04:00:00+08:00"
}
```

批次验收最低门槛：

- JSON/JSONL 解析成功率 100%，ID 非空且批内唯一；
- `crawled_at/content_hash/source_platform/url` 完整率 100%；
- JD 的 `job_title_raw` 和正文完整率 100%；
- 所有标准实体和关系可回链到 `source_id/evidence_id`；
- 参与时序分析的记录 `published_at` 完整率 100%；缺失时间的记录必须被排除并单独统计；
- `confidence` 和比例均在 `[0,1]`，数量为非负整数；
- 周期关系满足 `skill_jd_count <= job_jd_count`，且比例误差不超过 `0.001`；
- 人工抽检指标遵循任务书：2.1 JD 解析准确率不低于 90%，2.2 实体对齐精确率和同义词覆盖率不低于 90%。

## 9. 版本与变更流程

1. 当前冻结版本为 `1.0.0`，所有新批次必须带 `schema_version`。
2. 新增可选字段属于次版本升级；删除字段、改名、改变类型/枚举/语义属于主版本升级。
3. 上游修改契约前必须同时更新：本文、示例数据、转换脚本和批次质量报告版本。
4. 下游不得临时要求 2.1 重抽已有字段；新增需求应优先由 A/B 层已有原文和证据通过适配或重算获得。
5. 原始 A 层数据永久只追加不覆盖；B/C 层允许按相同稳定 ID 幂等重算。

## 10. 最终交付清单

2.1 每批交付：

- `extracted_records.jsonl` 或符合固定列的 `.xlsx`；
- `quality_report.json`；
- 本批使用的模型、Prompt 版本和字段说明。

2.2 每批交付：

- `normalized_records.jsonl`；
- 可直接调用 `/api/graph/import` 的 `graph_import_batch.json`；
- `quality_report.json`；
- 本体版本、同义词表版本、旧 ID 到新 ID 的映射/合并记录。

交接前由数据提供者和 2.3/2.4/3.1/3.3 负责人共同确认一次本清单。通过后冻结版本，后续下游只能提出兼容性扩展，不能口头改变既有字段含义。
