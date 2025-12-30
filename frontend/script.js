let sel = [], chart = null, pyIdx = 0;

// 生成指定格式时间戳: [2025/12/24_11:22:31]
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
        
        load(true); // <--- 这里设为 true，只有点按钮这一下会出日志

        if(!window.timer) {
            window.timer = setInterval(tick, 1000);
            log('l-front', 'CORE', '后端轮询线程已挂载', 'front-color');
        }
    } catch(e) { 
        log('l-front', 'ERROR', '路径验证不通过', 'front-color'); 
    }
}

// 3. 修改 tick 函数：任务完成自动刷新时设为 false
async function tick() {
    try {
        const s = stats[id];
        const res = await axios.get('/api/progress');
        // ... 前部逻辑保持不变 ...

        for(let id in stats) {
            // ...
            if(s.status === 'finished' && !s.logged) {
                log('l-front', 'DONE', `转换任务结束: ${id}`, 'front-color');
                s.logged = true;
                load(false); // <--- 任务完成后静默刷新素材库状态，不刷 FETCH 日志
            }
            // ...
        }
        // ...
    } catch (e) {}
}

async function load(verbose = false) {
    try {
        const res = await axios.get('/api/clips');
        const div = document.getElementById('list'); 
        div.innerHTML = '';

        // 只有当 verbose 为 true 时才打印这条日志
        if (verbose) {
            log('l-front', 'FETCH', `已扫描到 ${res.data.clips.length} 个视频片段`, 'front-color');
        }
        
        res.data.clips.forEach(c => {
            // ... 保持原有渲染逻辑不变 ...
            const el = document.createElement('div');
            el.className = `item ${c.is_converted?'done':''} ${sel.includes(c.id)?'selected':''}`;
            el.innerHTML = `<div class="img-box">${c.thumb?`<img src="${c.thumb}">`:'无预览'}</div><div style="padding:8px;font-size:10px;text-align:center;">${c.id}</div>`;
            
            if(!c.is_converted) el.onclick = () => {
                if(sel.includes(c.id)) {
                    sel = sel.filter(i=>i!==c.id);
                } else {
                    sel.push(c.id);
                }
                document.getElementById('qBtn').disabled = sel.length===0;
                load(false); // 用户点击选择时，不需要刷屏日志
            };
            div.appendChild(el);
        });
    } catch (e) {
        log('l-front', 'ERROR', '获取列表失败', 'front-color');
    }
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

async function tick() {
    try {
        const res = await axios.get('/api/progress');
        const stats = res.data.all_statuses, pyl = res.data.py_logs;
        
        if(pyl.length > pyIdx) {
            for(let i=pyIdx; i<pyl.length; i++) log('l-py', 'SYSTEM', pyl[i], 'py-color');
            pyIdx = pyl.length;
        }

        const qDiv = document.getElementById('qList'); 
        qDiv.innerHTML = '';
        let lbs = [], dat = [], activeCount = 0;
        
        // --- 核心复原点：不再删除 finished 状态的任务 ---
        for(let id in stats) {
            const s = stats[id];
            activeCount++;

            // 如果是运行中，打印 FFmpeg 日志
            if(s.status === 'running' && s.last_raw_log) log('l-ffmpeg', 'RAW', s.last_raw_log, 'ffmpeg-color');
            
            // 如果是刚刚完成，仅在前端打印一次 Log (此处可根据需要保留)
            if(s.status === 'finished' && !s.logged) {
                log('l-front', 'DONE', `转换任务结束: ${id}`, 'front-color');
                s.logged = true; // 标记已记录日志，防止重复打印
                load(); // 刷新左侧素材库变灰状态
            }

            // 无论什么状态，都加入图表
            lbs.push(id.slice(-6)); 
            dat.push(s.progress);
            
            // 无论什么状态，都渲染在任务监控区域
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