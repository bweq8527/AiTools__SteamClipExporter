const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function setup({ cancel = false, invalid = false, delayed = false, converted = false } = {}) {
    const elements = {};
    const document = {
        getElementById(id) {
            return elements[id] ||= { value: '', innerText: '', childNodes: [], appendChild() {} };
        },
        createElement() { return {}; },
        addEventListener() {}
    };
    document.getElementById('p').value = 'source';
    let output = 'old-output';
    let release;
    let configurations = 0;
    const jobs = [];
    const context = vm.createContext({ document, window: {}, setInterval() {}, console, axios: {
        async get(url) {
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
