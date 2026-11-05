let sel = [], chart = null, speedChart = null, pyIdx = 0;
let allClips = [];
let viewMode = 'flat';
let currentAlbum = null;
let pathUpdate = Promise.resolve();
let monitorStatuses = {}, selectedTaskId = null, selectedMonitorPhase = null;
const expandedTaskIds = new Set(), clipMetadataRequests = new Map();
let metadataTooltip = null, metadataTarget = null, metadataPointer = null;
let followRunningTask = true, lastMonitorKey = '';
const monitorPhases = {
    joining_video: { label: '拼接视频文件', bar: '#2798f5', line: '#8caec9', unit: '个/s' },
    joining_audio: { label: '拼接音频文件', bar: '#27c178', line: '#91b5a4', unit: '个/s' },
    muxing: { label: '封装媒体文件', bar: '#f29432', line: '#c6ad91', unit: 'x' }
};

// 路径请求串行提交，避免选择器与入队操作交错后恢复旧配置。
function submitPaths(url, data, afterSave = async () => {}) {
    pathUpdate = pathUpdate.catch(() => {}).then(async () => {
        const res = await axios.post(url, data);
        await afterSave(res);
        return res;
    });
    return pathUpdate;
}

async function setExportPath(refresh = true, afterSave = async () => {}) {
    try {
        await submitPaths('/api/set_export_path', {
            export_path: document.getElementById('ep').value
        }, async res => {
            document.getElementById('msg').innerText = res.data.message;
            if(refresh && !await load(true)) throw new Error('无法刷新素材列表，请重试');
            await afterSave();
        });
        return true;
    } catch(e) {
        const message = e.response?.data?.message || e.message || '导出目录配置失败';
        document.getElementById('msg').innerText = message;
        log('l-front', 'ERROR', message, 'front-color');
        return false;
    }
}

function getFormattedTime() {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, '0');
    const d = String(now.getDate()).padStart(2, '0');
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    const ss = String(now.getSeconds()).padStart(2, '0');
    return `[${y}/${m}/${d}_${hh}:${mm}:${ss}]`;
}

function log(id, tag, msg, cls) {
    const b = document.getElementById(id);
    if(!b) return;
    const d = document.createElement('div');
    d.innerHTML = `<span class="log-time">${getFormattedTime()}</span><span class="${cls}">${tag}</span> ${msg}`;
    b.appendChild(d);
    b.scrollTop = b.scrollHeight;
    if(b.childNodes.length > 100) b.removeChild(b.firstChild);
}

