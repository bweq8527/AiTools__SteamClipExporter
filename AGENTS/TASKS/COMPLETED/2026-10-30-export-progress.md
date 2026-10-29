# 导出阶段进度 Implementation Plan

> 执行方式：当前会话直接实现，使用 executing-plans、test-driven-development 和 verification-before-completion；结束前独立审查。用户已明确要求进行更改，不重复申请方案批准。遵守项目 GitKraken 约定，不创建分支或提交。

**Goal:** 显示导出各阶段、分别完成的视频／音频分段数和 FFmpeg 媒体处理进度。

**Architecture:** 保留 Flask、原生 JS、串行 worker 和既有音画同步命令；状态通过现有 `/api/progress` 增加字段。阶段详情作为主要依据，原 `progress` 保留为阶段加权估算，避免破坏图表。

**Tech Stack:** Python、Flask、原生 JavaScript、FFmpeg／FFprobe；无新增依赖。

**Spec:** 用户 2026-10-30 确认上轮阶段方案并要求实施：FFprobe 保留不动，重做阶段进度，断点继续暂不添加。

## 设计与约束

- 阶段：准备素材 → 拼接视频 → 拼接音频（无音轨明确跳过）→ 读取媒体时长 → FFmpeg 封装 → 收尾 → 完成；错误保留已完成段数。
- `.v/.a` 各一个文件；分段计数仅计完整复制的 chunk，init 不计段数；音视频各自统计。
- 状态增加 `stage`、`video_done/total`、`audio_done/total`、`has_audio`、`processed_seconds`、`duration_seconds`、`speed`、`progress_indeterminate`。旧 `status/progress/eta/last_raw_log` 兼容。
- 分段拼接按总字节映射至 0–40%；读取时长 40%；封装 40–98%；收尾 99%；成功才 100%。这是估算进度，不是剩余时间预测。
- 总时长不可用时显示未知并使用不定进度条，仍输出已处理时长和速度；FFprobe 函数与调用用途保留。
- 收尾等待 FFmpeg 退出、核对退出码及非空输出、清理本任务临时文件；不宣称完整解码验证。失败不能显示完成或写成功日志。
- 不实现恢复、队列持久化、旧 MP4 完整性扫描或临时输出发布机制；不改覆盖和命名规则；不改同步参数、不安装升级依赖。

## Review Focus

无音轨／两轨段数不同；时长未知及异常进度行；FFmpeg 非零退出或未产出文件；准备阶段缺素材；清理失败或进程异常时仍有准确终态。

## Task 1：后端阶段状态

涉及 `backend/worker.py`、`backend/app.py`、`tests/test_progress.py`、现有媒体回归。

- [x] 写行为测试并运行，证明旧实现缺少阶段、计数且会误报成功。
- [x] 在 `convert_clip(folder, out, status)` 发布上述字段，按复制字节和媒体时间更新；限制正常封装进度不超过 98%，完成前不显示 100%。
- [x] 调整 worker 日志依据终态；验证缺素材、失败退出、未知时长、清理错误。

## Task 2：前端消费状态

涉及 `frontend/script.js`、`frontend/style.css`、`frontend/index.html`、`tests/frontend.test.js`。

- [x] 先运行失败用例：轮询后卡片应保留两轨计数、显示当前阶段／处理时长／速度，未知时长不伪造百分比，失败不输出 DONE。
- [x] 用 DOM 文本节点展示阶段详情，保留旧响应回退；标注图表是估算进度。
- [x] 运行 Node 测试及语法检查。

## Task 3：验证与记忆维护

- [x] 运行 `python -B -m unittest discover -s tests -v`、`node --test tests/frontend.test.js`、JS／Python 语法检查；现有真实 FFmpeg 包时间轴回归必须通过。
- [x] 审查实际 diff，独立代码审查并处理重要发现；更新 CURRENT_STATE、HANDOFF、API、MODULES、DATA_FLOW、ARCHITECTURE、REQUIREMENTS、KNOWN_ISSUES、CHANGELOG 和必要学习说明。
- [x] 记录测试证据及未验证范围，任务移至 COMPLETED；Git 操作由用户进行。

## 执行记录

- 初始核对：`main`，HEAD `d1d022d`，工作区干净；旧快照哈希过时，未 fetch。用户确认进度功能，恢复功能延期。
- 后端新增 14 项行为回归：初始 9 项在旧实现得到 8 失败及 1 清理异常；改进后通过。worker 错误日志用旧分支单独验证失败后恢复修复；对齐空格、科学计数法速度分别先失败后修复。
- 前端旧 7 项保持通过，新增 4 项轮询显示测试先失败后通过，覆盖两轨计数、媒体时间／速度、无音轨、未知时长、错误阶段及旧响应。
- 最终命令：`python -B -m unittest discover -s tests -v` 30/30，无跳过；`node --test tests/frontend.test.js` 11/11；`node --check frontend/script.js`、Python AST 语法解析及 `git -c core.fsmonitor=false diff --check` 通过。真实 FFmpeg 回归验证原同步参数保留且输出可解码。
- 独立只读审查：发现 1 项 Important，真实 FFmpeg 输出 `speed=8.49e+03x` 被拒；已添加回归并支持有限非负指数值。其他无 Critical；补充部分复制失败保留计数、stdout 异常 terminate／超时 kill／wait 后清理回归。
- 界面视觉验证尝试：临时 Flask 仅监听 localhost，注入模拟状态，无真实素材；沙箱本地套接字受限，申请运行后浏览器仍超时并进入受 URL 策略限制的错误页，未取得页面截图，不能声称视觉验收通过。临时服务均已停止。
- 保留边界：真实 Steam 素材、长录像、桌面原生窗口、离线及 EXE 未验证；旧 MP4 仍仅按存在判定，失败残留风险未解决。没有断点继续、临时输出发布、队列持久化或完整解码校验。快速阶段可能被轮询跳过。
- 完成状态：实现、测试、审查及记忆维护完成，待用户重启源码应用做真实素材和视觉验收；未执行安装、升级或任何 Git 写操作。
