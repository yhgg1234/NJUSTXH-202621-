# Data Directory

该目录用于存放项目数据、样例和字段说明。

- `demo/`：放少量样例数据、演示数据和 Excel 模板，可提交到 Git。
- `raw/`：放原始采集数据。大规模真实数据不要提交到 Git，仅保留 `.gitkeep`。
- `processed/`：放清洗、去重、标准化后的数据。大规模真实数据不要提交到 Git，仅保留 `.gitkeep`。
- `schema/`：放字段说明、数据字典、Excel 模板字段定义等文档。

数据采集、清洗、导出等相关代码统一放在项目根目录的 `data_pipeline/`。
