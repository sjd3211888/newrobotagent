# ITER-001：工程规范实施计划

状态：已完成 · 日期：2026-10-10 · 范围：规范、模板、检查工具 · 关联：ITER-001

**Goal:** 建立可顺序阅读、可持续迭代、可自动检查的机器人 Agent 工程规范。

**Architecture:** 单仓库按职责组织代码；有效规范、需求架构与迭代记录分开；统一检查执行基础规则，人工确认设计和业务质量。

**Tech Stack:** Markdown、Git、Python 标准库；Go 检查仅在引入 Go 模块后适用。

执行者按任务清单逐项实现与自审；用户已授权实施与本地提交。本轮无需并行 agent 或业务 worktree。设计见[ITER-001 设计](../designs/ITER-001-engineering-standards.md)，结果见[验收报告](../reports/ITER-001-engineering-standards.md)。

## 任务

- [x] 初始化 main，提交原选型文档作为基线，建立 `chore/engineering-standards` 分支。
- [x] 建立根 README、AGENTS、CONTRIBUTING、编辑器和 Git 属性/忽略规则。
- [x] 建立 `docs/standards` 的目录、编码、文档、迭代、测试和交付规范。
- [x] 建立功能分类、架构边界、决策、研究和运维导航。
- [x] 建立 `docs/templates` 五类模板、本轮设计和计划。
- [x] 迁移选型资料并修正缺失原工程引用。
- [x] 实现 `scripts/check.py` 和 `tests/tooling/test_check.py`，通过断链、错误放置、语言适用性与外部命令错误回归。
- [x] 执行 `python scripts/check.py --scope docs`、`--scope code`、`--scope all`，检查 scope 参数与失败退出行为。
- [x] 执行 `git diff --check`，审查文档覆盖、导航、敏感内容和暂存范围。
- [x] 完成本轮验收报告、更新状态，显式暂存后本地提交。

## 验收与范围

用户能够从 README 找到完整规范；机器检查能发现断链和错误放置；模板能表达需求到交付全过程。业务代码、框架性能、真实服务、硬件和部署本轮不适用，不创建空业务目录。

代码任务只包含工程工具。Go 测试执行与失败传播通过模拟外部命令验证；本轮没有业务 Go 模块，不声称已验证 Go 业务。

## 交付

仅做本地提交，不推送、不合并、不部署。原工程不修改。正式提交前以报告记录实际测试数量、命令和限制，保留原始选型基线。
