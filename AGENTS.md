# AI 项目入口

SteamClipExporter 是将 Steam 本地录像分段批量导出为 MP4 的工具，使用原生 Web 前端、Python Flask、pywebview 和 FFmpeg。全部项目记忆位于 [AGENTS/INDEX.md](AGENTS/INDEX.md)，供用户学习及不同会话、账号、电脑和 AI 工具交接。不要依赖此前聊天记录。

## A．新会话启动

1. 开始分析、修改或开发前，依次读取 [INDEX](AGENTS/INDEX.md)、[PROJECT](AGENTS/PROJECT.md)、[REQUIREMENTS](AGENTS/REQUIREMENTS.md)、[CURRENT_STATE](AGENTS/CURRENT_STATE.md)、[HANDOFF](AGENTS/HANDOFF.md)。
2. 检查 `git status --short --branch`、最近提交及与任务有关的实际代码；无 Git 信息时明确记录限制。不要修改 Git 配置来掩盖环境问题。
3. 按 `INDEX.md` 的任务导航读取其他文档。文档与代码矛盾时指出差异；代码行为不能自动视为用户需求，未知内容写“待确认”。
4. 修改前简要说明当前理解、影响范围和准备执行的任务。只读提问无需更新文件。

## B．新功能与修改边界

先明确需求和验收标准，检查与现有需求的冲突，分析影响范围。复杂任务在 `AGENTS/TASKS/ACTIVE/` 建档。新功能先提出方案，等待用户确认后再实施。当前记忆系统初始化任务仅授权 Markdown 文档；后续代码工作须依据届时的用户授权。

遵守 [DEVELOPMENT_RULES](AGENTS/DEVELOPMENT_RULES.md)：保持兼容，不进行无关重构、格式化、安装或依赖升级；不擅自处理用户已有修改；不向记忆文档写入密码、Token、API Key 或个人隐私。不自动执行 Git 暂存、commit、push、reset、rebase 等变更操作，版本管理由用户在 GitKraken 手动完成。

## C．完成开发后的维护

完成代码修改及必要测试后，检查实际 diff，更新 `CURRENT_STATE.md`、`HANDOFF.md`；按影响更新 `CHANGELOG.md`、`REQUIREMENTS.md`、`ARCHITECTURE.md`、`DECISIONS.md`，以及受影响的模块、API、数据流、问题或学习说明。仅更新受影响内容，不全文重写。完成的任务移至 `TASKS/COMPLETED/`，保留测试证据、未验证内容和风险，再向用户解释结果。纯问答不产生维护任务。

## D．交接触发与跨账号要求

用户说“准备交接”“更新记忆”“保存当前进度”“我要换账号了”时，暂停新功能开发：核对 Git 状态和未提交修改，总结已完成及未完成工作，更新 `CURRENT_STATE.md`、`HANDOFF.md` 和相关 ACTIVE 任务，写出新 AI 的具体下一步；不擅自提交或推送。无法执行工具或写文件时，明确说明未保存，不声称交接已落盘。

跨账号传递完整项目文件夹及本地运行依赖，核对未跟踪文件；文档使用仓库相对路径，不依赖旧电脑盘符、旧账号、全局技能或聊天附件。新 AI 必须重新核对工作区与运行条件。此系统是需要助手执行的维护约定，没有后台自动同步程序；其他 AI 工具不自动识别本入口时，应由用户显式要求读取。
