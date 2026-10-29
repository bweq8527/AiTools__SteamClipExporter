# 项目学习指南

目标：逐渐能解释代码为什么这样运行、定位问题、验证结果并独立维护。先读后画调用链，再做小范围练习；本文练习仅为建议，不代表获准修改当前业务。

## 建议阅读顺序

| 顺序／真实文件 | 重点知识 | 读完可尝试回答 |
| --- | --- | --- |
| 1．`README.md`、PROJECT、REQUIREMENTS | 问题、需求和实现的区别 | 用户要解决什么？哪些行为只是现状？ |
| 2．`main.py` | Python import、`__name__`、函数、线程、事件循环 | 为什么 Flask 在后台而 WebView 在主流程？导入 app 有什么副作用？ |
| 3．`frontend/index.html`、`style.css` | DOM、事件、类名、Flex/Grid、video | 图片点击与底部选择为什么是两个操作？样式从哪里来？ |
| 4．`script.js:setP/load/addQ/tick` | `async/await`、Promise、数组、状态、定时器、Axios | 一次点击发出哪些 HTTP 请求？数据变化何时重绘？ |
| 5．`app.py:set_p/list_c/add_q/get_prog` | Flask 路由、JSON、字典、全局状态、文件系统 | 前后端字段怎样对应？为什么 success 不代表转换完成？ |
| 6．`app.py:worker_thread`、`worker.py:convert_clip` | 生产者消费者、FIFO、异常、子进程、IO | 为什么一次只导出一个？何时设置 finished，依据可靠吗？ |
| 7．`worker.py` 其他工具函数、`app.py:stream_clip` | 媒体分段、流复制和转码、生成器、资源清理 | 为什么导出和预览不同？临时文件在哪里清理？ |
| 8．`build.py`、`run_server.bat` | 打包资源、工作目录、运行依赖、构建副作用 | 源码和 EXE 如何找 bin？为什么 PATH 说明不足？ |

阅读中配合 [MODULES.md](MODULES.md) 定位，[DATA_FLOW.md](DATA_FLOW.md) 看跨模块过程；不必一次理解全部代码。

## Python 学习重点

- 路径、字符串和集合：从 `list_c()` 的 `glob`、`split`、`datetime.strptime`、字典构造入手；注意代码变量名 `steam_id` 与实际用途可能不一致。
- 模块与执行环境：`backend/__init__.py`、相对项目资源、`sys._MEIPASS`、`os.path.abspath('.')`；理解包位置与当前工作目录不是一回事。
- 线程和共享状态：`queue.Queue()` 是生产者消费者队列，`CONVERSION_STATUS` 是共享字典；理解 daemon 退出、按 cid 索引和切库风险，不能把多线程等同多进程共享。
- 异常与清理：跟踪 `try/except/finally`，比较 `convert_clip()` 与预览生成器的覆盖范围；“没有抛异常”不一定成功。
- 子进程和生成器：`subprocess.run/Popen`、stdout／stderr、返回码、`yield`；用 `get_video_duration()` 与 `stream_clip()` 对照同步结果与流式响应。

## 前端、通信与架构知识

前端先掌握 HTML 结构、CSS 布局、DOM 创建／更新、事件冒泡与 `stopPropagation()`；然后观察 `sel`、`allClips`、`viewMode` 这几份状态如何决定界面。`load()` 更新数组不等于自动更新 DOM，这是理解 `KI-002` 的入口。

通信从 [API.md](API.md) 的一条 `/api/set_path` 开始：找前端 JSON、后端解析、HTTP 状态和响应使用。区分 HTTP 成功、任务入队和导出成功；理解 1 秒轮询如何代替推送，以及 `s.logged` 为什么不会跨响应保存。

架构方面，画出“前端 → HTTP 层 → 队列 → 媒体处理 → 文件系统”，再指出哪些数据只在内存、哪些落盘。桌面壳仍然通过本地 HTTP 显示界面；pywebview 不是后端 API 的替代品。模块职责、部署方式、依赖管理是不同问题，先理解现状再考虑重构。

## 调试和测试方法

1. 先写预期结果及可重复步骤，记录输入目录结构、入口方式和症状，使用隔离样例。
2. 查看 UI 的 FRONTEND／FFMPEG／后端日志，浏览器 DevTools Network 检查请求、响应和次数；有需要再在 IDE 对 `set_p()`、`add_q()`、`convert_clip()` 设断点。
3. 从最小调用链判断是界面未刷新、通信失败、状态错误还是媒体工具失败；参照已知问题的“静态证据／待复现”分类。
4. 单独确认进程返回码与输出文件可播放性，不只看进度 100。关注音轨、时长、错误和临时文件。
5. 清楚记录验证等级：语法检查、隔离逻辑测试、真实素材集成、桌面交互、EXE 构建互不替代。本轮仅静态核对，未运行这些业务场景。

## GitKraken 学习路线

理解工作区、暂存区、commit、分支、远端跟踪分支与 push 的区别。在 GitKraken 查看未提交文件 diff，按本轮范围选择文档暂存，再写有意义的提交说明；新建文档未提交就不会通过仅 Git 克隆转移。未跟踪的本地 exe 也不会自动进入历史。提交操作由用户手动完成，本文不要求 push 或更改当前分支。

## 可独立尝试的小练习

| 练习 | 对应位置 | 完成标准 |
| --- | --- | --- |
| 不改代码，画一次扫描请求的往返 | `setP()` → `set_p()` → `load()` → `list_c()` | 能解释空导出路径会发生什么，以及 JPG 写在哪里 |
| 手工演算三项素材的选中和提交顺序 | `selectAll()`、`sel`、`addQ()`、`add_q()` | 能区分卡片显示排序、全选数组顺序和 FIFO |
| 跟踪一个失败任务的状态变化 | `convert_clip()`、`worker_thread()` | 找出哪些返回路径不会正确反映成功／失败，先写复现方案 |
| 解释进度 15～99 的计算 | `get_video_duration()`、`out_time_ms` 解析 | 能说明单位换算、时长为 0 和完成置 100 的含义 |
| 解释日志为何可能停止或重复 | `add_py_log()`、`tick()` | 用纸面数组和索引推演，不必改代码 |
| 经用户选定后实现一个小修复 | 从 KNOWN_ISSUES 选一项 | 先需求和验收、方案确认、隔离验证、更新文档，GitKraken 手动提交 |

重要功能完成后，按实际改动增补一两个知识点和对应文件即可，不把学习指南扩展成通用教材。下一项练习或业务修复由用户选择。
