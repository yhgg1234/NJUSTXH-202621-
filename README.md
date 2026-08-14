# XH-202621 多源异构数据驱动岗位和能力图谱构建与动态演化分析研究

## 项目简介

本项目面向新一代信息技术领域（人工智能、大数据、智能系统、物联网等），设计并开发一套"数据驱动 + 大模型 + 知识图谱"的岗位能力动态演化与分析系统。

核心功能包括：
- 多源异构数据采集与清洗
- 新岗位发现与定义
- 既有岗位能力动态更新
- 岗位能力全景图谱构建（Neo4j）
- 简历解析（PDF/Word）与人岗匹配诊断
- 动态演化分析与趋势预测

知识图谱模块的 Schema、API 和跨子任务数据契约见
[`backend/app/graph/README.md`](backend/app/graph/README.md)。

## 模块文档索引

为避免多人并行开发时文档分散或互相覆盖，根目录 README 只保留项目总览和导航；各子任务的实现细节、接口契约和联调要求写在对应模块 README 中。

| 模块/资料 | 文档位置 | 说明 |
|------|------|------|
| 项目任务书 | [`docs/`](docs/) | 任务书、分工表、项目相关资料 |
| 2.1/2.2 上游数据交付契约 | [`data/schema/README.md`](data/schema/README.md) | 供 2.3、2.4、3.1、3.3 使用的字段、时间、ID、证据、聚合与验收标准 |
| 2.3 岗位能力知识图谱 | [`backend/app/graph/README.md`](backend/app/graph/README.md) | 图谱 Schema、节点/关系格式、图谱 API、跨子任务数据契约 |
| 2.4 新岗位发现与能力动态更新 | [`backend/app/discovery/README.md`](backend/app/discovery/README.md) | 2.2 JSON/JSONL 接入、技能社区与 novelty 算法、人工审核、变更日志及 2.3 写回 |
| 3.2 简历解析 | 待补充 | 建议后续补充标准化简历画像输出格式，供 3.3 人岗匹配消费 |
| 3.3 人岗匹配诊断与差距分析 | [`backend/app/matching/README.md`](backend/app/matching/README.md) | 匹配评分、差距分析、Spark Lite 配置、对 2.3/3.2 的数据要求 |
| 数据目录 | [`data/README.md`](data/README.md) | 原始数据、处理后数据、示例数据和 schema 的存放约定 |
| 数据处理管线 | [`data_pipeline/README.md`](data_pipeline/README.md) | 数据处理脚本和管线说明 |
| 工具脚本 | [`scripts/README.md`](scripts/README.md) | 项目辅助脚本说明 |

当前联调状态：2.4 已支持直接读取 2.2 的 `normalized_records.json/jsonl`，对照 2.3 图谱进行新岗位发现和既有岗位能力更新，并在人工审核后写回 2.3；详见[子任务 2.4 文档](backend/app/discovery/README.md)。3.1 已支持将 `data/demo/task_2_2_1000/graph_import_batch.json` 实际导入 Neo4j，读取由 `published_at` 生成的月度快照，并在分析层进一步汇总季度演化结果；详见[子任务 3.1 文档](backend/app/jobs/README.md)。3.3 前后端展示链路可基于 demo 数据运行，完整真实简历匹配闭环仍需 3.2 简历画像的实际交接。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | Python + FastAPI |
| 前端框架 | Vue 3 + Vite + Element Plus |
| 图数据库 | Neo4j |
| 关系数据库 | MySQL |
| 文档数据库 | MongoDB |
| 大模型 | 讯飞星火 / LLM + RAG |
| 容器化 | Docker + Docker Compose |

## 项目结构

