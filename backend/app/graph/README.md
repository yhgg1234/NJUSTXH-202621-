# 子任务 2.3：岗位能力知识图谱

> 2.1/2.2 上游交付的规范性字段、逐 JD 标准化结构、周期聚合口径和批次验收规则统一见
> [`data/schema/README.md`](../../../data/schema/README.md)。如本文与中央契约冲突，以中央契约为准。

本模块负责将 2.2 输出的标准化实体和关系幂等写入 Neo4j，并向 2.4、3.1、3.3 和前端提供统一查询接口。模块不负责实体抽取、同义词归一或新岗位判定。

## 目录职责

子任务 2.3 横跨系统的多个层次，因此相关文件按职责放置，而不是全部堆放在一个目录：

| 目录或文件 | 职责 |
|---|---|
| `backend/app/graph/` | 图谱领域模型、Neo4j 仓储和业务服务 |
| `backend/app/routers/graph.py` | FastAPI 接口适配层 |
| `backend/tests/test_graph*.py` | 单元测试和真实 Neo4j 集成测试 |
| `frontend/src/components/KnowledgeGraph.vue` | 图谱交互式可视化 |
| `data/demo/graph_import_sample.json` | 2.2→2.3 对接样例和演示数据 |

这种分层使后端、前端和数据同学可以在各自目录内工作；模块入口集中在本 README，避免依赖物理目录集中来获得可发现性。

## 快速运行

运行环境需要 Python 3.10 及以上、Neo4j 5.x。

```bash
docker compose up -d neo4j
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

首次运行后初始化约束和索引：

```bash
curl -X POST http://localhost:8000/api/graph/schema
```

导入演示数据：

```bash
curl -X POST http://localhost:8000/api/graph/import \
  -H "Content-Type: application/json" \
  --data-binary @../data/demo/graph_import_sample.json
```

Swagger 文档位于 `http://localhost:8000/docs`，Neo4j Browser 位于 `http://localhost:7474`。

启动前端后访问 `http://localhost:5173` 可使用岗位能力图谱页面。页面支持岗位 ID、技术栈、岗位级别和行业筛选，以及图谱缩放、拖拽、邻接高亮和节点详情查看。

## 图谱 Schema

节点统一带有 `GraphEntity` 标签，并拥有业务类型标签。`id` 是跨批次稳定的业务主键，`name` 是展示名称。

| 节点类型 | 含义 | 推荐 ID 示例 |
|---|---|---|
| `Job` | 岗位 | `job:ai-agent-engineer` |
| `Skill` | 技能点 | `skill:python` |
| `TechStack` | 技术栈 | `stack:llm-application` |
| `Industry` | 行业 | `industry:artificial-intelligence` |
| `Certificate` | 证书 | `certificate:cka` |
| `Education` | 学历要求 | `education:bachelor` |
| `Project` | 项目或项目经验 | `project:rag-assistant` |
| `Company` | 企业 | `company:example` |
| `Source` | JD、报告等证据源 | `source:jd-001` |

支持的关系如下：

| 关系类型 | 推荐方向 |
|---|---|
| `REQUIRES_SKILL` / `BONUS_SKILL` | Job → Skill |
| `BELONGS_TO_STACK` | Skill → TechStack |
| `APPLIES_TO_INDUSTRY` | Job → Industry |
| `REQUIRES_CERTIFICATE` | Job → Certificate |
| `REQUIRES_EDUCATION` | Job → Education |
| `RELATED_PROJECT` | Job 或 Skill → Project |
| `PUBLISHED_BY` | Job → Company |
| `PREREQUISITE_OF` | Skill → Skill |
| `DERIVED_FROM` | 任意实体 → Source |
| `EVOLVES_TO` | 旧实体版本 → 新实体版本 |

## 与 2.2 的输入契约

2.2 应调用 `POST /api/graph/import`，完整示例见 `data/demo/graph_import_sample.json`。

关键规则：

