let sel = [], chart = null, pyIdx = 0;
let allClips = [];
let viewMode = 'flat';
let currentAlbum = null;

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
    log('l-front', 'CORE', '控制台引擎加载完毕', 'front-color');
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
        const res = await axios.post('/api/set_path', { path: pVal, export_path: epVal });
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
        if (verbose || oldLen !== allClips.length) {
            if(verbose) log('l-front', 'INFO', `扫描到 ${allClips.length} 个有效录像`, 'front-color');
            renderList();
        }
    } catch (e) {}
}

function renderList() {
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
    imgBox.onmouseenter = () => {
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
    imgBox.onmouseleave = () => {
        clearTimeout(previewTimer);
        hoverBox.innerHTML = "";
        hoverBox.style.opacity = "0";
    };

    imgBox.onclick = (e) => {
        e.stopPropagation();
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
    log('l-front', 'QUEUE', `将 ${sel.length} 项任务提交至转换引擎`, 'front-color');
    try {
        await axios.post('/api/queue', { clip_ids: sel });
        sel = [];
        document.getElementById('qBtn').disabled = true;
        load();
    } catch (e) {}
}

async function tick() {
    try {
        const res = await axios.get('/api/progress');
        const stats = res.data.all_statuses, pyl = res.data.py_logs;
        if(pyl.length > pyIdx) {
            for(let i=pyIdx; i<pyl.length; i++) {
                const msg = pyl[i];
                const cleanMsg = msg.includes(']') ? msg.split(']').slice(1).join(']').trim() : msg;
                log('l-py', 'SYSTEM', cleanMsg, 'py-color');
            }
            pyIdx = pyl.length;
        }
        const qDiv = document.getElementById('qList');
        let lbs = [], dat = [], activeCount = 0;
        for(let id in stats) {
            const s = stats[id];
            activeCount++;
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
            lbs.push(id.slice(-6));
            dat.push(s.progress);
            let existingItem = document.getElementById(`q-${id}`);
            if (!existingItem) {
                existingItem = document.createElement('div');
                existingItem.id = `q-${id}`;
                existingItem.className = 'q-item';
                qDiv.appendChild(existingItem);
            }
            existingItem.innerHTML = `<b>${id}</b> | <span class="eta-text">${s.eta}</span><progress value="${s.progress}" max="100"></progress>`;
        }
        if(activeCount > 0 && chart) {
            chart.data.labels = lbs;
            chart.data.datasets[0].data = dat;
            chart.update('none');
        }
    } catch (e) {}
}

document.addEventListener('DOMContentLoaded', initChart);