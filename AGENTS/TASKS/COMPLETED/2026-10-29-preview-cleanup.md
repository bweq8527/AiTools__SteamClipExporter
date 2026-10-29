# 预览临时文件占用与目录选择弃用警告

日期：2026-10-29。用户提供运行日志：目录选择触发 `FOLDER_DIALOG` 弃用警告；关闭预览的生成器在删除临时 MP4 时抛 Windows 文件占用错误。

## 范围与验收

- 现代 pywebview 使用 `FileDialog.FOLDER`，保留旧版本兼容分支，不安装或升级依赖。
- 预览正常结束、提前关闭或创建失败时，关闭自身句柄，先等待 FFmpeg 退出，再删除本请求的临时文件；终止超时则 kill 后等待。
- 删除仍被其他进程占用的文件时记录警告，不让清理异常逃出生成器。不得扫描或批量删除系统临时目录、杀死其他进程。
- 不改变预览前 10 段、无独立音轨和现有 API 契约；上次导出修复保留。

## 调查与方案

- HEAD 仍为 `b70cbc4`；上次修复尚未提交。用户运行后 `backend/__pycache__/app.cpython-312.pyc` 与 `worker.cpython-312.pyc` 已有修改，本任务保留这些缓存，不覆盖或回退。
- 当前 pywebview 为 6.1，安装源码确认 `FileDialog.FOLDER` 可用，旧别名在访问时记录弃用日志。
- 当前 `generate()` 仅在启动 FFmpeg 后进入 try/finally，且 `terminate()` 后立即删除，没有 wait，也没有关闭 stdout。临时文件创建和子进程启动失败亦可能漏清理。
- 修改仅限 `backend/app.py`，新增 `tests/test_preview.py` 与受影响记忆；采用外层资源生命周期保护，清理失败记录警告。

## 步骤与证据

- [x] 先写目录警告、文件占用、异常创建路径和超时终止回归，旧实现新增 9 项中 3 失败、4 错误、2 通过，实际复现 Windows 文件锁错误及弃用 warning。
- [x] 实施最小修复，Python 全套 16/16、Node 全套 7/7，语法检查通过。
- [x] 审查实际 diff，更新 CURRENT_STATE／HANDOFF、KI-008／013 及相关契约与流程；归档任务。

## 完成与验证

- 修改业务仅 `backend/app.py` 的目录选择和预览生命周期；新增 `tests/test_preview.py`。旧版 pywebview 条件回退，不提前求值弃用别名；不安装依赖。
- 回归使用真实文件句柄持有临时 MP4，模拟异步退出时序。先等待再删除可消除 Windows 文件锁；覆盖自然结束、提前关闭、终止超时后 kill、拼接／启动失败，以及外部删除失败仅记录 warning。
- 全套命令：`python -B -m unittest discover -s tests -v` 16/16，`node --test tests/frontend.test.js` 7/7，`node --check frontend/script.js` 通过。原导出时间轴及路径回归保留。
- 额外真实 FFmpeg 验证：隔离合成素材，Flask test client 连续 3 次提前关闭、1 次读取完整预览并解码到 null；每次自身进程已退出、stdout 已关闭、该请求临时文件已删除。
- 独立只读审查：`review_export_fixes` 未发现 Critical／Important。其测试兼容性建议经模拟旧模块确认：现代接口专用用例在旧版本会失败，已加明确 skip；现有现代版本仍实测无弃用日志，旧版分支仍执行兼容回归。模拟旧依赖后该现代专用用例跳过、无错误，不宣称真实旧版依赖已实装验证。
- 有界清理：最多两次 3 秒等待；若自身终止失败或外部仍占用，记录警告，保留文件。预览读取阻塞、媒体失败诊断、前 10 段及无独立音轨均为原有边界，不扩大本次修复。
- 完成状态：代码、隔离回归及真实 FFmpeg 生命周期验证完成；未操作原生目录窗口、未测真实 Steam 素材、未构建 EXE；用户重启后的交互验收待进行。原日志遗留文件未触碰，已有 pyc 修改保留，无 Git 写操作。
- 最终核对：7 个 Python 文件 AST、前端语法及 `git diff --check` 通过；19 份记忆 Markdown 的 70 个本地链接有效。测试结束后 Git 状态无隔离素材目录残留，原 app／worker pyc 修改仍保留。