function formatDate(ts) {
    const d = new Date(ts * 1000);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

// 固定像素柱宽需要等时间重采样，不能再把每个原始 dt 直接画成不同宽的柱。
function getMonitorSeries(history, capacity, focusedPhase = null) {
    let elapsed = 0;
    const phases = Object.keys(monitorPhases).map(phase => {
        const start = elapsed;
        const points = (history[phase] || []).filter(point => Number.isFinite(point.dt) && point.dt > 0).map(point => {
            const begin = elapsed;
            elapsed += point.dt;
            return { ...point, start: begin, end: elapsed };
        });
        return { phase, start, end: elapsed, points };
    });
    const focus = phases.find(item => item.phase === focusedPhase && item.points.length);
    const viewStart = focus ? focus.start : 0;
    const viewEnd = focus ? focus.end : elapsed;
    const series = {};
    for (const { phase, start, end, points } of phases) {
        series[phase] = [];
        if (!points.length || (focus && phase !== focus.phase)) continue;
        const count = Math.max(1, Math.round(capacity * (end - start) / (viewEnd - viewStart)));
        for (let index = 0; index < count; index++) {
            const begin = start + (end - start) * index / count;
            const finish = start + (end - start) * (index + 1) / count;
            const bin = { x: (begin + finish) / 2, start: begin, end: finish };
            for (const metric of ['write_mbps', 'speed']) {
                let weighted = 0, known = 0, unknown = false;
                for (const point of points) {
                    const overlap = Math.min(finish, point.end) - Math.max(begin, point.start);
                    if (overlap <= 0) continue;
                    if (Number.isFinite(point[metric])) {
                        weighted += point[metric] * overlap;
                        known += overlap;
                    } else unknown = true;
                }
                bin[metric] = !unknown && known > 0 ? weighted / known : null;
            }
            series[phase].push(bin);
        }
    }
    return { series, elapsed, viewStart, viewEnd };
}

function initChart() {
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const fixedAxisWidth = axis => { axis.width = 48; };
    const metricTick = value => Number(value) === 0 ? '' : Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 1 });
    const tooltip = {
        filter: item => Number.isFinite(item.raw?.y),
        callbacks: {
            title: items => items.length ? `处理时间 ${items[0].raw.start.toFixed(1)}–${items[0].raw.end.toFixed(1)} 秒` : '',
            label: item => `${item.dataset.label}: ${item.raw.y.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`
        }
    };
    const baseOptions = () => ({
        responsive: true, maintainAspectRatio: false,
        layout: { autoPadding: false, padding: { top: 0, bottom: 0 } },
        animation: reducedMotion ? false : { duration: 180, easing: 'linear' },
        animations: reducedMotion ? {} : { x: { duration: 0 }, colors: { duration: 140 } },
        interaction: { mode: 'nearest', axis: 'x', intersect: false },
        plugins: { legend: { display: false }, tooltip },
        onResize: () => {
            lastMonitorKey = '';
            requestAnimationFrame(() => refreshTaskMonitor());
        }
    });
    const timeAxis = () => ({
        type: 'linear', offset: false, min: 0, max: 1,
        border: { color: '#777' }, grid: { display: false, drawTicks: false },
        ticks: { display: false }
    });
    chart = new Chart(document.getElementById('chart'), {
        type: 'bar',
        data: { datasets: Object.entries(monitorPhases).map(([phase, config]) => ({
            phase, label: `${config.label} · 写入 MB/s`, data: [], yAxisID: 'disk',
            backgroundColor: config.bar, grouped: false, barThickness: 3, maxBarThickness: 3,
            borderWidth: 0, borderRadius: 0, borderSkipped: false, inflateAmount: 0
        })) },
        options: { ...baseOptions(), scales: {
            x: timeAxis(),
            disk: { position: 'left', beginAtZero: true, suggestedMax: 1, afterFit: fixedAxisWidth, grid: { color: '#383838' }, ticks: { color: '#aaa', maxTicksLimit: 4, font: { size: 10 }, callback: metricTick } },
            spacer: { position: 'right', min: 0, max: 1, afterFit: fixedAxisWidth, border: { display: false }, grid: { display: false }, ticks: { display: false } }
        } }
    });
    speedChart = new Chart(document.getElementById('speed-chart'), {
        type: 'line',
        data: { datasets: Object.entries(monitorPhases).map(([phase, config]) => ({
            phase, label: `${config.label} · ${config.unit}`, data: [],
            yAxisID: phase === 'muxing' ? 'mux' : 'chunks', borderColor: config.line,
            borderWidth: 2, pointRadius: 0, pointHoverRadius: 3, tension: 0, spanGaps: false
        })) },
        options: { ...baseOptions(), scales: {
            x: { ...timeAxis(), display: false },
            chunks: { position: 'left', reverse: true, beginAtZero: true, suggestedMax: 1, afterFit: fixedAxisWidth, grid: { color: '#383838' }, ticks: { color: '#91b5a4', maxTicksLimit: 3, font: { size: 10 }, callback: metricTick } },
            mux: { position: 'right', reverse: true, beginAtZero: true, suggestedMax: 1, afterFit: fixedAxisWidth, grid: { drawOnChartArea: false }, ticks: { color: '#c6ad91', maxTicksLimit: 3, font: { size: 10 }, callback: metricTick } }
        } }
    });
    document.getElementById('monitor-follow').onclick = () => {
        followRunningTask = true;
        selectedMonitorPhase = null;
        refreshTaskMonitor();
    };
    for (const [phase, config] of Object.entries(monitorPhases)) {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = config.label;
        button.dataset.phase = phase;
        button.style.setProperty('--phase-color', config.bar);
        button.title = '放大查看此阶段，再次点击返回完整图表';
        button.onclick = () => {
            selectedMonitorPhase = selectedMonitorPhase === phase ? null : phase;
            refreshTaskMonitor();
        };
        document.getElementById('monitor-phases').appendChild(button);
    }
    refreshTaskMonitor();
    log('l-front', 'CORE', '控制台引擎加载完毕', 'front-color');
}

