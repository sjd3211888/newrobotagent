# Robot Agent

机器人 Agent 平台重构工程。目标是在完整保留 VoiceAgent 业务能力的基础上，建立可扩展、可维护、可验证的机器人任务平台。

**当前状态（2026-10-10）：** 工程规范、文档模板与检查入口已建立；业务运行时、功能迁移和实机验证尚未开始。Eino 是优先原型候选，生产架构和依赖版本尚未冻结。

## 按顺序阅读

1. [文档导航](docs/README.md)：各类文档的用途、当前迭代与状态。
2. [功能基线](docs/requirements/README.md)：原工程能力分类与后续回归要求。
3. [架构边界](docs/architecture/README.md)：目前确认的原则与未冻结的技术选择。
4. [工程规范](docs/standards/README.md)：代码、文档、迭代、测试与交付规则。
5. [开发指南](CONTRIBUTING.md)：环境、分支和统一检查命令。
6. [ITER-001 实施计划](docs/plans/ITER-001-engineering-standards.md)与[验收记录](docs/reports/ITER-001-engineering-standards.md)。

AI 开始工作前先读 [AGENTS.md](AGENTS.md)。运维与后续交付入口见[运行维护导航](docs/operations/README.md)。

## 当前可运行的检查

需要 Git 与 Python 3.10+。从仓库根目录运行：

```sh
python scripts/check.py --scope all
```

该命令检查文档和文件放置，执行工程工具测试，并在存在 Go 模块时运行 Go 格式、静态检查与单元测试。没有适用业务代码的阶段会明确显示“不适用”。它不会启动模型服务、连接机器人或部署代码。

## 工作约定

- 按场景小步闭环：需求与验收条件 → 设计 → 计划 → 实现和测试 → 验收。
- 检查通过后在任务分支做本地提交；推送、合并、发布按明确授权执行。
- 当前有效规范集中在 `docs/standards/`；每轮设计、计划、结果通过同一迭代编号关联。
- 原工程位于本机 `D:\voiceagent`，仅作为业务和协议参考，本仓库不会修改它。

历史选型讨论见[研究导航](docs/research/README.md)。
