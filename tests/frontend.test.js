const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function setup({ cancel = false, invalid = false, delayed = false, converted = false, statuses = {} } = {}) {
    const elements = {};
    function element(tagName = 'div') {
        return {
            tagName, value: '', innerText: '', childNodes: [], attributes: {}, _text: '',
            set textContent(value) { this._text = String(value); this.childNodes = []; },
            get textContent() { return this._text + this.childNodes.map(child => child.textContent || '').join(''); },
            appendChild(child) { this.childNodes.push(child); },
            replaceChildren(...children) { this._text = ''; this.childNodes = children; },
            setAttribute(name, value) { this.attributes[name] = String(value); },
            removeAttribute(name) { delete this.attributes[name]; }
        };
    }
    const document = {
        getElementById(id) {
            return elements[id] ||= element();
        },
        createElement: element,
        addEventListener() {}
    };
    document.getElementById('p').value = 'source';
    let output = 'old-output';
    let release;
    let configurations = 0;
    const jobs = [];
    const context = vm.createContext({ document, window: {}, setInterval() {}, console, axios: {
        async get(url) {
            if (url === '/api/progress') return { data: { all_statuses: statuses, py_logs: [] } };
            if (url === '/api/select_folder') return { data: { success: !cancel, path: cancel ? '' : 'new-output' } };
            return { data: { clips: [{ id: 'clip_test', is_converted: converted }] } };
        },
        async post(url, payload) {
            if (url === '/api/set_export_path') {
                if (delayed && ++configurations === 1) await new Promise(resolve => { release = resolve; });
                if (invalid) throw { response: { data: { message: '无效的导出路径' } } };
                output = payload.export_path || 'source';
                return { data: { success: true, export_path: output, message: '导出目录配置成功' } };
            }
            if (url === '/api/queue') {
                // The server may process queue after a later configuration request arrives.
                await new Promise(resolve => setImmediate(resolve));
                jobs.push({ ids: payload.clip_ids, output });
            }
            return { data: { success: true } };
        }
    } });
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../frontend/script.js'), 'utf8'), context);
    // Rendering is outside these state/request-order tests; keep load() real.
    vm.runInContext('renderList = () => {}', context);
    return { context, document, jobs, get output() { return output; }, release: () => release?.() };
}

test('choosing export directory applies it without clicking scan', async () => {
    const ui = setup();
    await ui.context.browse('ep');
    assert.equal(ui.output, 'new-output');
});

test('cancelling picker preserves active output', async () => {
    const ui = setup({ cancel: true });
    await ui.context.browse('ep');
    assert.equal(ui.output, 'old-output');
});

test('queue uses latest typed output without rescanning', async () => {
    const ui = setup();
    ui.document.getElementById('ep').value = 'typed-output';
    vm.runInContext("sel = ['clip_test']", ui.context);
    await ui.context.addQ();
    assert.equal(ui.jobs[0].output, 'typed-output');
});

test('invalid output blocks queue and preserves selection', async () => {
    const ui = setup({ invalid: true });
    ui.document.getElementById('ep').value = 'missing';
    vm.runInContext("sel = ['clip_test']", ui.context);
    await ui.context.addQ();
    assert.equal(ui.jobs.length, 0);
    assert.equal(vm.runInContext('sel.length', ui.context), 1);
});

test('queue waits for output configuration', async () => {
    const ui = setup({ delayed: true });
    ui.document.getElementById('ep').value = 'new-output';
    vm.runInContext("sel = ['clip_test']", ui.context);
    const pending = ui.context.addQ();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(ui.jobs.length, 0);
    ui.release();
    await pending;
    assert.equal(ui.jobs[0].output, 'new-output');
});

test('changing output removes selections already exported in new directory', async () => {
    const ui = setup({ converted: true });
    vm.runInContext("sel = ['clip_test']; document.getElementById('qBtn').disabled = false", ui.context);
    await ui.context.browse('ep');
    assert.equal(vm.runInContext('sel.length', ui.context), 0);
    assert.equal(ui.document.getElementById('qBtn').disabled, true);
    await ui.context.addQ();
    assert.equal(ui.jobs.length, 0);
});

test('later output change cannot overtake an earlier queue action', async () => {
    const ui = setup({ delayed: true });
    ui.document.getElementById('ep').value = 'output-A';
    vm.runInContext("sel = ['clip_test']", ui.context);
    const enqueue = ui.context.addQ();
    await new Promise(resolve => setImmediate(resolve));
    ui.document.getElementById('ep').value = 'output-B';
    const change = ui.context.setExportPath(false);
    ui.release();
    await Promise.all([enqueue, change]);
    assert.equal(ui.jobs[0].output, 'output-A');
    assert.equal(ui.output, 'output-B');
});

function descendants(node) {
    return [node, ...node.childNodes.flatMap(descendants)];
}

test('polling renders independent track counts, current stage and media progress', async () => {
    const ui = setup({ statuses: { clip_test: {
        status: 'running', stage: 'muxing', progress: 60, eta: '正在封装 MP4',
        video_done: 12, video_total: 12, audio_done: 9, audio_total: 9,
        has_audio: true, processed_seconds: 150, duration_seconds: 600, speed: '2.5x'
    } } });
    await ui.context.tick();
    const card = ui.document.getElementById('q-clip_test');
    assert.match(card.textContent, /FFmpeg 封装/);
    assert.match(card.textContent, /视频分段：12 \/ 12/);
    assert.match(card.textContent, /音频分段：9 \/ 9/);
    assert.match(card.textContent, /02:30 \/ 10:00/);
    assert.match(card.textContent, /2.5x/);
    assert.match(card.textContent, /估算/);
});

test('unknown duration keeps elapsed time and uses indeterminate progress', async () => {
    const ui = setup({ statuses: { clip_test: {
        status: 'running', stage: 'muxing', progress: 40, progress_indeterminate: true,
        has_audio: false, video_done: 2, video_total: 2,
        processed_seconds: 65, duration_seconds: 0, speed: null
    } } });
    await ui.context.tick();
    const card = ui.document.getElementById('q-clip_test');
    assert.match(card.textContent, /01:05/);
    assert.match(card.textContent, /总时长未知/);
    assert.match(card.textContent, /无音轨/);
    const progress = descendants(card).find(node => node.tagName === 'progress');
    assert.ok(progress);
    assert.equal(Object.hasOwn(progress.attributes, 'value'), false);
    assert.doesNotMatch(card.textContent, /40%/);
});

test('failed job preserves counts and error without success log', async () => {
    const ui = setup({ statuses: { clip_test: {
        status: 'error', stage: 'joining_audio', progress: 30, eta: '出错: cannot read segment',
        has_audio: true, video_done: 5, video_total: 5, audio_done: 2, audio_total: 4
    } } });
    await ui.context.tick();
    const card = ui.document.getElementById('q-clip_test');
    assert.match(card.textContent, /失败/);
    assert.match(card.textContent, /拼接音频/);
    assert.match(card.textContent, /音频分段：2 \/ 4/);
    assert.match(card.textContent, /cannot read segment/);
    assert.equal(ui.document.getElementById('l-front').childNodes.length, 0);
});

test('pending and legacy status remain readable', async () => {
    const ui = setup({ statuses: {
        clip_pending: { status: 'pending', progress: 0, eta: '排队中' },
        clip_old: { status: 'running', progress: 15, eta: '旧版处理中' }
    } });
    await ui.context.tick();
    assert.match(ui.document.getElementById('q-clip_pending').textContent, /排队中/);
    assert.match(ui.document.getElementById('q-clip_old').textContent, /旧版处理中/);
});