```
├── backend/
│   ├── app/
│   │   ├── main.py              # 应用入口（52个API端点已注册）
│   │   ├── config.py            # 配置管理
│   │   ├── routers/             # API 路由（8个模块）
│   │   │   ├── graph.py         # ✅ 知识图谱（已实现）
│   │   │   ├── data_collection.py  # 数据采集
│   │   │   ├── data_cleaning.py    # 数据清洗
│   │   │   ├── extraction.py       # 信息抽取
│   │   │   ├── jobs.py             # 岗位管理
│   │   │   ├── resume.py           # 简历解析
│   │   │   ├── matching.py         # 人岗匹配
│   │   │   └── dashboard.py        # 仪表盘
│   │   ├── graph/               # 图谱领域模型+服务（已实现）
│   │   ├── discovery/           # 2.4 新岗位发现、审核与能力变更日志
│   │   ├── data_collection/     # 各模块 Pydantic 数据模型
│   │   ├── data_cleaning/
│   │   ├── extraction/
│   │   ├── jobs/
│   │   ├── resume/
│   │   ├── matching/
│   │   └── dashboard/
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── router/              # Vue Router 路由配置
│       ├── api/                 # 7个模块的 axios 调用层
│       ├── pages/               # 9个功能页面
│       │   ├── Dashboard.vue       # 仪表盘
│       │   ├── DataCollection.vue  # 数据采集
│       │   ├── DataCleaning.vue    # 数据清洗
│       │   ├── Extraction.vue      # 信息抽取
│       │   ├── KnowledgeGraph.vue  # 知识图谱
│       │   ├── JobSearch.vue       # 岗位管理
│       │   ├── JobEvolution.vue    # 岗位演化
│       │   ├── NewJobDiscovery.vue # 新岗位发现与能力动态更新
│       │   ├── ResumeParse.vue     # 简历解析
│       │   └── MatchReport.vue     # 人岗匹配
│       └── components/          # Navbar / TaskBar / KnowledgeGraph / Placeholder
├── data/                 # 数据目录（raw / processed / demo / schema）
├── data_pipeline/        # 数据处理管线脚本
├── scripts/              # 工具脚本
├── docs/                 # 项目文档
├── docker-compose.yml    # 容器编排
└── .env.example          # 环境变量模板
```

## 快速开始

### 1. 克隆仓库

```bash
git clone git@github.com:yhgg1234/NJUSTXH-202621-.git
cd NJUSTXH-202621-
```

### 2. 启动后端

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动后访问：
- API 文档（Swagger）：http://localhost:8000/docs
- API 文档（ReDoc）：http://localhost:8000/redoc

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

### 4. 启动数据库（可选，Docker）

```bash
docker-compose up -d neo4j
# Neo4j Browser: http://localhost:7474
```

---

## API 模块与输入格式说明

所有 API 使用 JSON 请求体（文件上传除外），开发阶段所有新模块接口返回 `501 Not Implemented`。

### 一、知识图谱 `/api/graph` ✅ 已实现

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/graph/schema` | 初始化图谱约束/索引 |
| POST | `/api/graph/import` | 批量导入节点和关系 |
| PUT | `/api/graph/nodes/{node_id}` | 创建/更新节点 |
| PUT | `/api/graph/relationships/{relationship_id}` | 创建/更新关系 |
| GET | `/api/graph/subgraph` | 子图查询 |
| GET | `/api/graph/stats` | 图谱统计 |

详细文档见 [`backend/app/graph/README.md`](backend/app/graph/README.md)。

---

### 二、数据采集 `/api/data-collection`

#### 数据源管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/sources` | 数据源列表 |
| POST | `/sources` | 注册数据源 |
| GET | `/sources/{id}` | 数据源详情 |
| PUT | `/sources/{id}` | 更新数据源 |
| DELETE | `/sources/{id}` | 删除数据源 |

**注册数据源** `POST /sources`
```json
{
  "name": "BOSS直聘-AI岗位",          // string 必填
  "type": "recruit_platform",          // enum 必填: search_engine|recruit_platform|enterprise_db|industry_report
  "url": "https://www.zhipin.com",     // string 可选
  "auth_info": { "api_key": "xxx" },   // object 可选
  "description": ""                    // string 可选
}
```

#### 采集任务
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/tasks` | 任务列表 |
| POST | `/tasks` | 创建采集任务 |
| GET | `/tasks/{id}` | 任务状态 |
| POST | `/tasks/{id}/cancel` | 取消任务 |

**创建采集任务** `POST /tasks`
```json
{
  "source_ids": ["src-001"],           // list[string] 必填
  "keywords": ["Python开发", "AI工程师"], // list[string] 必填
  "max_pages": 10,                     // int 1~100，默认10
  "schedule": "0 6 * * *"             // string 可选，cron表达式
}
```

#### 原始数据查询 `GET /raw-data`

| 参数 | 类型 | 说明 |
|------|------|------|
| `source_id` | string | 按数据源筛选 |
| `keyword` | string | 关键词搜索 |
| `date_from` | datetime | 起始时间 |
| `date_to` | datetime | 截止时间 |
| `page` | int | ≥1，默认1 |
| `page_size` | int | 1~100，默认20 |

---

### 三、数据清洗 `/api/data-cleaning`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/pipeline/defaults` | 获取默认管线配置 |
| POST | `/tasks` | 创建清洗任务 |
| GET | `/tasks` | 清洗任务列表 |
| GET | `/tasks/{id}` | 清洗任务状态 |
| GET | `/quality-check` | 待校验数据项列表 |
| POST | `/quality-review` | 提交人工校验 |
| GET | `/datasets` | 清洗后数据集 |
| GET | `/datasets/{id}` | 数据集条目详情 |
| DELETE | `/datasets/{id}` | 删除条目 |

