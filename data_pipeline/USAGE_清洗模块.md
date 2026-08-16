# 详细使用手册

本文档详细介绍 JD 数据预处理流水线的各项功能、参数、配置及操作方法。

---

## 目录

1. [命令行使用](#命令行使用)
2. [配置文件详解](#配置文件详解)
3. [各模块处理逻辑](#各模块处理逻辑)
4. [人工校验工具](#人工校验工具)
5. [日志与报告](#日志与报告)
6. [常见问题及调试](#常见问题及调试)

---

## 命令行使用

### 1. `quick_start.py` – 快速启动

适用于默认配置下的快速运行，参数最少。

```bash
python quick_start.py [--input INPUT] [--output OUTPUT]
```

| 参数       | 简写 | 默认值           | 说明                               |
| ---------- | ---- | ---------------- | ---------------------------------- |
| `--input`  | `-i` | `data.xlsx`      | 输入文件路径（支持 .xlsx 或 .csv） |
| `--output` | `-o` | `data/processed` | 输出目录                           |

示例：
```bash
python quick_start.py -i ./raw/jd_data.xlsx -o ./output
```

### 2. `run_pipeline.py` – 完整命令行入口

提供更精细的控制，包括日志级别设置。

```bash
python run_pipeline.py --input INPUT [--output OUTPUT] [--log-level LEVEL]
```

| 参数          | 必填                        | 说明                                          |
| ------------- | --------------------------- | --------------------------------------------- |
| `--input`     | 是                          | 输入文件路径                                  |
| `--output`    | 否（默认 `data/processed`） | 输出目录                                      |
| `--log-level` | 否（默认 `INFO`）           | 日志级别：`DEBUG`, `INFO`, `WARNING`, `ERROR` |

示例：
```bash
python run_pipeline.py -i data/raw/jobs.xlsx -o ./result --log-level DEBUG
```

### 3. 人工校验工具

```bash
python human_in_the_loop.py --input INPUT [--output OUTPUT]
```

| 参数       | 必填 | 说明                                                  |
| ---------- | ---- | ----------------------------------------------------- |
| `--input`  | 是   | 需要校验的文件（通常为 `needs_human_review.xlsx`）    |
| `--output` | 否   | 输出文件路径（默认在输入文件名后加 `_reviewed.xlsx`） |

---

## 配置文件详解

所有配置位于 `config.py`，建议根据实际数据特点调整。

### 字段映射 `FIELD_MAPPING`

定义原始列名到内部标准列名的映射。未映射的列将被丢弃。

```python
FIELD_MAPPING = {
    'jd_id': 'jd_id',
    'source_platform': 'source_platform',
    # ...
}
```

### 清洗配置 `CleaningConfig`

| 属性                        | 说明                                                 |
| --------------------------- | ---------------------------------------------------- |
| `required_fields`           | 必须存在的字段列表，缺失则删除整条记录               |
| `min_text_length`           | 各文本字段的最小长度阈值                             |
| `outlier_rules`             | 异常值检测规则，如经验范围、学历有效值               |
| `max_days_since_collection` | 数据时效性阈值（天），超过则标记为过时               |
| `null_handling`             | 各字段的空值处理策略：`drop` 删除，`fill` 填充默认值 |

### 去重配置 `DeduplicationConfig`

| 属性                        | 说明                                                       |
| --------------------------- | ---------------------------------------------------------- |
| `simhash_threshold`         | SimHash 相似度阈值（0~1），超过视为重复                    |
| `minhash_jaccard_threshold` | MinHash Jaccard 相似度阈值                                 |
| `similarity_fields`         | 用于计算相似度的字段及其权重                               |
| `inflation_keywords`        | 通胀词汇列表（如“世界顶级”），匹配则标记                   |
| `retention_strategy`        | 保留策略：`'latest'`（最新）或 `'most_complete'`（最完整） |

### 标注配置 `LabelingConfig`

| 属性                        | 说明                                       |
| --------------------------- | ------------------------------------------ |
| `quality_weights`           | 质量评分四个维度的权重（总和为1）          |
| `skill_extraction_patterns` | 技能词库，按类别组织，用于自动提取技能标签 |
| `human_review_sample_rate`  | 随机抽样标记为需人工校验的比例（0~1）      |

### 划分配置 `SplitConfig`

| 属性                                     | 说明                                    |
| ---------------------------------------- | --------------------------------------- |
| `train_ratio`, `val_ratio`, `test_ratio` | 训练/验证/测试集比例（总和1）           |
| `stratify_fields`                        | 分层采样使用的字段列表                  |
| `random_state`                           | 随机种子，保证可重复性                  |
| `min_samples_per_stratum`                | 每层最少样本数，少于该值则合并为“other” |

---

## 各模块处理逻辑

### 1. 数据清洗 (`DataCleaner`)

执行步骤顺序：
- **过滤无效记录**：删除缺失必填字段、文本过短的记录。
- **空值处理**：根据策略填充或删除。
- **文本规范化**：去除首尾空白、压缩多余空格、清理换行。
- **异常值检测**：校验经验年限（0~50年）、学历值合法性。
- **时滞检测**：计算采集时间距当前的天数，标记 `is_stale`。
- **标准化**：将经验和学历字段标准化为统一格式（如 `1-3年`，`本科`）。

### 2. 数据去重 (`Deduplicator`)

- **精确去重**：基于 `jd_id` 或 `url` 或组合字段（公司+岗位+城市+经验+学历）删除完全重复行。
- **SimHash**：将文本（岗位职责+要求+技能等）转为 SimHash 值，两两比较相似度，删除相似度超阈值的后续记录。
- **MinHash**：类似逻辑，采用 MinHash + Jaccard 相似度，适用于大规模文本。
- **抄袭检测**：比较职责和要求的文本内容，若重复度超过 90% 则保留较长者，删除较短者。
- **通胀检测**：标记包含通胀关键词的记录，不直接删除，供后续人工参考。
- **保留策略**：按 `retention_strategy` 保留最新或最完整的记录。

### 3. 标注与质量评分 (`DataLabeler`)

- **质量评分**：四项得分加权求和：
  - `completeness`：字段填充率（重要字段权重更高）。
  - `clarity`：文本长度、标点使用、数字出现等。
  - `specificity`：是否包含技能词、年限、学历、专业术语等。
  - `recency`：采集时间越近得分越高。
- **技能标签**：使用预定义词库在职责、要求等文本中匹配，生成各技能类别的标记列。
- **行业标签**：基于 `industry` 字段映射到一级行业（互联网、金融、医疗等）。
- **城市等级**：将城市映射为“一线/新一线/二线/其他/未知”。
- **职位等级**：根据岗位名称和经验推断初级/中级/高级/管理。
- **人工校验标记**：质量评分低于 0.6、含有通胀词汇或随机抽样的记录，标记 `needs_human_review=True`。

### 4. 数据集划分 (`DatasetSplitter`)

- 基于 `stratify_fields` 创建组合分层键，确保各层在训练/验证/测试集中保持相似分布。
- 使用 `train_test_split` 分两步进行：先分出训练集，再从剩余部分分出验证集和测试集。
- 自动处理样本过少的层（合并为“other”）。
- 验证划分后的比例偏差，并生成统计报告。

---

## 人工校验工具

交互式操作流程：

1. 运行 `human_in_the_loop.py --input <文件>`。
2. 程序逐条显示记录的关键信息（JD编号、岗位、公司、质量评分、标签等）。
3. 用户输入指令：
   - `a` / `approve`：通过（标记为正确）
   - `m` / `modify`：修改（随后输入修改意见）
   - `r` / `reject`：拒绝（标记为错误数据）
   - `s` / `skip`：跳过（待处理）
   - `b <action> [count]`：批量操作，如 `b a 10` 连续通过10条
   - `q` / `quit`：保存并退出
4. 退出后生成多个文件：`*_reviewed.xlsx`、`approved_records.xlsx`、`rejected_records.xlsx`、`modified_records.xlsx`、`pending_records.xlsx`。

---

## 日志与报告

- **运行日志**：`pipeline.log` 记录每个步骤的详细执行信息（DEBUG 级别会输出更多细节）。
- **步骤报告**：`reports/` 目录下每个模块生成一个 JSON 文件，包含统计信息和中间结果。
- **总结报告**：`summary_report.json` 提供整体数据流、质量指标和数据集大小。

---

## 常见问题及调试

### Q1：运行时报错“No module named 'simhash'”
**A**：请安装缺失依赖：`pip install simhash`（或 `datasketch`）。若无需该去重方式，可在 `deduplication.py` 中注释相应代码。

### Q2：为什么输出数据中有些字段不存在了？
**A**：检查 `config.py` 中的 `FIELD_MAPPING`，只有映射过的列才会保留，其余会被丢弃。若需保留，请添加映射。

### Q3：如何调整质量评分的阈值？
**A**：在 `LabelingConfig` 中修改 `quality_weights`，并可在 `labeling.py` 的 `_flag_for_human_review` 中调整判定条件（如 `<0.6`）。

### Q4：数据集划分比例不准确？
**A**：检查分层字段是否存在过多缺失值或极少数类别，导致无法分层。可调大 `min_samples_per_stratum` 或将某些字段值合并。

### Q5：人工校验工具无法打开 Excel 文件？
**A**：确保已安装 `openpyxl`。若文件较大，可考虑使用 `pandas` 的 `read_excel` 时指定 `engine='openpyxl'`。

### Q6：如何自定义技能词库？
**A**：编辑 `config.py` 中 `LabelingConfig.skill_extraction_patterns` 字典，添加或删除技能词汇即可。

---

如有其他问题，欢迎通过 Issue 反馈。