function selectMonitorTask(id) {
    selectedTaskId = id;
    followRunningTask = false;
    selectedMonitorPhase = null;
    refreshTaskMonitor();
}

function refreshTaskMonitor() {
    if (!chart || !speedChart) return;
    const ids = Object.keys(monitorStatuses);
    const previousTaskId = selectedTaskId;
    if (followRunningTask || !monitorStatuses[selectedTaskId]) {
        selectedTaskId = ids.find(id => monitorStatuses[id].status === 'running') || ids.at(-1) || null;
    }
    if (previousTaskId !== selectedTaskId) selectedMonitorPhase = null;
    const s = monitorStatuses[selectedTaskId];
    const history = s?.performance_history || {};
    if (selectedMonitorPhase && !history[selectedMonitorPhase]?.length) selectedMonitorPhase = null;
    const available = Object.keys(monitorPhases).filter(phase => history[phase]?.length);
    const currentPhase = monitorPhases[s?.stage] ? s.stage : available.at(-1) || 'joining_video';
    const phase = selectedMonitorPhase || currentPhase;
    const config = monitorPhases[phase];
    const last = history[phase]?.at(-1);
    const live = s?.status === 'running' && s.stage === phase;
    const formatRate = value => Number.isFinite(value) ? value.toLocaleString('zh-CN', { maximumFractionDigits: 1 }) : '—';
    document.getElementById('monitor-task').textContent = selectedTaskId || '等待导出任务';
    document.getElementById('monitor-state').textContent = !s ? '点击下方任务查看数据' :
        selectedMonitorPhase ? `${config.label} · 阶段放大${live ? ' · 实时' : ''}` :
        s.stage === 'probing' ? '读取媒体时长 · 图表省略等待' :
        s.status === 'finished' ? '导出成功 · 完整处理图表' :
        s.status === 'error' ? '导出失败 · 保留已有数据' : `${config.label}${live ? ' · 实时' : ' · 阶段记录'}`;
    document.getElementById('monitor-disk').textContent = `${formatRate(last?.write_mbps)} MB/s`;
    document.getElementById('monitor-speed-label').textContent = phase === 'muxing' ? '封装倍速' : phase === 'joining_video' ? '视频片段处理速度' : '音频片段处理速度';
    document.getElementById('monitor-speed').textContent = `${formatRate(last?.speed)} ${config.unit}`;
    document.getElementById('monitor-time').textContent = formatMediaTime(s?.elapsed_seconds);
    document.getElementById('monitor-panel').style.setProperty('--monitor-color', config.bar);
    document.getElementById('monitor-panel').classList.toggle('is-live', live);
    document.getElementById('monitor-follow').classList.toggle('active', followRunningTask);
    document.querySelectorAll('#monitor-phases button').forEach(button => {
        const active = button.dataset.phase === selectedMonitorPhase;
        button.classList.toggle('active', active);
        button.disabled = !history[button.dataset.phase]?.length;
        button.setAttribute('aria-pressed', String(active));
    });
    document.querySelectorAll('.q-item').forEach(item => {
        const active = item.id === `q-${selectedTaskId}`;
        item.classList.toggle('q-selected', active);
        item.setAttribute('aria-pressed', String(active));
    });
    const capacity = Math.max(3, Math.min(240, Math.floor((document.getElementById('chart').clientWidth - 96) / 5)));
    const key = `${selectedTaskId}:${selectedMonitorPhase}:${capacity}:` + Object.keys(monitorPhases).map(name => `${history[name]?.length}:${history[name]?.at(-1)?.t}`).join(':');
    if (key === lastMonitorKey) return;
    const changedTask = !lastMonitorKey.startsWith(`${selectedTaskId}:`);
    lastMonitorKey = key;
    const { series, viewStart, viewEnd } = getMonitorSeries(history, capacity, selectedMonitorPhase);
    for (const [name, colors] of Object.entries(monitorPhases)) {
        const points = series[name];
        const dimmed = selectedMonitorPhase && selectedMonitorPhase !== name;
        const bar = chart.data.datasets.find(dataset => dataset.phase === name);
        const line = speedChart.data.datasets.find(dataset => dataset.phase === name);
        bar.data = points.map(point => ({ ...point, y: point.write_mbps }));
        bar.backgroundColor = colors.bar + (dimmed ? '35' : 'ff');
        line.data = points.map(point => ({ ...point, y: point.speed }));
        line.borderColor = colors.line + (dimmed ? '45' : 'ff');
        line.borderWidth = selectedMonitorPhase === name ? 3 : 2;
        line.pointRadius = points.length === 1 ? 2 : 0;
    }
    chart.options.scales.x.min = speedChart.options.scales.x.min = viewStart;
    chart.options.scales.x.max = speedChart.options.scales.x.max = viewEnd > viewStart ? viewEnd : viewStart + 1;
    speedChart.options.scales.chunks.ticks.display = selectedMonitorPhase !== 'muxing';
    speedChart.options.scales.mux.ticks.display = !selectedMonitorPhase || selectedMonitorPhase === 'muxing';
    chart.update(changedTask ? 'none' : undefined);
    speedChart.update(changedTask ? 'none' : undefined);
}

