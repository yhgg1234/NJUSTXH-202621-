# 子任务 2.3：岗位能力知识图谱

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
3. 关系 `id` 必须稳定且唯一。时序关系建议包含观察周期，例如 `岗位ID|关系类型|技能ID|2026-06`。
4. `confidence` 范围为 0—1；节点来源放在 `source_ids`，关系证据放在 `evidence_ids`。
5. `properties` 仅接受 Neo4j 原生标量或同类型数组，不接受嵌套对象；核心字段名为保留字段，不能在 `properties` 中覆盖。
6. 同一批次可同时提交新节点和它们之间的关系。引用批次外节点时，该节点必须已存在，否则接口返回 422 和缺失 ID 列表。
7. 重复提交相同节点/关系 ID 会执行更新而非创建副本，因此允许安全重试。

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
| `GET /api/graph/stats` | 返回节点、关系及类型统计 |

`subgraph` 支持 `job_id`、`tech_stack`、`level`、`industry` 和 `limit` 参数。例如：

```text
GET /api/graph/subgraph?tech_stack=大模型应用开发&level=中级&limit=50
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
