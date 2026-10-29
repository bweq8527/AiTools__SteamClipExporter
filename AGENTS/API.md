# 前后端通信契约

依据：`backend/app.py` 的路由装饰器及 `frontend/script.js` 的调用。服务默认本地 `http://127.0.0.1:5000`；前端使用相对 URL。普通数据经 Axios HTTP JSON 通信，图片／视频由浏览器直接请求。没有 WebSocket、SSE 或 pywebview JS bridge 的业务调用；原生目录选择由 HTTP 路由间接调用 WebView。

## 路由清单

GET 路由未显式设置 methods 时由 Flask 默认提供 GET（框架还处理 HEAD／OPTIONS）；不把它们列成额外业务接口。

| 方法／路径 | 后端函数 | 前端调用 | 请求／成功响应 | 已显式处理的失败 |
| --- | --- | --- | --- | --- |
| `GET /` | `index()` | 页面装载 | `index.html` | 文件缺失走框架错误 |
| `GET /api/select_folder` | `select_folder()` | `browse(targetId)` | 无参数；`{success:true,path:"<目录>"}` | 无窗口／取消：200 `{success:false,path:""}` |
| `POST /api/open_folder` | `open_folder()` | `openExportDir()` | JSON `{path:string}`；200 `{success:true}`，调用 `os.startfile()` | 路径不存在：400 `{success:false}`；系统调用异常无统一封装 |
| `POST /api/set_path` | `set_p()` | `setP()` | JSON `{path:string,export_path?:string}`；200 `{success:true,message:"目录配置成功"}` | 素材路径非目录：400 `{success:false,message:"无效的素材路径"}` |
| `POST /api/set_export_path` | `set_export_path()` | `setExportPath()`（选择、手填更改及入队前） | JSON `{export_path?:string}`；200 `{success:true,message:"导出目录配置成功",export_path:string或null}`；只更改导出目录 | 非对象 JSON、非字符串或非空无效目录：400 `{success:false,message:"无效的导出路径"}`；不改变已生效配置 |
| `GET /api/clips` | `list_c()` | `load()` | 无参数；200 `{clips:Clip[]}` | 未设路径／路径不存在：200 空数组；扫描异常记录日志并返回已收集数组，不一定有 HTTP 错误 |
| `GET /api/thumbnail/<cid>` | `get_thumb(cid)` | 卡片 `<img>` | JPG，`send_from_directory()` 读取素材库根下 `<cid>.jpg` | 未设路径：404 文本 `404`；文件缺失走 Flask 404 |
| `GET /api/stream/<cid>` | `stream_clip(cid)` | 弹层／悬停 `<video>` | `video/mp4` 的 FFmpeg stdout 流 | 未设路径：400 `Path not set`；无 `video/fg_*`：404 `Clip not found`；生成器内异常未统一封装 |
| `POST /api/queue` | `add_q()` | `addQ()` | JSON `{clip_ids:string[]}`；200 `{success:true}` | 缺字段默认空数组；未统一验证路径、类型、cid 或素材完整性；异常可能走框架错误 |
| `GET /api/progress` | `get_prog()` | `tick()`，路径设置后每秒调用 | 200 `{all_statuses:{[cid]:Status},py_logs:string[]}` | 无统一业务错误结构 |

Flask 同时通过静态目录提供 `/script.js`、`/style.css` 等资源；不是单独的前端服务。没有发现额外上传、删除、取消、重试、队列清空或配置保存接口。

## 参数与数据模型

`cid` 是素材目录名，通常为 `clip_<字段>_<日期>_<时间>`。目前没有 schema 验证；不能把通常格式写成已强制的约束。

`set_path` 会对两项字符串 `.strip()`，优先使用素材目录中的 `clips/` 子目录。`export_path` 为空或不是现有目录时回退到有效素材库，不创建目录；响应没有回传归一化后的实际路径。`openExportDir()` 使用输入框值或原素材输入值，可能与实际回退路径不同。路径相关风险见 `KI-004`、`KI-006`。

