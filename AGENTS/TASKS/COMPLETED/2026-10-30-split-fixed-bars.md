# 上下分图与固定柱宽

## 用户授权与范围

2026-10-30 用户要求处理第三阶段小方块，确认柱状图在横轴上方、折线在下方，并要求模仿 Steam 的固定柱宽动效，明确“开始执行”。延续自己试用审核、不安排 agent／自动化回归偏好。

基于 v2.2 后工作区继续，main、HEAD 61bdb5f；已有业务／记忆／快照及两项运行后 pyc 改动全部保留。不安装、不改 Git、不覆盖快照，不改媒体处理。

## 排查证据及设计

- 旧 intervalBars 插件把 dt 转为柱宽；长采样低写入可显示为宽矮方块。截图的原始数据未取到：首次沙箱 socket 被拒绝，授权只读重试后本机 5000 端口连接拒绝，未启动服务／导出。不能确认截图那一点的具体采样值。
- 删除按 dt 撑宽插件；所有柱宽固定 3 CSS px、inflateAmount=0，不把低速点删除或置零。前端按可用宽度将每阶段 dt 历史重采样为等时间窗口，按区间覆盖时长平均；每阶段至少一个窗口，完整时间范围和蓝绿橙保留。
- 两个 Chart.js canvas 共享线性处理时间范围；上图柱形 MB/s 从中间时间轴向上，下图片段 个/s（左）／封装 x（右）从零向下；左右留白一致使横轴对齐。不同单位不归一化。
- 横向定位直接更新，纵向数值／颜色短过渡，减弱动态选项时关闭动效；固定柱宽不随 dt、任务长度改变。阶段高亮与任务切换／跟随保留。

## 实施计划

使用 writing-plans／executing-plans 技能，在当前会话连续实施已授权方案。

- [x] frontend/script.js：getMonitorSeries() 时长加权重采样；initChart() 两图固定轴边距及固定柱宽；refreshTaskMonitor() 同步时间范围和高亮，窗口改变时重新计算容量。
- [x] frontend/index.html、style.css：上下两个绘图容器、中央时间标注、单位说明及灰黑背景。
- [x] Python AST／node --check／git diff --check，静态审查空任务、短阶段、未知值、长区间和任务切换；不运行应用／UI／媒体或回归。
- [x] 更新受影响需求、模块、架构、API（前端展示）、决策、学习、CURRENT_STATE、HANDOFF、CHANGELOG，移入 COMPLETED。

## 验收边界

用户重启源码应用试用新任务，检查上下方向、时间对齐、固定细柱、短阶段、窗口变化、高亮及跟随。旧内存历史可重新显示，但不恢复已丢失的细节。写入含缓存，重采样为均值。截图具体小块的数值根因未证实；本次处理确定存在的可变柱宽机制，不凭推断改后端速率。

## 完成与验证

- 本轮实施完成：仅 frontend/script.js、index.html、style.css 及受影响记忆；既有修改全部保留，未覆盖 v2.1／v2.2，未进行 Git 写操作或安装。
- `node --check frontend/script.js` 退出码 0；`git -c core.fsmonitor=false diff --check` 退出码 0，无输出。
- HTMLParser 静态检查：chart／speed-chart／monitor-empty／monitor-speed-label 均存在，全部 HTML ID 无重复。
- 以 v2.2 manifest 逐文件 SHA-256 核对 backend 下所有文件（含 pyc）均一致；Python 源码 AST 解析通过，后端无本轮新增改动。
- 逐项阅读前端相对 v2.2 的 diff，确认取消 intervalBars、固定 barThickness/maxBarThickness=3、inflateAmount=0、两个 canvas 的共同 x 范围／固定左右留白、下图 reverse=true、未知值不伪造、阶段／任务选择保留。
- 未运行：自动化回归、UI／动效／真实素材导出／EXE。短阶段、窗口改变、轴像素对齐及方块视觉效果由用户重启源码应用试用验收。本次不声称截图原点的数值根因已确定。
- 状态：实现与静态核对完成，待用户试用审核；无新命名快照。
