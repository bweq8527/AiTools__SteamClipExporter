let sel = [], chart = null, pyIdx = 0;
let allClips = [];
let viewMode = 'flat';
let currentAlbum = null;

// --- 还原：完整的时间戳格式化 ---
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

// --- 还原：完整的日志输出函数 ---
function log(id, tag, msg, cls) {
    const b = document.getElementById(id);
    if(!b) return;
    const d = document.createElement('div');
    // 还原：HTML 结构与原始样式类名一致
    d.innerHTML = `<span class="log-time">${getFormattedTime()}</span><span class="${cls}">${tag}</span> ${msg}`;
    b.appendChild(d);
    b.scrollTop = b.scrollHeight;
    // 还原：保持 100 条日志限制
    if(b.childNodes.length > 100) b.removeChild(b.firstChild);
}

function formatDate(ts) {
    const d = new Date(ts * 1000);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function initChart() {
    chart = new Chart(document.getElementById('chart'), {
        type: 'bar',
        data: { labels: [], datasets: [{ data: [], backgroundColor: '#2196f3', borderRadius: 4 }] },
        options: {
            indexAxis: 'y', responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { x: { max:100, min:0, grid: { color: '#333' } }, y: { grid: { display: false }, ticks: { color: '#888', font: { size: 10 } } } }
        }
    });
    // 还原：初始化日志
    log('l-front', 'UI_INIT', '控制台界面渲染成功', 'front-color');
}

async function browse(targetId) {
    log('l-front', 'EVENT', '唤起文件浏览器', 'front-color');
    try {
        const res = await axios.get('/api/select_folder');
        if(res.data.success && res.data.path) {
            document.getElementById(targetId).value = res.data.path;
            log('l-front', 'PATH', `目录更新: ${res.data.path}`, 'front-color');
        }
    } catch (e) {
        log('l-front', 'ERROR', '无法唤起文件浏览器', 'front-color');
    }
}

async function openExportDir() {
    const ep = document.getElementById('ep').value || document.getElementById('p').value;
    if(!ep) return log('l-front', 'WARN', '未设定有效路径', 'front-color');
    try {
        await axios.post('/api/open_folder', { path: ep });
    } catch(e) {
        log('l-front', 'ERROR', '文件夹不存在或无法打开', 'front-color');
    }
}

async function setP() {
    const pVal = document.getElementById('p').value;
    const epVal = document.getElementById('ep').value;
    log('l-front', 'API', `正在同步后端路径配置...`, 'front-color');
    try {
        const res = await axios.post('/api/set_path', { path: pVal, export_path: epVal });
        document.getElementById('msg').innerText = res.data.message;
        load(true);
        if(!window.timer) {
            window.timer = setInterval(tick, 1000);
            log('l-front', 'CORE', '后端轮询线程已挂载', 'front-color');
        }
    } catch(e) {
        log('l-front', 'ERROR', '路径验证不通过', 'front-color');
    }
}

function toggleView() {
    viewMode = (viewMode === 'flat') ? 'album' : 'flat';
    currentAlbum = null;
    document.getElementById('viewBtn').innerText = (viewMode === 'flat') ? "视图: 全部平铺" : "视图: 游戏分类";
    renderList();
}

function selectAll() {
    let targetClips = [];
    if (viewMode === 'flat') {
        targetClips = allClips;
    } else if (viewMode === 'album' && currentAlbum) {
        targetClips = allClips.filter(c => c.game === currentAlbum);
    } else return;

    const toSelect = targetClips.filter(c => !c.is_converted).map(c => c.id);
    const allIn = toSelect.every(id => sel.includes(id));
    if (allIn) {
        sel = sel.filter(id => !toSelect.includes(id));
    } else {
        toSelect.forEach(id => { if(!sel.includes(id)) sel.push(id); });
    }
    document.getElementById('qBtn').disabled = sel.length === 0;
    renderList();
}

async function load(verbose = false) {
    try {
        const res = await axios.get('/api/clips');
        allClips = res.data.clips;
        if (verbose) log('l-front', 'FETCH', `已扫描到 ${allClips.length} 个视频片段`, 'front-color');
        renderList();
    } catch (e) {
        log('l-front', 'ERROR', '获取列表失败', 'front-color');
    }
}

function renderList() {
    const div = document.getElementById('list');
    const titleArea = document.getElementById('lib-title');
    const selectAllBtn = document.getElementById('allBtn');
    div.innerHTML = '';

    if (viewMode === 'flat') {
        titleArea.innerText = "待处理素材库";
        selectAllBtn.style.display = 'inline-block';
        const sorted = [...allClips].sort((a,b) => b.time - a.time);
        sorted.forEach(c => div.appendChild(createClipEl(c)));
    } else if (viewMode === 'album' && !currentAlbum) {
        titleArea.innerText = "游戏专辑库";
        selectAllBtn.style.display = 'none';
        const groups = {};
        allClips.forEach(c => {
            if(!groups[c.game]) groups[c.game] = [];
            groups[c.game].push(c);
        });
        Object.keys(groups).sort().forEach(game => {
            const clips = groups[game].sort((a,b) => b.time - a.time);
            const album = document.createElement('div');
            album.className = 'item album-item';
            album.innerHTML = `
                <div class="img-box album-stack">${clips[0].thumb?`<img src="${clips[0].thumb}">`:'无预览'}</div>
                <div class="album-info"><div class="album-name-text">${game}</div><div style="font-size:9px; color:#888;">${clips.length} 个录像</div></div>`;
            album.onclick = () => { currentAlbum = game; renderList(); };
            div.appendChild(album);
        });
    } else if (viewMode === 'album' && currentAlbum) {
        titleArea.innerText = `专辑: ${currentAlbum}`;
        selectAllBtn.style.display = 'inline-block';
        const backBtn = document.createElement('div');
        backBtn.className = 'item album-back-card';
        backBtn.innerText = `返回列表`;
        backBtn.onclick = () => { currentAlbum = null; renderList(); };
        div.appendChild(backBtn);

        const filtered = allClips.filter(c => c.game === currentAlbum).sort((a,b) => b.time - a.time);
        const dateGroups = {};
        filtered.forEach(c => {
            const d = formatDate(c.time);
            if(!dateGroups[d]) dateGroups[d] = [];
            dateGroups[d].push(c);
        });
        Object.keys(dateGroups).forEach(date => {
            const dateTitle = document.createElement('div');
            dateTitle.className = 'date-divider';
            dateTitle.innerHTML = `<span>${date}</span>`;
            div.appendChild(dateTitle);
            dateGroups[date].forEach(c => div.appendChild(createClipEl(c)));
        });
    }
}

function createClipEl(c) {
    const el = document.createElement('div');
    el.className = `item ${c.is_converted?'done':''} ${sel.includes(c.id)?'selected':''}`;
    el.innerHTML = `<div class="img-box">${c.thumb?`<img src="${c.thumb}">`:'无预览'}</div><div style="padding:8px;font-size:10px;text-align:center;">${c.id}</div>`;
    if(!c.is_converted) {
        el.onclick = (e) => {
            e.stopPropagation();
            if(sel.includes(c.id)) { sel = sel.filter(i=>i!==c.id); }
            else { sel.push(c.id); }
            document.getElementById('qBtn').disabled = sel.length===0;
            renderList();
        };
    }
    return el;
}

async function addQ() {
    log('l-front', 'QUEUE', `将 ${sel.length} 项任务提交至后台处理`, 'front-color');
    try {
        await axios.post('/api/queue', { clip_ids: sel });
        sel = [];
        document.getElementById('qBtn').disabled = true;
        load();
    } catch (e) {
        log('l-front', 'ERROR', '任务提交失败', 'front-color');
    }
}

// --- 还原：完整的后端轮询 tick 函数 ---
async function tick() {
    try {
        const res = await axios.get('/api/progress');
        const stats = res.data.all_statuses, pyl = res.data.py_logs;

        // 还原：Python 后端日志增量输出
        if(pyl.length > pyIdx) {
            for(let i=pyIdx; i<pyl.length; i++) log('l-py', 'SYSTEM', pyl[i], 'py-color');
            pyIdx = pyl.length;
        }

        const qDiv = document.getElementById('qList');
        qDiv.innerHTML = '';
        let lbs = [], dat = [], activeCount = 0;

        for(let id in stats) {
            const s = stats[id];
            activeCount++;

            // 还原：FFmpeg 原始日志输出
            if(s.status === 'running' && s.last_raw_log) log('l-ffmpeg', 'RAW', s.last_raw_log, 'ffmpeg-color');

            // 还原：任务完成时的前端日志记录
            if(s.status === 'finished' && !s.logged) {
                log('l-front', 'DONE', `转换任务结束: ${id}`, 'front-color');
                s.logged = true;
                load();
            }

            lbs.push(id.slice(-6));
            dat.push(s.progress);

            qDiv.innerHTML += `
                <div class="q-item">
                    <b>${id}</b> | ${s.eta}
                    <progress value="${s.progress}" max="100"></progress>
                </div>`;
        }

        if(activeCount > 0) {
            chart.data.labels = lbs;
            chart.data.datasets[0].data = dat;
            chart.update('none');
        }
    } catch (e) {}
}

document.addEventListener('DOMContentLoaded', initChart);