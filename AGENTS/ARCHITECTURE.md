# 整体架构与启动

## 2026-11-06 增量

新增 `backend/metadata.py`，由悬停 HTTP 请求按需调用，不进入导出队列；系统临时目录保存 init＋首尾视频片段样本，FFprobe 退出后清理，不改源素材。前端按库／cid 缓存，扫描时失效。`PREVIOUS_TASK_SECONDS` 与现有任务状态共同提供进程内累计用时，无新依赖或持久化。

依据：`main.py`、`backend/app.py`、`backend/worker.py`、`frontend/`、`build.py`、`run_server.bat`；基线见 [CURRENT_STATE.md](CURRENT_STATE.md)。下述为源码事实，运行成功与否见交接验证记录。

## 技术栈及组件

| 层次 | 实际技术／依赖 | 依据与边界 |
| --- | --- | --- |
| 界面 | HTML、CSS、原生 JavaScript、HTML video | `frontend/index.html`、`script.js`、`style.css`；未发现 npm 工程或前端构建配置 |
| 浏览器库 | Axios、Chart.js | HTML 从 jsDelivr 加载，URL 未锁定版本；离线可用性未验证 |
| HTTP 服务 | Python、Flask、flask-cors | `backend/app.py`，`CORS(app)`；同服务提供静态资源及 JSON／媒体接口 |
| 桌面壳 | pywebview（导入名 `webview`） | `main.py` 创建原生窗口，并注入 `WEBVIEW_WINDOW` |
| 任务执行 | `threading`、`queue.Queue`、全局字典 | 模块导入时创建单个 daemon worker；串行导出 |
| 媒体处理 | 外部 `ffmpeg.exe`、`ffprobe.exe` | `subprocess` 调用，项目 `bin/` 或打包资源目录定位 |
| 打包 | PyInstaller | `build.py` 构建单文件窗口应用并打包前后端、bin、图标 |

未发现 `requirements.txt`、`pyproject.toml`、依赖锁文件或 CI。`tests/` 新增标准库 unittest 和 Node 内置行为测试，媒体回归依赖本地 bin 工具；不需要安装测试框架。支持的最低 Python 和依赖版本未声明；已有 `.cpython-312.pyc` 不是兼容性声明。初始化核对使用 Python 3.12.2，不代表最低要求。

```mermaid
flowchart LR
    U[用户] --> UI[原生 Web 前端]
    WV[pywebview 桌面窗口] --> UI
    CDN[jsDelivr: Axios / Chart.js] --> UI
    UI -->|本地 HTTP| F[Flask 静态资源与 API]
    F -->|目录选择| WV
    F --> Q[内存队列与状态]
    Q --> W[单个后台 worker]
    W --> T[FFmpeg / FFprobe 子进程]
    F -->|缩略图与预览| T
    F --> FS[本地素材目录]
    T --> FS
    T --> OUT[导出目录 MP4]
    F -->|进度与日志 JSON| UI
```

## 三种入口及前提

以下命令为接手说明，本轮没有启动服务、构建或安装依赖。均从项目根目录运行，先确保所需 Python 包和本地工具已准备好。

1. **桌面方式**：`python main.py`。导入 `backend.app`（此时启动 worker），新建 daemon 线程在 `127.0.0.1:5000` 启动 Flask（`debug=False`、`threaded=True`），创建 `1650×1000` 的 pywebview 窗口并加载该地址；将窗口写入 `app.config['WEBVIEW_WINDOW']`，进入 WebView 事件循环。有图标则传入 `app_icon.ico`。WebView 对系统运行时的要求未验证。
2. **浏览器方式**：已有依赖时可运行 `python -m flask --app backend.app run --host 127.0.0.1 --port 5000`，再打开 `http://127.0.0.1:5000/`。这是根据 Flask app 对象与既有 bat 整理的显式等价启动命令，未实跑。`run_server.bat` 设置 `FLASK_APP=backend.app` 后执行 `python -m flask run`；它会先尝试 pip 安装 Flask、flask-cors，并检查 PATH 中的 FFmpeg。**bat 有安装副作用，本轮未运行。** `backend/app.py` 仍顶层导入 `webview`，bat 未安装 pywebview。纯浏览器方式无 `WEBVIEW_WINDOW`，原生选目录接口返回失败，应手填路径。
3. **EXE 构建**：准备 PyInstaller 及运行依赖后 `python build.py`，目标 `dist/SteamConverterPro.exe`。包含 `backend/`、`frontend/`、`bin/`、图标，收集 webview、flask、flask_cors；结束时 `finally` 清理 `build/` 和对应 `.spec`。构建本身有文件写入／清理副作用，需属于获准任务；本轮未运行。不存在本轮可验证的现成 `dist/` 产物。

端口占用、服务线程就绪与窗口加载时序未实际验证。不要承诺三种入口行为完全一致。

## 路径、配置和存储