// --- 新增：播放器逻辑 ---
function openPlayer(cid) {
    const overlay = document.getElementById('video-overlay');
    const video = document.getElementById('main-player');
    const title = document.getElementById('player-title');

    title.innerText = `正在播放预览: ${cid}`;
    // 添加时间戳防止浏览器缓存导致的无法刷新
    video.src = `/api/stream/${cid}?t=${new Date().getTime()}`;
    overlay.classList.add('active');

    video.load();
    video.play().catch(e => {
        log('l-front', 'ERROR', '播放失败，可能是解码器未就绪', 'front-color');
    });
    log('l-front', 'PLAYER', `请求视频流: ${cid}`, 'front-color');
}

function closePlayer() {
    const overlay = document.getElementById('video-overlay');
    const video = document.getElementById('main-player');
    video.pause();
    video.removeAttribute('src');
    video.load();
    overlay.classList.remove('active');
}

async function browse(targetId) {
    log('l-front', 'UI', `触发 ${targetId==='p'?'素材':'导出'} 路径选择器`, 'front-color');
    try {
        const res = await axios.get('/api/select_folder');
        if(res.data.success && res.data.path) {
            document.getElementById(targetId).value = res.data.path;
            log('l-front', 'EVENT', `用户选择了新路径: ${res.data.path}`, 'front-color');
            if(targetId === 'ep') await setExportPath();
        }
    } catch (e) {}
}

async function openExportDir() {
    const ep = document.getElementById('ep').value || document.getElementById('p').value;
    if(!ep) return log('l-front', 'WARN', '未探测到有效路径，无法打开', 'front-color');
    log('l-front', 'SYS', `尝试唤起资源管理器...`, 'front-color');
    axios.post('/api/open_folder', { path: ep });
}

async function setP() {
    const pVal = document.getElementById('p').value;
    const epVal = document.getElementById('ep').value;
    log('l-front', 'API', `请求后端初始化库路径...`, 'front-color');
    try {
        const res = await submitPaths('/api/set_path', { path: pVal, export_path: epVal });
        document.getElementById('msg').innerText = res.data.message;
        load(true);
        if(!window.timer) {
            window.timer = setInterval(tick, 1000);
            log('l-front', 'THREAD', '状态监听心跳已开启', 'front-color');
        }
    } catch(e) {
        log('l-front', 'ERROR', '路径验证通信异常', 'front-color');
    }
}