**创建清洗任务** `POST /tasks`
```json
{
  "raw_data_ids": ["raw-001"],         // list[string] 必填
  "pipeline": {
    "dedup_method": "simhash",         // simhash|minhash，默认simhash
    "dedup_threshold": 0.9,            // 0.0~1.0，默认0.9
    "remove_noise": true,              // 去噪，默认true
    "normalize": true,                 // 规范化，默认true
    "human_review": false              // 人工校验，默认false
  }
}
```

**人工校验** `POST /quality-review`
```json
{
  "item_id": "item-001",               // string 必填
  "action": "edit",                    // enum: approve|reject|edit
  "edited_text": "修正后的文本",        // action=edit时必填
  "comment": ""                        // string 可选
}
```

---

### 四、信息抽取 `/api/extraction`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/entities/extract` | NER实体抽取 |
| POST | `/relations/extract` | 关系抽取 |
| POST | `/entities/align` | 实体对齐 |
| GET | `/entities/align/history` | 对齐历史 |
| GET | `/ontology` | 获取本体Schema |
| PUT | `/ontology` | 更新本体Schema |
| GET | `/ontology/entities` | 本体实体列表 |
| GET | `/ontology/relations` | 本体关系列表 |

**实体抽取** `POST /entities/extract`
```json
{
  "text": "我们正在招聘AI Agent开发工程师，要求精通Python和LangChain...",
  "entity_types": ["position", "skill", "education"],  // 可选，7种类型
  "use_rag": true                                      // 默认true
}
```

**实体类型（7种）：** `position` / `skill` / `certificate` / `industry` / `tech_stack` / `education` / `company`

**关系类型（8种）：** `requires` / `prefers` / `prerequisite` / `same_as` / `related_to` / `belongs_to` / `evolved_from` / `applies_to`

**关系抽取** `POST /relations/extract` — 先做实体抽取，将结果连同原文一并传入。

**实体对齐** `POST /entities/align`
```json
{
  "entities": [ ... ],                 // list[ExtractedEntity] 必填
  "method": "bert_semantic"            // bert_semantic|rule_based|hybrid
}
```

---

### 五、岗位管理 `/api/jobs`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 岗位列表（支持筛选） |
| POST | `/` | 创建岗位 |
| GET | `/{id}` | 岗位详情 |
| PUT | `/{id}` | 更新岗位 |
| DELETE | `/{id}` | 删除岗位 |
| GET | `/search` | 高级检索 |
| POST | `/discover-new` | 新岗位自动发现 |
| POST | `/evolution` | 演化分析 |
| GET | `/{id}/evolution-timeline` | 演化时间线 |
| GET | `/skills/hot` | 热门技能排行 |
| GET | `/skills/{name}/trend` | 技能趋势 |

**创建岗位** `POST /`
```json
{
  "title": "AI Agent开发工程师",        // string 必填
  "description": "负责基于LLM的Agent系统设计...",  // string 必填
  "skills": [
    {
      "name": "Python",                // string 必填
      "required": true,                // bool, true=必备 false=加分
      "proficiency": "精通",           // string 可选: 了解|熟悉|精通|专家
      "years": 3                       // int 可选
    }
  ],
  "education_required": "本科及以上",   // string 可选
  "experience_years": [3, 5],         // [int,int] 可选
  "industries": ["互联网"],            // list[string] 可选
  "tech_stacks": ["Python", "Docker"], // list[string] 可选
  "certificates": ["PMP"]             // list[string] 可选
}
```

**新岗位发现** `POST /discover-new`
```json
{
  "time_range": ["2026-01-01", "2026-06-30"],  // [string,string] 必填
  "novelty_threshold": 0.3,                     // 0.0~1.0，默认0.3
  "min_frequency": 5                            // ≥1，默认5
}
```

**演化分析** `POST /evolution`
```json
{
  "job_id": "job-001",                          // string 必填
  "granularity": "quarterly",                   // monthly|quarterly
  "time_range": ["2024-01-01", "2026-06-30"]   // 可选
}
```

---

### 六、简历解析 `/api/resume`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/upload` | 上传简历（PDF/DOCX） |
| POST | `/upload/batch` | 批量上传 |
| GET | `/` | 简历列表 |
| GET | `/{id}` | 结构化简历详情 |
| DELETE | `/{id}` | 删除简历 |
| GET | `/search` | 简历检索 |