- `get_res_path()` 以 `sys._MEIPASS` 或 `backend/app.py` 的父级项目目录定位前端资源。
- `get_ffmpeg_tool()` 以 `sys._MEIPASS` 或**当前工作目录**定位 `bin/<name>`；`main.py` 的图标定位和 `build.py` 也依赖工作目录。因此源码运行应从根目录启动，不能只依赖系统 PATH。
- 输入素材路径、导出路径由 `/api/set_path` 设置；新增 `/api/set_export_path` 独立更改导出目录。前端路径提交串行，入队前再次等待导出目录校验。没有配置文件、环境变量配置层或数据库。bat 的 `FLASK_APP` 仅用于选 Flask 应用。
- `CURRENT_CLIP_PATH`、`EXPORT_PATH`、`CONVERSION_STATUS`、`CONVERSION_QUEUE`、`PYTHON_LOGS` 全部为单进程内存；重启丢失，不应配置多进程并假定共享状态。
- 持久数据是原素材、`gamename.txt`、素材库根目录的 `<cid>.jpg`、导出目录的 `<cid>.mp4`。导出临时 `.v`、`.a` 位于输出旁；预览临时 MP4 位于系统临时目录；缩略临时文件为 `<cid>.jpg.tmp.mp4`。

## 素材布局和转换约束

```text
素材库/                       # 或输入目录下的 clips/
  clip_<字段>_<YYYYMMDD>_<HHMMSS>/
    gamename.txt              # 可选，UTF-8，覆盖默认 AppID 展示名
    video/
      fg_*/                   # 当前只使用 glob 找到的第一个目录
        init-stream0.m4s
        chunk-stream0-*.m4s   # 按文件名字典排序
        init-stream1.m4s      # 可选音频
        chunk-stream1-*.m4s
  <cid>.jpg                   # 扫描时可能生成
导出目录/
  <cid>.mp4
```

这里是代码期待的格式，不是全部 Steam 格式规范；目录中第二字段被代码用作 `AppID` 展示，不应误写为已验证的用户 SteamID。

导出拼接 init 与 chunks 后调用 FFmpeg `-c copy`，有 stream1 时在音频输入前使用 `-isync 0` 以视频输入起点为参考，保留两路相对偏移；输出端 `-avoid_negative_ts make_zero` 对所有轨道统一平移。合成分段已验证音频早／晚、B 帧、大时间戳、无音轨及进度；真实 Steam 素材仍待验收。本地 FFmpeg 8.0.1 支持该参数，替换旧工具时需核实。无用户可选编码和格式配置。预览单独走 stream0 前 10 段的 H.264 流式转换，不等同完整导出，也没有 Range／定位处理。缺片段、多个 `fg_*`、损坏数据和输出覆盖等风险统一见 [KNOWN_ISSUES.md](KNOWN_ISSUES.md)。

2026-10-30 导出进度按阶段发布，两轨 chunk 分别计数，拼接按总字节估算，封装按 FFprobe 时长及 FFmpeg 媒体时间估算；未知时长不定显示，成功前不达 100%。仍使用原 `/api/progress`，字段见 [API.md](API.md)。完成检查退出码及非空文件，清理警告单独展示；未增加恢复／持久化或改变输出覆盖规则。

现有 README 声称添加 FFmpeg 至 PATH，但当前代码直接调用 `bin/` 中的 exe，且 bat 的依赖安装不完整。本轮保留原文，通过本文件说明差异；未来变更需独立授权。

任务监控复用 Chart.js，无新依赖；`backend/telemetry.py` 随 `/api/progress` 下发有界区间历史，重启丢失。图表背景改为 #252525，视频／音频／封装三阶段连续排列，读取时长等待不占横轴；真实总用时不变。柱形仅为文件写入 MB/s；折线分别为视频片段 个/s、音频片段 个/s、封装 x，init 不计片段。阶段按钮仅高亮，再点取消，任务选择与跟随保留。每阶段最多 600 个区间；超限按相邻区间用时加权合并，保留完整时间范围但较早峰值变为均值。Point 增加 dt/write_mbps，t 仍为真实任务秒数；图表按 dt 累加省略等待。MB/s、个/s、x 分轴，不归一化，高亮不改刻度。拼接按实际写入字节和完整 chunk 差值采样；封装使用 FFmpeg total_size，缺失时只读输出文件大小，不再查询 Windows 进程总 I/O。写入可能含系统缓存，不等于物理落盘速率；未知为 null。 报告四步、内部分段校验与清理保留。

最新前端展示修订（后端采样不变）：用户确认上方柱形、下方折线共用连续处理时间；柱形固定 3 CSS px，不随采样 dt 变宽，删除 intervalBars 插件。下方个/s（左）与封装 x（右）刻度从零向下增加，MB/s 在上图独立显示。getMonitorSeries() 根据可用宽度按每阶段等时间窗口重采样，按覆盖时长加权平均；每个有数据阶段至少一柱，未知值保留 null，完整处理时间范围保留。两图左右轴各固定 48 px 对齐；横向直接更新，纵向／颜色短过渡，减少动态效果偏好关闭动画。 详见 [上下分图与固定细柱](TASKS/COMPLETED/2026-10-30-split-fixed-bars.md)。

上下图贴合补充：中间时间文字／刻度及单位行隐藏，零刻度不显示文字；单位集中在顶部，时间仍由悬停提示提供。上下绘图容器贴合，共同时间范围和固定轴留白不变。此次修改发生在 v2.3 归档之后。

阶段交互最新修订：点击阶段标签放大该阶段，上下图同时只展示该阶段并铺满绘图区，纵轴按所选数据自动调整；再次点击返回全程，点击其他标签切换阶段。保持 3 px 固定柱宽、原始单位和真实处理时间提示，无归一化。无数据阶段禁用，切换任务／恢复跟随／重排队无历史时退出放大。 getMonitorSeries() 按 focusedPhase 返回显示数据和视区边界，上下图同步；后端采样／API 不变。该实现发生在 v2.4 捕获之后；v2.3 已按用户要求删除。