function toggleView() {
    viewMode = (viewMode === 'flat') ? 'album' : 'flat';
    currentAlbum = null;
    log('l-front', 'UI', `切换视图至: ${viewMode==='flat'?'平铺':'分类'}`, 'front-color');
    document.getElementById('viewBtn').innerText = (viewMode === 'flat') ? "视图: 全部平铺" : "视图: 按游戏分类";
    renderList();
}

function selectAll() {
    let targetClips = (viewMode === 'flat') ? allClips : (currentAlbum ? allClips.filter(c => c.game === currentAlbum) : []);
    const toSelect = targetClips.filter(c => !c.is_converted).map(c => c.id);
    const allIn = toSelect.every(id => sel.includes(id));
    if (allIn) {
        sel = sel.filter(id => !toSelect.includes(id));
        log('l-front', 'UI', `已取消选择当前范围内所有项`, 'front-color');
    } else {
        toSelect.forEach(id => { if(!sel.includes(id)) sel.push(id); });
        log('l-front', 'UI', `已全选 ${toSelect.length} 个未转换项`, 'front-color');
    }
    document.getElementById('qBtn').disabled = sel.length === 0;
    renderList();
}

async function load(verbose = false) {
    try {
        const res = await axios.get('/api/clips');
        const oldLen = allClips.length;
        allClips = res.data.clips;
        allClips.forEach(c => { c.library = res.data.library; });
        if (verbose) clipMetadataRequests.clear();
        const available = new Set(allClips.filter(c => !c.is_converted).map(c => c.id));
        sel = sel.filter(id => available.has(id));
        document.getElementById('qBtn').disabled = sel.length === 0;
        if (verbose || oldLen !== allClips.length) {
            if(verbose) log('l-front', 'INFO', `扫描到 ${allClips.length} 个有效录像`, 'front-color');
            renderList();
        }
        return true;
    } catch (e) { return false; }
}

function renderList() {
    hideClipMetadata();
    const div = document.getElementById('list');
    const selectAllBtn = document.getElementById('allBtn');
    div.innerHTML = '';
    if (viewMode === 'flat') {
        selectAllBtn.style.display = 'inline-block';
        [...allClips].sort((a,b) => b.time - a.time).forEach(c => div.appendChild(createClipEl(c)));
    } else if (viewMode === 'album' && !currentAlbum) {
        selectAllBtn.style.display = 'none';
        const groups = {};
        allClips.forEach(c => { if(!groups[c.game]) groups[c.game] = []; groups[c.game].push(c); });
        Object.keys(groups).sort().forEach(game => {
            const clips = groups[game].sort((a,b) => b.time - a.time);
            const album = document.createElement('div');
            album.className = 'item album-item';
            album.innerHTML = `<div class="img-box album-stack">${clips[0].thumb?`<img src="${clips[0].thumb}">`:'无预览'}</div><div class="album-info"><div class="album-name-text">${game}</div><div style="font-size:9px; color:#888;">${clips.length} 个录像</div></div>`;
            album.onclick = () => { currentAlbum = game; renderList(); };
            div.appendChild(album);
        });
    } else if (viewMode === 'album' && currentAlbum) {
        selectAllBtn.style.display = 'inline-block';
        const backBtn = document.createElement('div');
        backBtn.className = 'item album-back-card'; backBtn.innerText = `返回列表`;
        backBtn.onclick = () => { currentAlbum = null; renderList(); };
        div.appendChild(backBtn);
        const filtered = allClips.filter(c => c.game === currentAlbum).sort((a,b) => b.time - a.time);
        const dateGroups = {};
        filtered.forEach(c => { const d = formatDate(c.time); if(!dateGroups[d]) dateGroups[d] = []; dateGroups[d].push(c); });
        Object.keys(dateGroups).forEach(date => {
            const dateTitle = document.createElement('div'); dateTitle.className = 'date-divider'; dateTitle.innerHTML = `<span>${date}</span>`;
            div.appendChild(dateTitle);
            dateGroups[date].forEach(c => div.appendChild(createClipEl(c)));
        });
    }
}

function hideClipMetadata() {
    metadataTarget = null;
    if (metadataTooltip) metadataTooltip.hidden = true;
}

