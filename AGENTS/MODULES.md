# 模块与代码地图

路径均相对项目根目录，链接可定位文件；优先在 IDE 搜索函数名。当前源码很小，未分出服务层或数据访问层，不应描述为已有这些架构层。

| 文件 | 职责与关键入口 | 调用／依赖 |
| --- | --- | --- |
| [main.py](../main.py) | 桌面入口；`get_base_path()`、`start_flask()`；创建 WebView 并配置窗口对象 | 导入 `backend.app.app`，启动 Flask 线程、pywebview 主循环 |
| [backend/app.py](../backend/app.py) | Flask、静态页面、全部业务路由、内存状态和后台 worker | 直接调用文件系统、WebView、worker 的媒体函数 |
| [backend/worker.py](../backend/worker.py) | 媒体工具定位、分段拼接、缩略图和导出进度 | `subprocess` 调用项目内 FFmpeg、FFprobe |
| [backend/__init__.py](../backend/__init__.py) | 空包入口 | 允许 `backend.app` 导入 |
| [frontend/index.html](../frontend/index.html) | 页面结构、按钮事件、日志面板、图表、视频弹层 | CDN Axios／Chart.js，本地 CSS／JS |
| [frontend/script.js](../frontend/script.js) | 路径操作、选择、分组渲染、队列提交、轮询和播放 | Axios 调 Flask，Chart.js 画图，HTML video 播放流 |
| [frontend/style.css](../frontend/style.css) | 深色布局、素材卡片、游戏专辑、日志与播放器样式 | HTML 类名，含固定侧栏和最小网格宽度 |
| [build.py](../build.py) | PyInstaller 打包及清理中间产物 | 依赖根目录资源和 pywebview／Flask 包 |
| [run_server.bat](../run_server.bat) | 检查 Python／PATH FFmpeg，尝试安装部分依赖，启动 Flask CLI | 有安装副作用；与实际依赖／工具定位不完全一致 |
| [README.md](../README.md) | 原始用途与三种使用方式 | 保留原信息，差异见架构与已知问题 |
| [tests/test_export.py](../tests/test_export.py)、[tests/frontend.test.js](../tests/frontend.test.js) | 导出路径 API／交互、FFmpeg 合成分段逐包时间轴回归 | Python unittest、Flask test client、Node 内置测试器；无新增测试框架 |
| [tests/test_preview.py](../tests/test_preview.py) | 预览资源生命周期、Windows 文件锁及目录选择器弃用／兼容回归 | 模拟外部进程退出时序，真实文件句柄与 Flask Response 关闭 |
| [tests/test_progress.py](../tests/test_progress.py) | 导出阶段、分段计数、媒体时间／速度、失败终态与清理警告 | 隔离文件＋外部进程边界替身；真实媒体由 test_export 回归 |
| `bin/`、`app_icon.ico` | 媒体可执行文件／压缩包、桌面图标 | exe 是否随版本保存见交接；不执行未知二进制进行文档核对 |
| `backend/__pycache__/`、`.idea/` | Python 缓存、IDE 配置 | 部分已纳入 Git，非业务源码；本轮不清理 |

## 后端关键函数与状态

- `app.py:get_res_path()`：源码／打包资源定位。
- `add_py_log()`：保留最近 100 条 Python 日志。
- `worker_thread()`：导入模块时启动，取队列、置 `running`、调用 `convert_clip()`、按终态写成功／错误／清理警告日志、`task_done()`；单个串行 worker。
- `index()`、`select_folder()`、`open_folder()`：首页和桌面／资源管理器能力。
- `set_p()`：设置素材与导出目录；`set_export_path()`：独立更新导出目录并拒绝无效路径；`list_c()`：扫描目录、解析时间和游戏名、按需生成缩略图、判断输出存在。
- `get_thumb()`：读取 JPG；`stream_clip()` 及内部 `generate()`：短预览拼接与 FFmpeg stdout 流，外层 finally 覆盖创建失败／断开清理，等待进程退出后关闭管道并删除临时文件。
- `add_q()`：按数组顺序入队，跳过已 `pending/running` 的同 cid；`get_prog()`：状态及日志快照。
- `worker.py:get_ffmpeg_tool()`、`get_hide_config()`：定位 exe 和 Windows 子进程隐藏窗口配置。
- `get_video_duration()`：FFprobe 查询时长，失败回退 0。
- `generate_quick_thumb()`：init 加首段生成 JPG，最后清理缩略临时文件。
- `convert_clip()`：检查并以 1MiB 块拼接两轨，完整 chunk 独立计数；保留 `-isync 0`／`-avoid_negative_ts make_zero` 同步参数与流复制，按阶段报告进度，解析媒体时间／速度，核对退出码／非空输出，等待进程退出后清理本任务 `.v/.a`。FFprobe 保留，无断点恢复。

## 前端关键入口

- 初始化：`DOMContentLoaded → initChart()`，此时不自动扫描。
- 路径：`browse()`、`openExportDir()`、`setP()`；`submitPaths()` 串行提交路径请求；`setExportPath()` 在导出选择／手填更改时独立提交并刷新标记；`setP()` 成功后 `load(true)` 并首次启动 1 秒 `tick()` 定时器。
- 列表：`load()` 请求数据，`toggleView()` 切换平铺／分类；`renderList()` 按 `viewMode/currentAlbum` 渲染；`createClipEl()` 绑定预览和底部选择；`selectAll()` 操作 `sel`。
- 队列：`addQ()` 捕获点击时的选择，将配置、列表刷新和有效选择入队作为同一串行操作；失败保留选择，成功移除已入队项。`load()` 会清除已导出／已消失的选择。`tick()` 更新任务卡、图表及三类日志，完成后触发 `load()`。
- 播放：`openPlayer()`、`closePlayer()`；悬停 800ms 创建静音循环 video，均使用 `/api/stream/<cid>`。
- 日志和时间：`log()`、`getFormattedTime()`、`formatDate()`；不要把前端时间戳误认为后端持久日志。
- 任务详情：`renderQueueProgress()` 通过文本节点显示阶段、两轨段数、错误／清理警告及估算进度；`formatMediaTime()` 格式化媒体秒数。未知时长使用不定进度条，旧响应仍可展示。

## 按功能定位修改入口

| 目标 | 先读／主要修改入口 | 必须评估的相邻影响 |
| --- | --- | --- |
| 扫描、目录识别、游戏名、时间 | `set_p()`、`list_c()`、`load()`、`renderList()` | API 字段、缩略写入、导出标记、排序 |
| 选择顺序、全选、分组 UI | `selectAll()`、`createClipEl()`、`addQ()` | `sel` 与显示排序差异、后端去重和串行顺序 |
| 导出正确性、进度、失败状态 | `convert_clip()`、`get_video_duration()`、`worker_thread()`、`tick()` | 临时文件、退出码、重排队、输出存在判定 |
| 缩略或播放器 | `generate_quick_thumb()`、`stream_clip()`、`openPlayer()`、`createClipEl()` | 媒体兼容、进程清理、并发、仅前 10 段 |
| 启动、工具路径、打包 | `main.py`、`get_res_path()`、`get_ffmpeg_tool()`、`build.py`、bat | 根目录启动、PyInstaller 资源、浏览器／桌面差异 |
| 记忆／交接 | 根入口及 INDEX 指定的主要维护文档 | 不把文档工作扩大为业务修复 |

新增功能前按需求与开发规范确认方案；本表只提供定位，不代表修改授权。
