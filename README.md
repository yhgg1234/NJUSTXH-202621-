# JD 数据预处理流水线

一套用于招聘网站职位描述（JD）数据的自动化预处理工具，涵盖数据清洗、去重、质量评分、标签生成、数据集划分及人工校验等全流程，为后续模型训练或分析提供高质量数据集。

---

## 功能特点

- **数据清洗**：过滤无效记录、处理缺失值、规范文本格式、标准化经验和学历字段、检测过时数据。
- **智能去重**：精确去重、SimHash 近似去重、MinHash 相似度去重、抄袭检测、通胀词汇标记。
- **质量标注**：计算完整性、清晰度、具体性、时效性四个维度的质量评分；自动提取技能标签、行业标签、城市等级、职位等级。
- **数据集划分**：支持按行业、城市、学历等维度分层采样，生成训练集、验证集、测试集（默认 7:1.5:1.5）。
- **人工校验支持**：内置交互式工具，可对自动标注结果进行人工审核、修改或拒绝，并导出分类结果。
- **可配置化**：所有参数集中管理于 `config.py`，易于调整阈值、字段映射、评分权重等。

---

## 系统要求

- Python 3.8 及以上
- 依赖包列表见 [安装](#安装)

---

## 安装

1. 克隆或下载本项目代码。
2. 安装依赖（建议使用虚拟环境）：
   ```bash
   pip install pandas numpy openpyxl loguru jieba simhash datasketch scikit-learn
   ```
   若需运行单元测试，还需 `unittest`（内置）。
3. 将原始数据文件（Excel 或 CSV）放置于项目根目录，命名为 `data.xlsx`（或通过参数指定）。

---

## 快速开始

### 使用默认配置一键运行

```bash
python quick_start.py
```

该命令默认读取当前目录下的 `data.xlsx`，处理后输出到 `data/processed/` 目录。

### 指定输入输出文件

```bash
python quick_start.py --input 您的数据.xlsx --output 输出目录
```

或使用更详细的命令行脚本：

```bash
python run_pipeline.py --input 您的数据.xlsx --output data/processed/
```

---

## 输出结果

处理后生成的目录结构如下：

```
data/processed/
├── final_dataset.xlsx          # 完整的高质量数据集（含所有标注）
├── train_set.xlsx              # 训练集
├── val_set.xlsx                # 验证集
├── test_set.xlsx               # 测试集
├── needs_human_review.xlsx     # 需人工校验的数据（如有）
├── summary_report.json         # 总结报告（含各步骤统计）
├── pipeline.log                # 运行日志
└── reports/                    # 各步骤详细报告（JSON格式）
    ├── cleaning_report.json
    ├── deduplication_report.json
    ├── labeling_report.json
    └── splitting_report.json
```

---

## 配置调整

所有可调参数集中在 `config.py` 中，主要配置类包括：

- `CleaningConfig`：清洗策略（必填字段、文本长度阈值、异常值规则、空值处理等）。
- `DeduplicationConfig`：去重阈值（SimHash 相似度、MinHash Jaccard 阈值、通胀关键词列表等）。
- `LabelingConfig`：质量评分权重、技能词库、人工校验采样率等。
- `SplitConfig`：数据集划分比例、分层字段、随机种子等。

修改 `config.py` 后再次运行即可生效。

---

## 人工校验工具

如果自动标注后存在需要人工审核的记录，可使用交互式工具进行校验：

```bash
python scripts/human_in_the_loop.py --input data/processed/needs_human_review.xlsx
```

工具会逐条展示记录，并提供通过、修改、拒绝、跳过、批量操作等选项，最终生成分类结果文件。

---

## 运行测试

执行单元测试以验证各模块功能：

```bash
python -m unittest test_pipeline.py
```

---

## 项目结构

```
.
├── config.py                  # 全局配置文件
├── pipeline.py                # 主流水线
├── data_cleaning.py           # 清洗模块
├── deduplication.py           # 去重模块
├── labeling.py                # 标注模块
├── dataset_split.py           # 数据集划分模块
├── quick_start.py             # 快速启动脚本
├── run_pipeline.py            # 完整命令行入口
├── human_in_the_loop.py       # 人工校验工具
├── test_pipeline.py           # 单元测试
└── README.md / USAGE.md       # 本文档
```

---

## 常见问题

### 1. 输入文件格式支持哪些？
支持 `.xlsx` 和 `.csv` 格式。若为 `.csv`，请确保编码为 UTF-8。

### 2. 如何自定义字段映射？
在 `config.py` 的 `FIELD_MAPPING` 字典中修改原始列名到内部标准列名的映射关系。

### 3. 为什么有很多记录被标记为“需人工校验”？
默认约 10% 的记录会随机抽样标记，加上质量评分较低或包含通胀词汇的记录也会被标记，以保证数据集质量。

### 4. 去重后数据量明显减少，是否正常？
正常。数据中可能存在大量重复或高度相似的 JD，去重模块会保留最完整或最新的记录，从而减少数据冗余。

---

## 贡献与许可

欢迎提交 Issue 或 Pull Request。  
本项目遵循 [MIT License](LICENSE)（若需许可证文件请自行添加）。