新增 `set_export_path` 不修改素材路径，也不移动已排队任务的输出路径。非空目录可先于素材扫描配置；空字符串回退至 `CURRENT_CLIP_PATH`，尚未配置素材时返回 null。新接口严格拒绝无效非空目录；原 `set_path` 的回退契约保留。前端将配置、刷新和入队作为同一串行操作，入队前过滤新目录中已导出／消失的项；配置或刷新失败均停止入队。手填 `change` 或选择器成功后强制刷新列表标记。

```json
{
  "clips": [{
    "id": "clip_APPID_20260101_120000",
    "game": "AppID APPID",
    "time": 1767240000,
    "is_converted": false,
    "thumb": "/api/thumbnail/clip_APPID_20260101_120000",
    "status": "idle"
  }]
}
```

这是**结构示例**，不是实测响应，示例时间值不表达目录与时区换算的契约。

| Clip 字段 | 类型／含义 |
| --- | --- |
| `id` | string；目录 basename |
| `game` | string；默认 `AppID <第二字段>`，有可读取非空 UTF-8 `gamename.txt` 时替换 |
| `time` | number；目录名解析的本机时间戳（秒），解析失败用目录修改时间 |
| `is_converted` | boolean；导出目录同名 MP4 是否存在，未验证可播放或完整 |
| `thumb` | string 或 null；仅 JPG 存在时提供 URL |
| `status` | string；当前 cid 内存状态，否则 `idle` |

`/api/progress` 初次入队状态示例：

```json
{
  "all_statuses": {
    "clip_APPID_20260101_120000": {
      "status": "pending",
      "progress": 0,
      "eta": "排队中"
    }
  },
  "py_logs": ["加入队列: clip_APPID_20260101_120000"]
}
```

| Status 字段 | 含义 |
| --- | --- |
| `status` | `pending` → `running` → `finished` 或 `error`；异常流程有静态风险，不保证总能到终态 |
| `progress` | 0 入队，准备 5、探测后 15，FFmpeg 时间映射至最多 99，结束置 100；异常时保留已有值 |
| `eta` | 展示文本，准备阶段／已处理秒数／完成或错误；不是可靠的剩余时间数字 |
| `last_raw_log` | 可选 string；最近 FFmpeg 输出行，stderr 已合并到 stdout |

`logged` 仅由前端在本次响应对象上设置，未传回后端，不是持久 API 字段。`py_logs` 是最多 100 条的滚动文本数组，无序列号和服务端时间戳；增量显示问题见 `KI-003`。

## 队列、预览与错误边界

- `clip_ids` 按请求数组顺序入队；相同 cid 已 `pending/running` 时跳过，但响应不列出逐项结果。已 `finished/error` 可再次入队；`success:true` 只代表请求执行，不代表转换成功。
- 悬停附带 `?type=preview`，弹层附带 `?t=<时间戳>`；后端不读取这两个查询参数，两种调用都只预览 stream0 前 10 段，不提供完整视频或音频拼接。没有 Range 请求的专门处理。
- 预览生成器从临时文件创建起保护资源；结束／关闭时等待自身 FFmpeg 退出（terminate，3 秒超时后 kill 再等待最多 3 秒），关闭 stdout，再删除本请求临时文件。清理错误记录 warning，原始拼接／启动错误仍按原契约传播。目录选择器优先用 `FileDialog.FOLDER`，旧版条件回退，不改变响应字段。
- API 默认无鉴权，启用 `CORS(app)`。不应据此扩展为对外服务。许多输入异常由 Flask 处理，具体 4xx／5xx 取决于异常和 Flask 版本，不承诺统一 JSON 错误。
- 前端多处空 `catch`，有些错误只显示通用日志，`openExportDir()` 未 await 请求。不能把“界面无提示”视为操作成功。
- 2026-10-29 已用 Flask test client 验证目录配置／入队、选择器参数／取消和预览清理；真实 FFmpeg 预览输出亦已解码核对。未启动真实 HTTP 服务或操作原生选择器。其他路由仍主要是静态契约核对。回归入口见 `tests/test_export.py`、`tests/test_preview.py`。