function moveClipMetadata(event) {
    if (!metadataTarget || !metadataTooltip) return;
    metadataPointer = { clientX: event.clientX, clientY: event.clientY };
    const { width, height } = metadataTooltip.getBoundingClientRect();
    let left = event.clientX + 14, top = event.clientY + 16;
    if (left + width > window.innerWidth - 8) left = event.clientX - width - 14;
    if (top + height > window.innerHeight - 8) top = event.clientY - height - 16;
    metadataTooltip.style.left = `${Math.max(8, left)}px`;
    metadataTooltip.style.top = `${Math.max(8, top)}px`;
}

function showClipMetadata(event, target) {
    if (!metadataTooltip) {
        metadataTooltip = document.createElement('div');
        metadataTooltip.id = 'clip-metadata-tooltip';
        metadataTooltip.className = 'clip-metadata';
        metadataTooltip.setAttribute('role', 'tooltip');
        document.body.appendChild(metadataTooltip);
        document.addEventListener('scroll', hideClipMetadata, true);
        window.addEventListener('resize', hideClipMetadata);
        window.addEventListener('blur', hideClipMetadata);
    }
    metadataTarget = target;
    metadataTooltip.textContent = '时长：读取中…\n预计大小：读取中…';
    metadataTooltip.hidden = false;
    moveClipMetadata(event);
}

function createClipEl(c) {
    const el = document.createElement('div');
    el.className = `item ${c.is_converted?'done':''} ${sel.includes(c.id)?'selected':''}`;

    el.innerHTML = `
        <div class="img-box">
            ${c.thumb?`<img src="${c.thumb}">`:'无预览'}
            <div class="hover-preview"></div>
            <div class="play-hint">点击播放</div>
        </div>
        <div class="item-footer">
            <div class="cid-text">${c.id}</div>
        </div>
    `;

    const imgBox = el.querySelector('.img-box');
    const hoverBox = el.querySelector('.hover-preview');

    let previewTimer;
    imgBox.onmouseenter = event => {
        showClipMetadata(event, imgBox);
        const key = JSON.stringify([c.library, c.id]);
        if (!clipMetadataRequests.has(key)) {
            const request = axios.get(`/api/metadata/${encodeURIComponent(c.id)}`, { params: { library: c.library } })
                .then(res => res.data).catch(() => {
                    if (clipMetadataRequests.get(key) === request) clipMetadataRequests.delete(key);
                    return {};
                });
            clipMetadataRequests.set(key, request);
        }
        clipMetadataRequests.get(key).then(data => {
            if (metadataTarget !== imgBox) return;
            const duration = Number.isFinite(data.duration_seconds) && data.duration_seconds > 0 ? formatMediaTime(data.duration_seconds) : '未知';
            metadataTooltip.textContent = `时长：${duration}\n预计大小：${formatFileSize(data.estimated_size_bytes)}`;
            moveClipMetadata(metadataPointer);
        });
        previewTimer = setTimeout(() => {
            const v = document.createElement('video');
            v.src = `/api/stream/${c.id}?type=preview`;
            v.muted = true;
            v.autoplay = true;
            v.loop = true;
            v.setAttribute('playsinline', '');
            hoverBox.appendChild(v);
            hoverBox.style.opacity = "1";
        }, 800);
    };
    imgBox.onmousemove = moveClipMetadata;
    imgBox.onmouseleave = () => {
        hideClipMetadata();
        clearTimeout(previewTimer);
        hoverBox.innerHTML = "";
        hoverBox.style.opacity = "0";
    };

    imgBox.onclick = (e) => {
        e.stopPropagation();
        hideClipMetadata();
        openPlayer(c.id);
    };

    el.querySelector('.item-footer').onclick = (e) => {
        e.stopPropagation();
        if(c.is_converted) return;
        if(sel.includes(c.id)) sel = sel.filter(i=>i!==c.id);
        else sel.push(c.id);
        document.getElementById('qBtn').disabled = sel.length===0;
        renderList();
    };

    return el;
}
async function addQ() {
    const requestedIds = [...sel];
    // 配置、刷新和入队共用串行链，后续目录变更必须等此次队列提交结束。
    await setExportPath(true, async () => {
        const available = new Set(allClips.filter(c => !c.is_converted).map(c => c.id));
        const ids = requestedIds.filter(id => available.has(id));
        if(!ids.length) return;
        log('l-front', 'QUEUE', `将 ${ids.length} 项任务提交至转换引擎`, 'front-color');
        await axios.post('/api/queue', { clip_ids: ids });
        sel = sel.filter(id => !ids.includes(id));
        document.getElementById('qBtn').disabled = sel.length === 0;
        renderList();
    });
}

