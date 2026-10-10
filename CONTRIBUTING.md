# 开发指南

状态：有效 · 日期：2026-10-10 · 范围：全仓库 · 关联：ITER-001

## 环境与入口

当前仅有文档与 Python 工程工具，需要 Git 和 Python 3.10+，脚本仅依赖标准库。Windows 可在 PowerShell 执行，Linux 可在 shell 执行；仓库内使用相对路径。

Go 是 Eino 原型的预期语言，具体工具链和框架版本在原型设计中固定。本轮不创建业务 `go.mod`，不把开发机已安装版本视为生产依赖。C++、前端和现场硬件工具链在引入对应代码时记录。

阅读顺序见[根 README](README.md)，目录与编码规则见[工程规范](docs/standards/README.md)。

## 开始一轮工作

```sh
git status --short
git switch -c feat/short-topic
```

从已确认的基线创建任务分支。工作区不干净时先确认归属，不自动 stash、丢弃或带走他人的修改。分支与提交命名见[Git 与交付规范](docs/standards/git-delivery.md)。

按[迭代规范](docs/standards/workflow.md)填写需求、设计和计划。首次使用的代码目录随本轮内容建立，不生成空业务骨架。

## 检查命令

```sh
python scripts/check.py --scope docs
python scripts/check.py --scope code
python scripts/check.py --scope all
```

- `docs`：必需文件、目录放置和 Markdown 本地文件引用检查。
- `code`：Python 工程工具回归；存在 Go 模块时运行 `gofmt -l`、`go vet ./...`、`go test -count=1 ./...`。
- `all`：上述两部分依次执行；任一失败返回非零退出码。

检查脚本不会修复或改写文件。仅验证本地文件目标，不请求外部 URL，不验证 Markdown 锚点是否存在。Go 检查不包含模型、数据库或设备集成测试；这些验证必须在场景计划中单独列出。

Go 源码确需格式化时显式运行 `gofmt -w <本轮文件>`。新增 C++、前端等源代码前，必须接入对应检查；脚本检测到尚未配置的语言检查会失败。

## 提交与完成

```sh
git diff --check
git diff
git add -- <本轮具体文件或目录>
git diff --cached
git commit -m "docs: describe the change"
```

记录执行命令、结果和未验证项，更新导航及本轮验收报告。推送、合并、发布需要已有明确授权。不能把“本地检查通过”写成“真实机器人可用”。
