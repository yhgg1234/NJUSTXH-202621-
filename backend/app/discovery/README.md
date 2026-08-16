# 子任务 2.4：新岗位发现与既有岗位能力动态更新

本模块不再使用演示候选。正式数据流为：

```text
2.2 normalized_records.json/jsonl ─┐
                                  ├─> 2.4 发现、定义、证据链、人工审核
2.3 Job/Skill 图谱与周期快照 ─────┘                  │
                                                     └─审核通过后批量写回 2.3
```

## 输入

通过 `DISCOVERY_NORMALIZED_PATH` 配置 2.2 的 `normalized_records.jsonl`、JSON 文件或目录。字段规范以
`data/schema/README.md` 的 B 层契约为准。用于时序发现的记录必须有带时区的 `published_at`、稳定
`jd_id/source_id`、标准岗位和技能、公司、行业及证据。

2.3 不需要额外导出文件。2.4 通过依赖注入直接调用 `GraphService.get_subgraph()`、
`get_job_evolution_rows()` 和 `import_graph()`。

候选、人工优化、审核结论和变更日志保存到 `DISCOVERY_STATE_PATH`。默认使用 JSON 原子文件，服务接口
与存储解耦，生产部署可替换为 MySQL/MongoDB。

## 发现算法

`skill-community-novelty-v1` 执行以下可复现步骤：

1. 按稳定岗位候选 ID/岗位名形成种子组；
2. 在岗位—技能二部图投影上，按标题相似度与技能 Jaccard 相似度连接种子组，以连通分量形成候选社区；
3. 与 2.3 的正式岗位技能画像计算最大 Jaccard 相似度，`novelty = 1 - max_similarity`；
4. 统计相邻月度/季度的 JD 频次变化，并检查公司数、来源渠道数和抽取质量；
5. 基于真实 JD 证据生成岗位名称、核心职责、必备技能、加分技能和典型行业应用场景；
6. 人工可编辑定义、采纳或否决；只有图谱批次写入成功后才记录为已采纳。

默认验收门槛为 5 条去重 JD、2 家公司、2 个来源渠道。所有阈值均通过发现请求显式记录，不能用抓取
时间替代发布时间。

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/jobs/discover-new` | 执行发现 |
| GET | `/api/jobs/discover-new/stats` | 审核统计 |
| GET | `/api/jobs/discover-new/history` | 候选与审核历史 |
| GET/PUT | `/api/jobs/discover-new/{candidate_id}` | 查看/人工优化定义 |
| POST | `/api/jobs/discover-new/{candidate_id}/adopt` | 审核通过并可写入 2.3 |
| POST | `/api/jobs/discover-new/{candidate_id}/reject` | 否决并记录原因 |
| POST | `/api/jobs/discover-new/batch/adopt` | 批量采纳 |
| POST | `/api/jobs/discover-new/batch/reject` | 批量否决 |
| POST | `/api/jobs/discovery/evaluate` | 使用人工金标准计算 Precision/Recall/F1 |
| POST | `/api/jobs/ability-changes/analyze` | 比较两个周期并生成变更日志 |
| GET | `/api/jobs/ability-changes` | 查询变更日志 |
| PUT | `/api/jobs/ability-changes/{change_id}/review` | 审核变更项 |

## 验收数据

- 新岗位案例：至少 5 条去重 JD，建议覆盖至少 2 家公司、2 个来源及两个相邻周期；
- 既有岗位更新：2.3 中至少两个同粒度周期快照，且关系包含样本计数、需求占比和证据 ID；
- `quality_report.json` 用于证明重复、缺失发布时间和低置信度样本已经处理；
- 算法准确率需另行使用人工金标准测试集评估，本模块不会用候选置信度冒充准确率。
