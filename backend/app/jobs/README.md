# 子任务 3.1：岗位能力动态演化分析

本模块基于 2.3 的周期化岗位—技能关系，生成岗位能力快照、相邻期变化、跨期趋势和
轻量预测结果。它不负责抓取、清洗、实体对齐或独立重建年度知识图谱。

## 边界与依赖

```text
2.1 / 数据管线：文档、岗位、技能、发布时间、证据
        ↓
2.3：同一 Neo4j 中的周期化 Job → Skill 关系
        ↓
3.1：时间切片、差分、趋势、质量提示、可视化数据
        ↓
2.4：复用相邻期变更；3.3：默认读取最新有效岗位快照
```

详见 [2.3 图谱时态契约](../graph/README.md)。

## 时间语义

| 字段 | 含义 | 使用位置 |
|---|---|---|
| `published_at` | JD/报告真实发布时间 | 归入月度或季度 |
| `crawled_at` | 系统采集时间 | 审计、时滞识别 |
| `period_key` | `2024Q1` / `2024-06` 等切片标识 | 周期关系 ID 与查询 |
| `period_start` / `period_end` | 统计窗口 | 图谱关系属性 |
| `valid_from` / `valid_to` | 结论业务有效期 | 图谱历史查询 |

API 的 `time_range` 是**包含首尾日期**的日历范围，例如
`["2024-01-01", "2025-12-31"]`。内部查询会转换为半开区间，避免遗漏结束日。

### 进入 3.1 前的数据验收

3.1 不从 Excel 文件元数据、导出日期或 `crawled_at` 推断历史趋势。只有带真实 `published_at` 的 JD 才能按发布时间归入周期；`crawled_at` 用于识别迟到/回补数据，并触发该历史周期的完整重算。

每个统计周期应满足：

1. 先以标准岗位 ID 和 `jd_id` 去重，再计算 `job_jd_count`；
2. 再计算包含每个标准技能的去重 JD 数 `skill_jd_count`；
3. 写入 `demand_ratio = skill_jd_count / job_jd_count`，不得使用关键词出现次数；
4. 每条周期关系保留至少一个 `evidence_id`，且证据可回链到 `Source` 节点；
5. 使用同一岗位、同一技能、同一关系类型、同一 `period_key` 的稳定关系 ID 覆盖该期完整快照。

没有时间字段的数据仍可进入 2.3 静态图谱；在补齐/回溯 `published_at` 前，3.1 会将其排除在趋势、变化和预测样本之外。至少 4 个连续周期才展示完整演化结论，至少 6 个连续周期才开放预测基线。

## 2.3 → 3.1 最小输入契约

每条 `REQUIRES_SKILL` 或 `BONUS_SKILL` 周期关系必须能够提供以下信息：

```json
{
  "id": "job:backend-engineer|REQUIRES_SKILL|skill:python|2024Q1",
  "type": "REQUIRES_SKILL",
  "from_id": "job:backend-engineer",
  "to_id": "skill:python",
  "properties": {
    "period_key": "2024Q1",
    "period_start": "2024-01-01T00:00:00+08:00",
    "period_end": "2024-04-01T00:00:00+08:00",
    "skill_jd_count": 56,
    "job_jd_count": 120,
    "demand_ratio": 0.4667,
    "importance": 0.82
  },
  "confidence": 0.93,
  "evidence_ids": ["source:jd-2024-001", "source:jd-2024-002"],
  "valid_from": "2024-01-01T00:00:00+08:00"
}
```

`skill_jd_count` 按“包含该技能的去重 JD 文档数”计数，不能按关键词在文本中的出现次数计数。
`demand_ratio` 是跨周期比较的主指标；`frequency` 仅作为兼容旧数据的回退字段。

## REST API

可先导入 8 个季度的离线演示数据验证完整链路：

```bash
curl -X POST http://localhost:8000/api/graph/import \
  -H "Content-Type: application/json" \
  --data-binary @../data/demo/job_evolution_sample.json
```

### `POST /api/jobs/evolution`

请求：

```json
{
  "job_id": "job:backend-engineer",
  "granularity": "quarterly",
  "time_range": ["2024-01-01", "2025-12-31"],
  "top_n": 10,
  "change_threshold": 0.05,
  "prediction_horizon_months": 6
}
```

响应包含：

- 每期 `skill_set`：技能需求占比、样本量、权重、证据；
- `changes_from_previous`：`added`、`removed`、`increased`、`decreased`；
- `hot_trends`、`cold_trends`：首末期需求占比差；
- `prediction`：至少 6 个周期后才返回线性趋势基线；
- `data_quality`：周期不足、样本量缺失、证据缺失等警告。

### `GET /api/jobs/{job_id}/evolution-timeline`

与 POST 返回相同结构，适合前端时间滑块刷新：

```text
GET /api/jobs/job:backend-engineer/evolution-timeline?granularity=quarterly&start=2024-01-01&end=2025-12-31&top_n=10
```

## 实施取舍

第一版实现岗位技能需求占比、相邻期差分、趋势、数据质量与线性外推。中心性、社区发现和
复杂预测需要 Neo4j GDS 或额外分析依赖，等多期真实数据稳定后再接入；不能用少于 4 个周期的数据
得出完整演化结论，也不应在少于 6 个周期时展示预测。

## 测试要点

- 月度/季度归期和时区；
- 同 JD 去重后的分母；
- 新增、删除、增强、减弱；
- 少于 4 期和少于 6 期的质量/预测降级；
- 时间过滤只读取指定周期，不混入历史关系；
- 3.3 读取默认最新快照，不重复计入同一技能的历史版本。
