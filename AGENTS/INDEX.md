# 项目记忆导航

核对日期：2026-10-29（Asia/Hong_Kong）。本文定义信息归属与阅读路线；代码基线和运行验证边界见 [CURRENT_STATE.md](CURRENT_STATE.md)。

## 必读顺序与优先级

新会话依次读本文件 → [PROJECT.md](PROJECT.md) → [REQUIREMENTS.md](REQUIREMENTS.md) → [CURRENT_STATE.md](CURRENT_STATE.md) → [HANDOFF.md](HANDOFF.md)，然后核对 Git 和当前任务代码。P0 为每次接手必读，P1/P2 按需读取，不要求每轮加载全部文档。

| 文件 | 优先级 | 唯一主要职责／何时读取 |
| --- | --- | --- |
| [PROJECT.md](PROJECT.md) | P0 | 长期背景、产品定位、用户来源与边界 |
| [REQUIREMENTS.md](REQUIREMENTS.md) | P0 | 用户意图、稳定需求编号、待确认需求；新增需求先读 |
| [CURRENT_STATE.md](CURRENT_STATE.md) | P0 | 简洁的分支、基线、当前进度与验证快照 |
| [HANDOFF.md](HANDOFF.md) | P0 | 本轮结果、未提交修改、下一步接手操作 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | P1 | 技术栈、启动、配置、存储和架构图 |
| [MODULES.md](MODULES.md) | P1 | 文件、函数和功能修改入口 |
| [API.md](API.md) | P1 | HTTP 接口、数据字段和错误契约 |
| [DATA_FLOW.md](DATA_FLOW.md) | P1 | 扫描、队列、导出和预览的跨模块流程 |
| [DECISIONS.md](DECISIONS.md) | P1 | 决策状态、证据、未知原因和影响 |
| [KNOWN_ISSUES.md](KNOWN_ISSUES.md) | P1 | 问题编号、静态风险、复现方法及验证程度 |
| [DEVELOPMENT_RULES.md](DEVELOPMENT_RULES.md) | P1 | 开发、测试、安全、文档和 GitKraken 约束 |
| [CHANGELOG.md](CHANGELOG.md) | P2 | 有证据的重要历史变更，不代替 Git 日志 |
| [LEARNING_GUIDE.md](LEARNING_GUIDE.md) | P2 | 阅读路线、项目对应知识与小练习 |
| [TASKS/ACTIVE/](TASKS/ACTIVE/README.md) | 相关任务 P1 | 未完成的重要任务；README 是说明，不是活动任务 |
| [TASKS/COMPLETED/](TASKS/COMPLETED/2026-10-29-project-memory-bootstrap.md) | P2 | 已完成任务的目标、方案和验收证据 |

## 按任务选择

- 启动／迁移电脑：架构、交接、已知问题中的 `KI-005`、`KI-007`。
- 界面／选择／列表：模块、API、需求；必要时读 `KI-002`、`KI-003`、`KI-004`。
- 扫描／转换／预览：架构、模块、API、数据流、已知问题。
- 新功能／结构调整：需求、开发规范、架构、决策及相关 ACTIVE 任务；先方案确认。
- 排错：已知问题 → 模块和 API → 实际代码，先复现再定性。
- 学习：学习指南 → 对应源码；只读不更新状态。
- 交接／额度不足：交接、当前状态和相关 ACTIVE 任务优先。

## 证据和维护约定

“用户确认”只指本次明确要求或可追溯的用户确认；“文档记载”指现有 README；“代码事实”指当前实现；“静态风险”未运行复现；“待用户确认”不能作为已批准需求。事实变更时更新其主要归属文件，其他文档通过链接引用，避免多处维护同一详细说明。

所有路径相对仓库根目录（链接从当前文档目录解析），函数名用于 IDE 搜索，不把本机绝对路径写成迁移前提。日期只写有证据的事件或本轮记录日期；不把记录日期当作历史决策日期。过期状态替换为当前快照，历史放 CHANGELOG 或 COMPLETED；需求、决策和问题编号不重新编号、不复用。

任务使用 `YYYY-MM-DD-简短主题.md`；重要未完成任务放 ACTIVE，完成后移动原文件到 COMPLETED。任务至少记录目标、用户原始需求及后续确认、验收标准、方案、涉及文件、进度、测试、决策和完成状态；不得用原始聊天日志替代整理。初始化任务档案含本轮的 12 项交接自测。
