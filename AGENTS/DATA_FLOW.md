# 数据流与运行流程

依据当前实现；已运行隔离合成分段及 test client，未运行真实 Steam 素材。接口字段以 [API.md](API.md) 为准，故障与限制见 [KNOWN_ISSUES.md](KNOWN_ISSUES.md)。

## 1．配置路径、扫描并展示

```mermaid
sequenceDiagram
    actor U as 用户
    participant UI as script.js
    participant API as Flask app.py
    participant W as worker.py
    participant FS as 文件系统
    U->>UI: 输入素材／导出路径并扫描
    UI->>API: POST /api/set_path
    API->>FS: 验证目录并检查 clips 子目录
    API-->>UI: success / message
    UI->>API: GET /api/clips
    API->>FS: 枚举 clip_*，读取时间与 gamename.txt
    opt 缺少 JPG
        API->>W: generate_quick_thumb()
        W->>FS: 写临时 MP4，调用 FFmpeg 生成 JPG并清理临时文件
    end
    API->>FS: 检查导出 MP4 是否存在
    API-->>UI: clips 数组
    UI->>UI: allClips 更新，renderList() 按视图排序／分组
    UI->>UI: 首次设置路径后开启 1 秒 tick()
```

`setP()` 不 await `load(true)`；扫描与轮询可能交错。列表接口在 HTTP 请求线程内同步生成缩略图，不是由转换队列生成。导出选择器成功或手填 `change` → `setExportPath()` → `POST /api/set_export_path`，独立设置后端导出目录，再 `load(true)` 刷新标记、清除已导出／消失项的选择；无需重新点击扫描。`submitPaths()` 把路径设置及其刷新／入队回调作为完整串行操作。

## 2．选择、排队、导出、显示进度

```mermaid
sequenceDiagram
    actor U as 用户
    participant UI as script.js
    participant API as Flask app.py
    participant Q as CONVERSION_QUEUE
    participant W as worker_thread / convert_clip
    participant FF as FFprobe / FFmpeg
    participant FS as 文件系统
    U->>UI: 点击卡片底部或全选未导出
    UI->>UI: 更新有序 sel 数组
    U->>UI: 批量转换所选素材
    UI->>API: POST /api/set_export_path，等待配置成功
    API-->>UI: success / 400，无效则停止入队
    UI->>API: GET /api/clips，刷新标记并过滤选择，失败停止入队
    UI->>API: POST /api/queue，clip_ids = sel
    API->>API: 跳过 pending/running，设置 pending
    API->>Q: 写入素材路径、输出路径、cid
    API-->>UI: success true
    UI->>UI: 清空 sel，调用 load()
    Q->>W: 单 worker 按 FIFO 取任务
    W->>W: 标记 running
    W->>FS: 拼接 stream0 到 .v，可选 stream1 到 .a
    W->>FF: FFprobe 获取视频时长
    W->>FF: 音频输入 -isync 0，-c copy，输出端 make_zero 统一平移，输出 MP4及进度
    FF-->>W: out_time_ms 等输出行
    W->>W: 更新共享 progress / eta / last_raw_log
    loop 每秒
        UI->>API: GET /api/progress
        API-->>UI: all_statuses / py_logs
        UI->>UI: 更新任务卡、进度条、图表和日志
    end
    W->>W: 当前代码在进程结束后标记 finished
    W->>FS: finally 清理 .v 和 .a
    UI->>API: 看到 finished 后调用 load()
    API-->>UI: 更新 is_converted 等字段
```

上图描述当前调用链，**不保证进程退出意味着转换成功**：当前未检查返回码。`load()` 仅在显式 verbose 或数量变化时重绘，完成后状态可能不反映到卡片；问题详情由 `KI-001`、`KI-002` 维护。

转换时使用入队时已捕获的完整路径；共享状态只按 cid 索引。中途切换素材库时，任务仍运行原路径，但新素材库可能和旧库 cid 冲突，详见 `KI-004`。

## 3．短预览和关闭播放器

用户悬停素材图片 800ms → `createClipEl()` 创建静音循环 video，或点击图片 → `openPlayer()` 打开弹层 → video 请求 `/api/stream/<cid>` → `stream_clip()` 找第一个 `video/fg_*` → 在系统临时 MP4 拼接 stream0 init 与前 10 个 chunk → 启动 FFmpeg H.264 分片 MP4 输出到 stdout → Flask `Response` 流 → video 播放。

离开悬停会清空预览容器；关闭弹层时 `closePlayer()` 暂停、移除 src 并 `load()`。服务端从创建临时文件起进入 try/finally：正常结束、断开或拼接／启动失败均进入清理。若进程仍运行，先 terminate；wait 最多 3 秒，超时后 kill 并再次 wait 最多 3 秒；关闭 stdout 后才删除本请求临时文件，防止 Windows 输入文件锁尚未释放。清理失败记 warning，不遮蔽原错误；外部占用或应用被强杀仍可能残留，见 `KI-008`。预览未读取 stream1，也不是对已导出的 MP4 做播放。

## 数据生命周期

| 数据 | 保存位置 | 生命周期／重启行为 |
| --- | --- | --- |
| `sel`、`allClips`、视图、前端日志索引 | 浏览器内存 | 页面刷新重建 |
| 路径、队列、任务状态、最近 100 条后端日志 | Python 进程内存 | 进程停止即丢失 |
| 素材分段、游戏名文本 | 本地素材目录 | 本轮不修改；运行扫描会在素材库根额外写缩略文件 |
| 缩略 JPG、导出 MP4 | 素材库／导出目录 | 跨进程保留；输出仅按存在与否识别 |
| 临时媒体文件 | 输出旁／素材库旁／系统临时目录 | 正常路径尝试清理，异常或进程退出可能残留 |

不存在已发现的云同步、后台恢复或持久任务数据库。记忆 Markdown 保存的是项目知识与进度，不会使应用自身的运行队列持久化。
