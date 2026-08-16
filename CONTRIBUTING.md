# 提交规范（Commit Message Convention）

本项目采用 [Conventional Commits](https://www.conventionalcommits.org/) 规范。

## 格式

```
<type>: <description>

[optional body]
```

## 类型说明

| Type | 说明 | 示例 |
|------|------|------|
| `feat` | 新增功能 | `feat: 新增岗位JD数据采集模块` |
| `fix` | 修复 bug | `fix: 修复简历解析中文编码问题` |
| `docs` | 文档变更 | `docs: 更新API接口文档` |
| `test` | 测试相关 | `test: 添加人岗匹配单元测试` |
| `refactor` | 代码重构 | `refactor: 重构知识图谱构建逻辑` |
| `chore` | 配置/依赖 | `chore: 更新Docker镜像版本` |
| `style` | 格式调整 | `style: 统一import排序` |
| `perf` | 性能优化 | `perf: 优化图谱查询性能` |

## 注意事项

- 不要只写"修改"、"更新"、"1" 这种无意义信息
- description 用中文，简明描述改动内容
- 大的功能模块拆分为多次 commit，每次 commit 做一件事