function formatMediaTime(seconds) {
    const total = Math.floor(Math.max(0, Number.isFinite(seconds) ? seconds : 0));
    const hours = Math.floor(total / 3600);
    const minutes = String(Math.floor(total / 60) % 60).padStart(2, '0');
    const remainder = String(total % 60).padStart(2, '0');
    return `${hours ? String(hours).padStart(2, '0') + ':' : ''}${minutes}:${remainder}`;
}

function formatFileSize(bytes) {
    if (!Number.isFinite(bytes) || bytes < 0) return '未知';
    if (bytes < 1024) return `${bytes} B`;
    const units = ['KiB', 'MiB', 'GiB', 'TiB'];
    let value = bytes / 1024, index = 0;
    while (value >= 1024 && index < units.length - 1) { value /= 1024; index++; }
    return `${value.toFixed(1)} ${units[index]}`;
}

function renderQueueProgress(item, id, s) {
    const stages = {
        joining_video: '拼接视频文件', joining_audio: '拼接音频文件',
        probing: '读取媒体时长', muxing: '封装媒体文件'
    };
    item.replaceChildren();
    item.className = `q-item${s.status === 'error' ? ' q-error' : s.status === 'finished' ? ' q-finished' : ''}`;
    item.tabIndex = 0;
    item.setAttribute('role', 'button');
    item.setAttribute('aria-label', `展开或收起任务 ${id} 的详情并查看图表`);
    item.setAttribute('aria-expanded', String(expandedTaskIds.has(id)));
    const toggle = () => {
        if (expandedTaskIds.has(id)) expandedTaskIds.delete(id);
        else expandedTaskIds.add(id);
        renderQueueProgress(item, id, s);
        selectMonitorTask(id);
    };
    item.onclick = toggle;
    item.onkeydown = event => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            toggle();
        }
    };
    let content = item;
    const addText = (tag, text, className = '') => {
        const element = document.createElement(tag);
        element.className = className;
        element.textContent = text;
        content.appendChild(element);
        return element;
    };
    addText('b', `${expandedTaskIds.has(id) ? '▾' : '▸'} ${id}${s.status === 'finished' ? ' · 已完成' : ''}`, 'q-title');
    const reportStage = s.stage === 'preparing' ? 'joining_video' :
        ['finalizing', 'finished'].includes(s.stage) ? 'muxing' : s.stage;
    const stage = stages[reportStage] || s.eta || '排队中';
    addText('div', s.status === 'error' ? `失败 · ${stage}` : stage, 'q-stage');
    const details = document.createElement('div');
    details.hidden = !expandedTaskIds.has(id);
    details.className = 'q-details';
    item.appendChild(details);
    content = details;
    if (Number.isFinite(s.elapsed_seconds)) {
        addText('div', `总用时：${s.elapsed_seconds.toFixed(1)} 秒（不含排队）`, 'q-detail');
        const durations = { ...(s.stage_durations || {}) };
        if (Number.isFinite(durations.preparing)) durations.joining_video = (durations.joining_video || 0) + durations.preparing;
        if (Number.isFinite(durations.finalizing)) durations.muxing = (durations.muxing || 0) + durations.finalizing;
        const timings = Object.entries(stages).map(([key, label]) => {
            if (key === 'joining_audio' && s.has_audio === false) return `${label}：跳过`;
            if (!Number.isFinite(durations[key])) return `${label}：待开始`;
            const current = s.status === 'running' && reportStage === key ? '（进行中）' : '';
            return `${label}：${durations[key].toFixed(1)} 秒${current}`;
        });
        addText('div', timings.join(' · '), 'q-detail');
    }
    if (s.stage) {
        addText('div', `视频分段：${s.video_done || 0} / ${s.video_total || 0}`, 'q-detail');
        const audio = s.has_audio === false ? '无音轨，跳过音频拼接' :
            s.has_audio === true ? `音频分段：${s.audio_done || 0} / ${s.audio_total || 0}` : '音频分段：待检查';
        addText('div', audio, 'q-detail');
        if (['muxing', 'finalizing', 'finished'].includes(s.stage)) {
            const duration = s.duration_seconds > 0 ? formatMediaTime(s.duration_seconds) : '总时长未知';
            addText('div', `已处理媒体：${formatMediaTime(s.processed_seconds)} / ${duration}`, 'q-detail');
        }
        if (Number.isFinite(s.processing_speed)) {
            const speed = addText('div', `封装速度：${s.processing_speed.toFixed(1)} ${s.speed_unit}`, 'q-detail');
            speed.title = s.speed_unit === 'x' ? '2x 表示 FFmpeg 每秒处理约 2 秒录像。' : '拼接阶段按每秒复制的数据量计算。';
        } else if (s.speed && ['muxing', 'finalizing', 'finished'].includes(s.stage)) {
            addText('div', `封装速度：${s.speed}`, 'q-detail');
        }
    }
    if (s.status === 'error') addText('div', s.eta || '导出失败，请查看日志', 'q-message');
    if (s.cleanup_warning) addText('div', `临时文件清理警告：${s.cleanup_warning}`, 'q-message');
    content = item;
    const percent = Math.max(0, Math.min(100, Number.isFinite(s.progress) ? s.progress : 0));
    const indefinite = s.status === 'running' && s.progress_indeterminate;
    addText('div', indefinite ? '整体进度：当前阶段处理中' : `整体进度（估算）：${percent}%`, 'q-detail');
    const progress = document.createElement('progress');
    progress.setAttribute('max', '100');
    progress.setAttribute('aria-label', `${id} ${stage}`);
    if (!indefinite) progress.setAttribute('value', String(percent));
    item.appendChild(progress);
}