1. `batch_id` 必须唯一且可追溯，建议格式为 `来源-日期-批次号`。
2. 节点 `id` 必须使用标准化实体 ID，同一个概念跨来源不得更换 ID；原始称谓放入 `aliases`。
3. 关系 `id` 必须稳定且唯一。时序关系必须包含观察周期，例如 `岗位ID|关系类型|技能ID|2026Q2`。
4. `confidence` 范围为 0—1；节点来源放在 `source_ids`，关系证据放在 `evidence_ids`。
5. `properties` 仅接受 Neo4j 原生标量或同类型数组，不接受嵌套对象；核心字段名为保留字段，不能在 `properties` 中覆盖。
6. 同一批次可同时提交新节点和它们之间的关系。引用批次外节点时，该节点必须已存在，否则接口返回 422 和缺失 ID 列表。
7. 重复提交相同节点/关系 ID 会执行更新而非创建副本，因此允许安全重试。

### 给 2.1 数据抽取同学：JD 原始记录最低字段

2.1 输出的**每一条 JD**都应保留以下字段；2.3 负责标准化和入图，3.1 依赖其中的业务时间生成月度或季度快照。

| 字段 | 是否必填 | 说明 |
|---|---:|---|
| `jd_id` | 是 | 来源内稳定的 JD 标识；同一条招聘不能因重复抓取产生新 ID。 |
| `source_platform`、`url` | 是 | 来源平台和原始链接，用于去重、回溯和人工核验。 |
| `published_at` | **是（未知时显式为 `null`）** | 招聘实际发布日期，ISO-8601 且带时区，例如 `2025-04-16T09:30:00+08:00`。这是 3.1 的归期依据。 |
| `crawled_at` | 是 | 系统采集时间，ISO-8601 且带时区；仅用于审计、迟到数据重算和时效性检查。 |
| `job_title`、`industry`、`city` | 是 | 用于岗位归一、行业/地域分层和后续统计；原始值不得被覆盖。 |
| `requirements` / `responsibilities` | 至少其一 | 可追溯的 JD 正文或对应片段。 |
| `raw_skills`、`tech_stack` | 推荐 | 原始抽取结果；2.2/2.3 再映射为标准 `Skill` / `TechStack`。 |
| `extracted_skills` 与证据定位 | 推荐 | 标准技能及其文本证据；至少应能反查到原 JD。 |

禁止把 Excel 文件创建时间、批次导出时间或网页抓取时间写成 `published_at`。无法取得真实发布日期的记录可以进入 2.3 静态图谱，但**不得参与 3.1 的按期统计**；应在质量报告中单独计数。

```json
{
  "jd_id": "zhaopin:CCL1439887430J40933789215",
  "source_platform": "智联招聘",
  "url": "https://example.invalid/job/123",
  "published_at": "2025-04-16T09:30:00+08:00",
  "crawled_at": "2025-04-17T02:15:00+08:00",
  "job_title": "后端开发工程师",
  "industry": "互联网/软件",
  "city": "南京",
  "requirements": "熟悉 Python、Docker 与关系型数据库……",
  "raw_skills": ["Python", "Docker"],
  "extracted_skills": ["skill:python", "skill:docker"]
}
```

### 3.1 周期化岗位—技能关系契约

3.1 不建立独立的年度图数据库，而是在同一图谱中保存多个岗位—技能关系版本。对于
`REQUIRES_SKILL` 与 `BONUS_SKILL`，2.1/聚合管线必须在 `properties` 中提供：

| 字段 | 含义 | 要求 |
|---|---|---|
| `period_key` | 时间切片，如 `2024Q1` 或 `2024-06` | 必填 |
| `period_start` | 切片起点 | 必填，建议与关系 `valid_from` 一致 |
| `period_end` | 切片终点 | 推荐 |
| `skill_jd_count` | 此周期内要求该技能的去重 JD 数 | 必填 |
| `job_jd_count` | 此周期内该岗位的去重有效 JD 总数 | 必填 |
| `demand_ratio` | `skill_jd_count / job_jd_count` | 必填，范围 0—1 |
| `importance` | 岗位技能权重 | 推荐，范围 0—1 |

关系的 `evidence_ids` 必须回链到 JD/报告等 `Source` 证据；Source 应保存资料的
`published_at`（业务发布时间）和 `crawled_at`（系统采集时间）。业务时间用于归期，
采集时间不能代替业务时间。

