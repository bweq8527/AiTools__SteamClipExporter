# 跨账号／会话交接

交接记录：2026-10-29（Asia/Hong_Kong）。给没有旧聊天记录的新 AI：先读根入口，再按 INDEX 的核心顺序接手；本文件不代表授权开始修复业务。

## 项目整体情况

SteamClipExporter 把本地 Steam `clip_*` 录像分段导出为 MP4。原生 Web 前端通过本地 Flask API 操作目录、排队和读取进度；pywebview 提供桌面窗口；FFmpeg／FFprobe 处理媒体。队列、路径和状态仅在内存，启动与依赖细节见 [ARCHITECTURE.md](ARCHITECTURE.md)。

用户从 Gemini 网页 Vibe Coding 逐步转向理解架构、学习开发和独立维护，希望完整项目文件夹能交给不同账号／电脑／工具。旧 Gemini 对话和此前分析文本不在本轮上下文内；已确认意图归 [REQUIREMENTS.md](REQUIREMENTS.md)，不要从代码补写历史需求。

## 本轮目标和结果

- 原始任务只允许 Markdown：建立指定记忆文档、维护规则、学习指南、TASKS 档案，并做 12 问交接自测。
- 已完成内容：目录／隐藏项目文件检查（不展开 Git 对象库）、Git 状态与近期历史核对、现有 README 和全部业务源码核对、记忆分工与证据分级、已知问题和接手路线整理，以及文档限定的 12 问接手自测。本轮记忆初始化完成。
- 新增文件：根 `AGENTS.md`；`AGENTS/` 下 `INDEX.md`、`PROJECT.md`、`REQUIREMENTS.md`、`ARCHITECTURE.md`、`MODULES.md`、`API.md`、`DATA_FLOW.md`、`DECISIONS.md`、`CURRENT_STATE.md`、`CHANGELOG.md`、`KNOWN_ISSUES.md`、`DEVELOPMENT_RULES.md`、`LEARNING_GUIDE.md`、本文件；`TASKS/ACTIVE/README.md`；[本轮 COMPLETED 档案](TASKS/COMPLETED/2026-10-29-project-memory-bootstrap.md)。共 17 个 Markdown。
- 未改现有 README、业务／构建／启动文件、二进制或 IDE 配置。没有安装、运行 bat、构建、暂存、提交或推送。
- 未完成的本轮业务开发：无，本轮没有业务任务。尚未选择下一项业务目标；待确认项不是已经接受的开发排期。

## 交接时工作区

- 本地分支 `main`，显示跟踪 `origin/main`；HEAD 为 `3e930fc9d4544ad1def95f008ee41af551ee992f`。未 fetch，远端实时情况未知。
- 本轮之前已跟踪文件无修改，已有未跟踪 `bin/ffmpeg.exe`、`bin/ffprobe.exe`；本轮文档也是未跟踪／未提交状态，后续用户可能手动提交，接手时必须复查。
- 两个 exe 是本地运行依赖，不能因为未跟踪而删除或误称本轮创建。Git 中只有对应 zip，不保证新克隆直接包含可执行工具；完整文件夹迁移与仅 Git 克隆不同。
- 曾因沙箱用户与仓库所有者不同遇到 Git 所有权检查；使用单次命令参数 `git -c safe.directory=<当前已核实仓库绝对路径> ...` 完成只读核对，没有持久修改 Git 全局配置。新机器应使用实际路径，不复制旧电脑盘符。

## 已执行验证和未验证内容

本轮静态证据：5 个 Python 源文件通过 `ast.parse`，未导入 app、未写 pyc；`node --check frontend/script.js` 退出 0；9 个业务路由与 API 文档匹配，模块地图可定位 36 个源码函数；17 份文档齐全、62 个本地链接有效，结构检查无错误。原有 26 个文件的 SHA-256 比较无变化，受保护的原有源码／README 对 HEAD 无 diff。12 问文档接手自测通过，其中历史问题和下一业务任务如实标注未知。

最终文件完整性、链接、证据定位、原文件哈希和 12 问自测的具体结果，以 [本轮任务档案](TASKS/COMPLETED/2026-10-29-project-memory-bootstrap.md) 为准。文档检查不等于应用测试；没有运行 Flask、HTTP 请求、转换、声音／视频播放、WebView、离线运行或 EXE 构建，未验证跨机器迁移。

## 遗留风险和未知

- `KI-001`：转换未检查 FFmpeg 退出码、无流目录直接返回等终态风险。
- `KI-002`／`KI-003`：列表不重绘、滚动日志和重复完成日志的静态缺陷。
- 其他切库／路径、依赖和本地工具分发、预览资源清理、输入与 DOM 风险见 [KNOWN_ISSUES.md](KNOWN_ISSUES.md)。全部未在本轮运行复现，不当作上一轮用户报告的 Bug。
- 没有已提供的历史未完成功能清单、真实素材样例、环境版本矩阵或功能路线图；这些保持待确认。

## 新 AI 的具体下一步

1. 读取根入口及核心文档；只据本轮任务档案理解初始化结果，不依赖旧聊天或账号记忆。
2. 只读检查 `git status --short --branch`、`git log -5 --oneline` 和必要 diff，核对用户是否已提交文档、有无新修改；保留全部原有文件。
3. 按架构检查 Python 依赖及项目 `bin/` 工具是否齐备，不直接执行会安装的 bat；从仓库根目录启动的说明只是已整理的操作路线，不是本轮运行成功证据。
4. 如果仅询问项目，直接依据文档和代码回答，无需改文件。若提出开发，先确认需求／验收并分析影响，提出新功能方案等待用户确认，复杂任务写入 ACTIVE。
5. 用户尚未选下一任务时，可建议先用隔离素材建立运行基线，再讨论 `KI-001` 等正确性问题的优先级；不要直接开始修复。
6. 获准修改后做必要验证，执行根入口维护规则。Git 保存一律由用户在 GitKraken 手动进行。

## 可复制的接手提示词

> 请接手当前 SteamClipExporter 项目。先读取根目录 AGENTS.md，并依次读取 AGENTS/INDEX.md、PROJECT.md、REQUIREMENTS.md、CURRENT_STATE.md、HANDOFF.md，再按任务读取相关文档和实际代码。先只读检查 Git 状态与最近提交，简要总结项目用途、启动前提、现有进度、未提交修改、风险和建议下一步；区分用户确认需求、代码事实、静态风险与待确认内容。不要假设知道旧聊天，不自动修复已知问题。新功能先提出方案等待我确认。不要自动安装、升级、重构或执行 Git 暂存、commit、push、reset、rebase 等操作；Git 由我使用 GitKraken 管理。实际修改后更新受影响的记忆和交接文件；只读提问不改文件。