**文件上传** `POST /upload`
- Content-Type: `multipart/form-data`
- 字段名: `file`
- 支持格式: 仅 PDF / DOCX
- 建议大小: ≤10MB

**解析结果包含：** 基本信息（姓名/邮箱/电话）、教育经历、工作经历、项目经验、技能/证书/语言列表、置信度(0~1)。

---

### 七、人岗匹配 `/api/matching`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/match` | 简历-岗位匹配 |
| GET | `/match/{id}` | 匹配报告详情 |
| POST | `/multi-match` | 多岗位对比 |
| POST | `/gap-analysis` | 差距分析 |
| POST | `/learning-path` | 学习路径规划 |
| GET | `/history` | 匹配历史 |

**单岗位匹配** `POST /match`
```json
{
  "resume_id": "resume-001",
  "job_id": "job-001"
}
```
返回4维度得分：技能(0~100)、经验(0~100)、学历(0~100)、行业(0~100) + 综合得分 + 各维度 matched/missing/surplus 明细。

**学习路径** `POST /learning-path`
```json
{
  "resume_id": "resume-001",
  "job_id": "job-001",
  "target_months": 6     // 1~24，默认6
}
```
返回三阶段学习计划（基础→核心→实战），每阶段含主题、课程、项目、证书、里程碑。

---

### 八、仪表盘 `/api/dashboard`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/overview` | 统计概览（总数/分布） |
| GET | `/trends` | 趋势数据 |
| GET | `/hot-rankings` | 热门技能/技术栈/行业排行 |
| GET | `/recent-activity` | 最近系统活动 |

**趋势查询参数：** `time_range` (如 `6m`/`1y`), `granularity` (`monthly`/`quarterly`)

---

## 数据流全景

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  数据采集      │ → │  数据清洗      │ → │  信息抽取      │
│  注册数据源    │    │  simhash去重   │    │  NER实体抽取   │
│  关键词采集    │    │  去噪+规范化   │    │  关系抽取      │
│  翻页爬取      │    │  人工校验      │    │  实体对齐      │
└──────────────┘    └──────────────┘    └──────┬───────┘
                                               │
                                               ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  人岗匹配      │ ← │  简历解析      │    │  知识图谱      │
│  4维打分       │    │  PDF/DOCX上传 │    │  Neo4j写入    │
│  差距分析      │    │  结构化抽取    │    │  子图查询      │
│  学习路径      │    │              │    │  统计分析      │
└──────────────┘    └──────────────┘    └──────┬───────┘
                                               │
                                               ▼
                                       ┌──────────────┐
                                       │  岗位管理      │
                                       │  岗位CRUD      │
                                       │  新岗位发现     │
                                       │  演化分析      │
                                       └──────────────┘
```

## 开发状态

| 模块 | API端点 | 状态 |
|------|--------|------|
| 知识图谱 | 6 | ✅ 已实现 |
| 数据采集 | 11 | 🏗️ 接口已定义（501） |
| 数据清洗 | 9 | 🏗️ 接口已定义（501） |
| 信息抽取 | 8 | 🏗️ 接口已定义（501） |
| 岗位管理 | 11 | 🏗️ 接口已定义（501） |
| 简历解析 | 6 | 🏗️ 接口已定义（501） |
| 人岗匹配 | 6 | 🏗️ 接口已定义（501） |
| 仪表盘 | 4 | 🏗️ 接口已定义（501） |
| **合计** | **52** | 1模块已实现 / 7模块待实现 |

## 分支策略

- `main` — 稳定版本，只接受合并
- `dev` — 开发主分支，日常开发从此拉分支
- `feature/xxx` — 功能分支，开发完成后合并回 `dev`

## 提交规范

```
feat: 新增功能
fix: 修复 bug
docs: 修改文档
test: 添加测试
refactor: 重构代码
chore: 配置、依赖等杂项
```

示例：`feat: 新增岗位JD数据采集模块`

## 核心指标

| 指标 | 目标值 |
|------|--------|
| JD 解析准确率 | ≥90% |
| 简历技能要素提取准确率 | ≥90% |
| 人岗匹配准确率 | ≥90% |
| 测试用例（含岗位JD） | ≥100 条 |
| 单元测试覆盖率 | ≥60% |

## 开发周期

2026年6月 — 2026年8月（3个月）

## 团队

挑战杯 · 揭榜挂帅擂台赛 · 题目编号 XH-202621
发榜单位：科大讯飞股份有限公司