同一周期的统计应以“完整重算快照”方式写入：晚到数据需要重新计算该周期的完整统计后
覆盖同一关系 ID，不能把局部计数作为增量直接覆盖。

`POST /api/graph/import` 将请求中每个 `(job_id, period_key)` 视为完整岗位—技能快照：新关系成功写入后，会删除该岗位该周期中本次未再提供的旧 `REQUIRES_SKILL`/`BONUS_SKILL` 关系。因此同一岗位同一周期不能拆成多个独立请求上传，否则后一个请求会替换前一个请求的技能集合；不同岗位或不同周期可以放在同一批次中。

接口会对带周期字段的 `REQUIRES_SKILL` / `BONUS_SKILL` 关系执行以下校验；未通过会返回 422，而不是写入不可比较的历史数据：

- `period_key` 只能是 `YYYY-MM` 或 `YYYYQ1` 到 `YYYYQ4`，且 `period_start` 必须是该切片起点；
- 必须同时给出 `period_key`、`period_start`、`skill_jd_count`、`job_jd_count`、`demand_ratio` 和至少一个 `evidence_id`；
- `0 <= skill_jd_count <= job_jd_count`，且 `demand_ratio` 与 `skill_jd_count / job_jd_count` 的误差不超过 `0.001`；
- 对尚未补齐历史数据的静态图谱，可完全不带上述周期字段导入；这类关系不会进入 3.1 统计。

## 与 2.4 的时序和溯源约定

2.4 可直接使用以下字段进行新岗位发现、能力变化识别和变更解释：

| 字段 | 用途 |
|---|---|
| `observed_at` | 数据被观测或采集的时间 |
| `valid_from` / `valid_to` | 结论的业务有效期 |
| `confidence` | 抽取、融合或判定置信度 |
| `source_ids` / `evidence_ids` | 回溯原始 JD、报告或人工证据 |
| `last_batch_id` | 定位最后一次写入批次，由 2.3 自动记录 |
| 关系 `frequency` | 某周期内技能出现频次，放在 `properties` 中 |

能力发生变化时不要覆盖历史关系：使用包含周期的关系 ID 创建新关系，并为旧关系填写 `valid_to`。岗位定义发生版本变化时，可创建新岗位版本并用 `EVOLVES_TO` 连接；仅名称修正等非语义变化可原 ID 更新。

## REST API

| 方法与路径 | 作用 |
|---|---|
| `POST /api/graph/schema` | 创建唯一约束与查询索引 |
| `POST /api/graph/import` | 2.2 批量幂等导入 |
| `PUT /api/graph/nodes/{id}` | 人工新增或修正单个节点 |
| `PUT /api/graph/relationships/{id}` | 人工新增或修正单条关系 |
| `GET /api/graph/subgraph` | 返回前端可视化所需 `nodes` 与 `links` |
| `GET /api/graph/filter-options` | 返回岗位、技术栈、级别、行业和月份的可用筛选项 |
| `GET /api/graph/stats` | 返回节点、关系及类型统计 |

`subgraph` 支持 `job_id`、`tech_stack`、`level`、`industry`、`period`、`as_of`、
`include_history` 和 `limit` 参数。默认只返回岗位技能关系的最新版本；传入 `period`
返回指定切片，传入 `as_of` 返回该日期有效的关系，`include_history=true` 才返回全部历史。
例如：

```text
GET /api/graph/subgraph?tech_stack=大模型应用开发&level=中级&limit=50
GET /api/graph/subgraph?job_id=job:ai-agent-engineer&period=2024Q2
```

## 测试

```bash
cd backend
pytest -q
```

单元测试通过依赖注入使用内存仓储，不要求本机启动 Neo4j。正式联调时应另外运行一次演示数据导入，并在 Neo4j Browser 中检查约束、节点、关系和溯源字段。

真实 Neo4j 集成测试默认跳过，可按需启用：

```bash
RUN_NEO4J_INTEGRATION=1 pytest -q tests/test_graph_neo4j_integration.py
```
