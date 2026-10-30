# 连续写入速度与片段处理图表

后续显示方式已由用户确认修订为 [上下分图与固定细柱](2026-10-30-split-fixed-bars.md)；本档案记录 v2.2 捕获前的实施，采样语义仍保留。

> 执行方式：superpowers:executing-plans，当前会话直接实施。用户已确认方案并要求“开始改吧”；沿用不安排 agent／自动化回归、用户试用审核的偏好。Git 仅只读。

## 目标与已确认设计

- 基于命名快照 v2.1 开发，不覆盖 SNAPSHOTS；开始时 main、HEAD 61bdb5f，工作区干净。
- 图表背景 #252525，三阶段蓝绿橙连续排列，读取时长等待不占图表横轴；真实总用时不变。
- 三阶段柱形均为目标文件写入 MB/s；视频／音频折线分别为完整 chunk 个/s，init 不计；封装折线为 FFmpeg x。
- 阶段按钮仅高亮，重复点击取消；不切图、不改变数据与刻度。任务选择及跟随保留。
- 已选方案：延续 Chart.js，后端记录区间 dt 并保留完整时间范围；每阶段超过 600 点时合并相邻区间，速率按时长加权平均，保留较早历史。相比无限保存原始点控制内存及轮询成本，相比旧 120 点窗口不会丢弃开头。长任务图是区间均值，非每个瞬时峰值。
- 左轴 MB/s，右侧片段 个/s 与封装 x 明确分轴，不归一化。写入计数可能含系统缓存，非物理落盘速度。

## 实施计划

**Goal:** 三阶段连续图展示写入和处理速度，保留完整阶段历史及真实总用时。
**Architecture:** telemetry 采集区间、累计写入与完整片段差值；worker 供应写入和片段计数，FFmpeg total_size 供应输出字节；前端按 dt 累加绘制压缩后的处理时间。
**Tech Stack:** Python 标准库、原生 JS/CSS、现有 Chart.js。
**Spec:** 本任务“目标与已确认设计”（最后一次方案已由用户确认；600 点聚合为实施选择）。

### Task 1：采样与连续图表

涉及 backend/telemetry.py、backend/worker.py、frontend/script.js、frontend/index.html、frontend/style.css。

- [x] TaskMonitor.record(processed_bytes=0, completed_chunks=0, output_bytes=None, speed=None, force=False)：生成 t/dt/disk_mbps/speed；disk_mbps 为兼容字段，现表示仅写入；新增 write_mbps 别名。speed 拼接为个/s，封装为 x。保留完整范围，每阶段最多 600 点，相邻区间按 dt 加权合并。
- [x] worker 在完整 chunk 后更新计数并采样，封装解析 total_size，缺失时只读输出文件大小；不改 FFmpeg 媒体参数、队列、路径与清理。
- [x] 前端线性处理秒轴、区间宽度柱形、三色阶段折线；MB/s／个/s／x 各自零起点原始刻度。按钮只改变强调色，空值保持未知，无音轨不生成假数据。
- [x] 灰黑背景及指标／坐标／提示文案同步，说明横轴省略等待、写入含缓存。

### Task 2：静态核对与记忆维护

- [x] Python AST、node --check、git diff --check；检查采样末尾、无音轨、未知写入、长任务聚合、失败已有数据及高亮不重设轴的实现分支。不运行应用或自动化回归。
- [x] 更新受影响需求、API、架构、模块、决策、学习说明、CURRENT_STATE、HANDOFF、CHANGELOG。完成档案移至 COMPLETED，交代未运行验收。

## 验收与风险

用户重启源码应用创建新任务，检查连续三色图、无音轨、阶段高亮、MB/s／个/s／x 单位、总用时包含等待。旧内存采样不兼容新语义，需重启；未运行 UI／真实媒体／EXE，所有运行验收待用户试用。

## 完成记录与验证证据

- 5 个源码文件完成修改，更新受影响记忆；媒体命令参数、队列、输出目录与清理保持原流程。无 Git 写操作、依赖安装、缓存生成或 SNAPSHOTS 修改。
- 实施补充：阶段末尾不足 0.5 秒的采样与上一段合并，避免片段完成计数除以极短时间产生尖峰；封装 progress 批次重置速度，缺失数据不沿用上一批次速度。
- 验证：`python -B` 读取并 ast.parse backend/telemetry.py、backend/worker.py，均输出 AST OK；`node --check frontend/script.js` 退出码 0；`git -c core.fsmonitor=false diff --check` 退出码 0，无输出。已检查实际源码 diff 与 Git 文件清单。
- 未执行：自动化回归、应用启动、界面视觉验收、真实媒体及 EXE；遵照用户既有试用审核偏好，不把静态核对称为运行通过。
- 完成状态：实施及静态核对完成，待用户重启源码应用用新任务试用。原 v2.1 归档保留，当前改动未另建命名快照。
