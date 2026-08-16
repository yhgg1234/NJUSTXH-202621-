# 子任务 2.2 标准化与月度图谱管线

该目录保存可复现的 2.2 数据处理程序。程序读取 2.1 Excel，使用固定岗位本体和实体同义词
进行确定性对齐，输出逐 JD 标准化记录、月度图谱批次、去重日志和质量报告。

## 文件

| 文件 | 用途 |
|---|---|
| `parse_excel.py` | 读取 Excel、统一原始字段名并解析 JSON 列 |
| `entity_aligner.py` | 实体对齐、兜底技能恢复、月度聚合和输出校验 |
| `job_ontology.json` | 标准岗位 ID、名称和别名 |
| `synonym_map.json` | 技能、学历和技术生态的标准实体映射 |
| `requirements.txt` | 管线独立依赖 |

字段语义以 [`data/schema/README.md`](../../data/schema/README.md) 为准。

## 输入和输出

默认输入：

```text
data/raw/1000条抽取数据.xlsx
```

默认输出目录：

```text
data/processed/task_2_2/
```

输出文件：

```text
normalized_records.jsonl
graph_import_batch.json
deduplication_logs.json
quality_report.json
```

`data/raw/` 和 `data/processed/` 中的大规模真实数据受 `.gitignore` 保护，不会被提交到仓库。

## 安装依赖

在项目使用的 Conda 环境中执行：

```powershell
python -m pip install -r data_pipeline/task_2_2/requirements.txt
```

## 运行

使用默认目录：

```powershell
python -m data_pipeline.task_2_2.entity_aligner
```

指定输入和输出：

```powershell
python -m data_pipeline.task_2_2.entity_aligner `
  --input "E:\path\to\1000条抽取数据.xlsx" `
  --output-dir "data\processed\task_2_2"
```

复现实验或测试时可以固定批次 ID：

```powershell
python -m data_pipeline.task_2_2.entity_aligner `
  --input "E:\path\to\1000条抽取数据.xlsx" `
  --output-dir "tmp\task_2_2_validation" `
  --batch-id "task-2.2-validation-001"
```

程序退出码为 `0` 表示内置图谱验收通过；退出码为 `1` 表示质量报告中存在图谱错误。

## 本版本已处理的问题

- JSONL 和 Source 节点均保留 2.1 原始 `crawled_at`；
- 2.2 运行时间只写入 `alignment_meta.normalized_at` 和质量报告 `generated_at`；
- 图谱 `properties` 自动剔除 `null`，可以直接通过 2.3 模型校验；
- 去重不再改变正文、职责和要求与 JD 的对应关系；
- 岗位技能关系按 `(job_id, period_key, skill_id)` 聚合；
- 关系 ID 包含月份，证据只来自当前月份；
- 质量报告区分结构有效记录和 2.4/3.1 技能分析有效记录；
- 质量报告包含月份分布、周期关系数、跨月证据数和图谱校验结果。