async function tick() {
    try {
        const res = await axios.get('/api/progress');
        const stats = res.data.all_statuses, pyl = res.data.py_logs;
        monitorStatuses = stats;
        const total = res.data.total_elapsed_seconds ?? Object.values(stats).reduce((sum, s) => sum + (Number.isFinite(s.elapsed_seconds) ? s.elapsed_seconds : 0), 0);
        document.getElementById('monitor-total-time').textContent = formatMediaTime(total);
        if(pyl.length > pyIdx) {
            for(let i=pyIdx; i<pyl.length; i++) {
                const msg = pyl[i];
                const cleanMsg = msg.includes(']') ? msg.split(']').slice(1).join(']').trim() : msg;
                log('l-py', 'SYSTEM', cleanMsg, 'py-color');
            }
            pyIdx = pyl.length;
        }
        const qDiv = document.getElementById('qList');
        for(let id in stats) {
            const s = stats[id];
            if(s.status === 'running' && s.last_raw_log) {
                if (window[`lastLog_${id}`] !== s.last_raw_log) {
                    log('l-ffmpeg', 'EXEC', `${id.slice(-6)}: ${s.last_raw_log}`, 'ffmpeg-color');
                    window[`lastLog_${id}`] = s.last_raw_log;
                }
            }
            if(s.status === 'finished' && !s.logged) {
                log('l-front', 'DONE', `文件 [${id}] 转换成功并已保存`, 'front-color');
                s.logged = true;
                load();
            }
            let existingItem = document.getElementById(`q-${id}`);
            if (!existingItem) {
                existingItem = document.createElement('div');
                existingItem.id = `q-${id}`;
                existingItem.className = 'q-item';
                qDiv.appendChild(existingItem);
            }
            renderQueueProgress(existingItem, id, s);
        }
        refreshTaskMonitor();
    } catch (e) {}
}

document.addEventListener('DOMContentLoaded', initChart);
