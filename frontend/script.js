// script.js (JavaScript)
const API_BASE = 'http://127.0.0.1:5000/api';
let selectedClips = []; // 存储选中的 clip_id
let progressChart = null;
let pathStatusElement = null;

document.addEventListener('DOMContentLoaded', () => {
    pathStatusElement = document.getElementById('pathStatus');
    initChart();
});

// 初始化 Chart.js
function initChart() {
    const ctx = document.getElementById('progressChart').getContext('2d');
    progressChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: [], // 录像名称
            datasets: [{
                label: '转换进度 (%)',
                data: [], // 进度百分比
                backgroundColor: 'rgba(54, 162, 235, 0.7)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            }]
        },
        options: {
            indexAxis: 'y', // 柱状图横向显示
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    max: 100,
                    min: 0,
                    title: { display: true, text: '进度 (%)' }
                }
            }
        }
    });
}

// 1. 设置路径并加载列表
async function setPathAndLoad() {
    const path = document.getElementById('clipPath').value.trim();
    if (!path) {
        pathStatusElement.textContent = '❌ 请输入路径';
        return;
    }
    
    pathStatusElement.textContent = '正在设置...';

    try {
        const response = await axios.post(`${API_BASE}/set_path`, { path });
        pathStatusElement.textContent = `✅ ${response.data.message}`;
        await loadClipList();
        
        // 启动实时进度更新 (只启动一次)
        if (!window.progressInterval) {
            window.progressInterval = setInterval(updateProgress, 1000); 
        }

    } catch (error) {
        pathStatusElement.textContent = `❌ 错误: ${error.response ? error.response.data.message : error.message}`;
    }
}

// 2. 加载录像列表
async function loadClipList() {
    const container = document.getElementById('clipListContainer');
    try {
        const response = await axios.get(`${API_BASE}/clips`);
        const clips = response.data.clips;
        container.innerHTML = '';
        selectedClips = []; // 清空选中状态
        
        if (clips.length === 0) {
             container.innerHTML = '<p>当前目录下未找到可转换的录像文件夹。</p>';
        }

        clips.forEach(clip => {
            const item = document.createElement('div');
            item.className = 'clip-item';
            
            // 默认显示未处理
            let statusText = '[未处理]';
            
            if (clip.is_converted) {
                item.classList.add('converted');
                statusText = '✅ [已转换]';
            } else if (clip.status === 'running' || clip.status === 'pending') {
                item.classList.add('in-queue');
                statusText = '⏳ [排队中]';
            } else {
                 // 待转换项可点击
                item.onclick = () => toggleClipSelection(item, clip.id);
            }
            
            // 构建内容
            item.innerHTML = `<span id="status-tag-${clip.id}">${statusText}</span> ${clip.name} (${clip.size_mb} MB)`;
            container.appendChild(item);
        });
        
        // 如果列表中有未转换的项，则启用按钮
        document.getElementById('queueBtn').disabled = !clips.some(c => !c.is_converted && c.status === 'idle');

    } catch (error) {
        container.innerHTML = `<p class="error-msg">加载录像失败: ${error.response ? error.response.data.message : error.message}</p>`;
        document.getElementById('queueBtn').disabled = true;
    }
}

// 3. 选中/取消选中录像
function toggleClipSelection(item, clipId) {
    const index = selectedClips.indexOf(clipId);
    const statusTag = item.querySelector(`#status-tag-${clipId}`);
    
    if (index > -1) {
        // 取消选中
        selectedClips.splice(index, 1);
        item.classList.remove('selected');
        statusTag.textContent = '[未处理]';
    } else {
        // 选中 (记录顺序)
        selectedClips.push(clipId);
        item.classList.add('selected');
    }
    
    // 重新更新所有选中项的序号
    selectedClips.forEach((id, idx) => {
        const selectedItem = document.querySelector(`.clip-item:has(#status-tag-${id})`);
        if (selectedItem) {
            selectedItem.querySelector(`#status-tag-${id}`).textContent = `[选中 #${idx + 1}]`;
        }
    });
}


// 4. 加入转换队列
async function addToQueue() {
    if (selectedClips.length === 0) {
        alert("请选择至少一个录像加入队列。");
        return;
    }
    
    // 禁用按钮防止重复提交
    const queueBtn = document.getElementById('queueBtn');
    queueBtn.disabled = true;
    
    try {
        const response = await axios.post(`${API_BASE}/queue`, { clip_ids: selectedClips });
        
        // 刷新列表（清除选中标记，更新排队状态）
        selectedClips = []; 
        await loadClipList();
        
    } catch (error) {
        alert(`加入队列失败: ${error.response.data.message}`);
    } finally {
        queueBtn.disabled = false;
    }
}

// 5. 实时更新进度和图表
async function updateProgress() {
    try {
        const response = await axios.get(`${API_BASE}/progress`);
        const { all_statuses } = response.data;
        
        updateQueueDisplay(all_statuses);
        updateChart(all_statuses);
        
        // 检查是否有任务刚刚完成或失败，如果是则刷新列表
        const needsReload = Object.values(all_statuses).some(s => 
            s.status === 'done' || (s.status === 'error' && s.progress !== 100)
        );
        
        if (needsReload) {
            await loadClipList(); 
        }

    } catch (error) {
        console.error("更新进度失败:", error);
    }
}

// 更新队列显示
function updateQueueDisplay(allStatuses) {
    const container = document.getElementById('queueContainer');
    container.innerHTML = '';
    
    // 过滤出 正在运行, 等待中, 和 错误 的任务
    const activeJobs = Object.keys(allStatuses)
        .filter(id => ['running', 'pending', 'error'].includes(allStatuses[id].status))
        .map(id => ({ id, ...allStatuses[id] }));

    if (activeJobs.length === 0) {
        container.innerHTML = '<p>队列为空。</p>';
        return;
    }
    
    activeJobs.forEach(job => {
        const item = document.createElement('div');
        let statusText = '';
        let progressBar = '';
        
        if (job.status === 'running') {
            statusText = `[运行中] 进度: ${job.progress}% | 预计剩余: ${job.eta}`;
            progressBar = `<progress value="${job.progress}" max="100"></progress>`;
            item.classList.add('running');
        } else if (job.status === 'pending') {
            statusText = `[等待中]`;
            item.classList.add('pending');
        } else if (job.status === 'error') {
            statusText = `[错误] ${job.message || '未知错误'}`;
            item.classList.add('error');
        }
        
        item.innerHTML = `<strong>${job.id}</strong><br>${statusText}${progressBar}`;
        container.appendChild(item);
    });
}

// 更新进度柱状图
function updateChart(allStatuses) {
    
    const chartLabels = [];
    const chartData = [];
    
    // 仅显示正在运行和等待中的任务
    Object.keys(allStatuses)
        .filter(id => ['running', 'pending'].includes(allStatuses[id].status))
        .forEach(id => {
            chartLabels.push(id);
            chartData.push(allStatuses[id].progress);
        });
        
    progressChart.data.labels = chartLabels;
    progressChart.data.datasets[0].data = chartData;
    progressChart.update();
}