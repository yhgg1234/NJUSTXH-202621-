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
XH21/
├── backend/              # 后端（FastAPI）
│   ├── app/
│   │   ├── main.py       # 应用入口
│   │   ├── config.py     # 配置管理
│   │   └── routers/      # API 路由模块
│   ├── tests/            # 后端测试
│   └── requirements.txt  # Python 依赖
├── frontend/             # 前端（Vue 3）
│   ├── src/
│   ├── App.vue
│   ├── index.html
│   └── package.json
├── data/                 # 数据目录
│   ├── raw/              # 原始采集数据
│   ├── processed/        # 清洗后数据
│   └── demo/             # 演示数据
├── scripts/              # 工具脚本（爬虫、数据处理等）
├── docs/                 # 项目文档
├── docker/               # Docker 相关配置
├── docker-compose.yml    # 容器编排
├── .env.example          # 环境变量模板
└── README.md
```

## 快速开始

### 1. 克隆仓库

```bash
git clone https://gitee.com/sulianbo606/XH21.git
cd XH21
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入实际配置
```

### 3. 启动基础设施（Docker）

```bash
# 启动 Neo4j 图数据库
docker-compose up -d neo4j
```

启动后访问 http://localhost:7474 管理 Neo4j。

### 4. 启动后端

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

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
