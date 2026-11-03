import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../djangocms_transfer/static/djangocms_transfer/js/clipboard.js', import.meta.url), 'utf8');
const payload = JSON.stringify({format: 'djangocms-transfer', version: 1, kind: 'plugin', plugins: []});
const flush = async () => { for (let i = 0; i < 5; i++) { await new Promise(setImmediate); } };

function setup(options = {}) {
    const messages = [], writes = [], requests = [];
    const timers = new Map();
    let click, capture, reloads = 0, closedMenus = 0;
    class StructureBoard {
        invalidateState() { return 'cms-result'; }
    }
    class Plugin {
        constructor() { this.options = {}; }
        copyPlugin() { return 'copy-started'; }
        cutPlugin() { return 'cut-started'; }
    }
    const clipboard = {
        readText: async () => options.text ?? payload,
        writeText: async text => { writes.push(text); }
    };
    const context = {
        Blob, FormData,
        MouseEvent: class { constructor(type) { this.type = type; } },
        setTimeout: handler => { const id = timers.size + 1; timers.set(id, handler); return id; },
        clearTimeout: id => timers.delete(id),
        addEventListener() {},
        navigator: {clipboard},
        document: {
            body: {dispatchEvent: () => { closedMenus++; }},
            readyState: 'complete', documentElement: {dataset: {}},
            querySelectorAll: () => [],
            querySelector: () => ({matches: () => false, querySelector: () => ({href: '/clipboard/'})}),
            addEventListener: (name, handler, useCapture) => { click = handler; capture = useCapture; }
        },
        location: {reload: () => { reloads++; }},
        CMS: {
            StructureBoard, Plugin,
            config: {csrf: 'csrf-token', clipboard: {id: '42'}},
            API: {locked: false, StructureBoard: new StructureBoard(), Messages: {open: message => messages.push(message)}}
        },
        fetch: async (url, settings = {}) => {
            requests.push({url, ...settings});
            if (options.fetch) { return options.fetch(url, settings); }
            return {ok: options.ok !== false, status: options.status || 200, text: async () => payload};
        }
    };
    if (options.gestureWrite) {
        context.ClipboardItem = class { constructor(data) { this.data = data; } };
        clipboard.write = async items => {
            const blob = await items[0].data['text/plain'];
            writes.push(await blob.text());
        };
    }
    context.window = context;
    vm.runInNewContext(source, context);
    const event = kind => ({
        target: {closest: selector => {
            if (kind === 'copy' && selector === '[data-rel="copy"]') { return {closest: () => null}; }
            return kind === 'import' && selector === '.cms-transfer-clipboard-import' ? {} : null;
        }},
        preventDefault() {}, stopImmediatePropagation() {}
    });
    return {context, clipboard, messages, writes, requests,
        click: kind => kind === 'copy' ? new Plugin().copyPlugin() : click(event(kind)), capture,
        copy: (options, language) => new Plugin().copyPlugin(options, language),
        success: (action = 'COPY', options = {}) => context.CMS.API.StructureBoard.invalidateState(action, {plugins: [{plugin_id: '123', plugin_parent: ''}]}, options),
        cut: () => new Plugin().cutPlugin(),
        failure: () => { for (const handler of timers.values()) { handler(); } },
        get reloads() { return reloads; },
        get closedMenus() { return closedMenus; }
    };
}

test('import intercepts toolbar navigation and submits JSON with CSRF', async () => {
    const app = setup();
    assert.equal(app.capture, true);
    await app.click('import');
    assert.equal(app.requests.length, 1);
    assert.equal(await app.requests[0].body.get('clipboard').text(), payload);
    assert.equal(app.requests[0].headers['X-CSRFToken'], 'csrf-token');
    assert.equal(app.reloads, 1);
});

test('invalid JSON and unrelated JSON never reach the server', async () => {
    for (const text of ['bad json', '{}', 'null']) {
        const app = setup({text});
        await app.click('import');
        assert.equal(app.requests.length, 0);
        assert.equal(app.messages[0].error, true);
        assert.equal(app.reloads, 0);
    }
});

test('permission denial or clipboard denial does not refresh or replace content', async () => {
    const app = setup({ok: false, status: 403});
    await app.click('import');
    assert.match(app.messages[0].message, /session or CSRF/);
    assert.equal(app.reloads, 0);
    app.clipboard.readText = async () => { throw Object.assign(new Error(), {name: 'NotAllowedError'}); };
    await app.click('import');
    assert.match(app.messages[1].message, /denied/);
    assert.equal(app.requests.length, 1);
});

test('successful CMS copy exports its clipboard; ordinary Paste does not', async () => {
    const app = setup();
    app.success('PASTE');
    await flush();
    assert.equal(app.requests.length, 0);
    await app.click('copy');
    app.success();
    await flush();
    assert.deepEqual(app.writes, [payload]);
});

test('gesture-based write waits for the CMS copy and export', async () => {
    const app = setup({gestureWrite: true});
    await app.click('copy');
    assert.equal(app.writes.length, 0);
    app.success();
    await flush();
    assert.deepEqual(app.writes, [payload]);
});

test('failed CMS copy does not write browser clipboard', async () => {
    const app = setup({gestureWrite: true});
    await app.click('copy');
    app.failure();
    await flush();
    assert.equal(app.writes.length, 0);
});

test('failed browser write reports that CMS copy still succeeded', async () => {
    const app = setup();
    app.clipboard.writeText = async () => { throw new Error('denied'); };
    await app.click('copy');
    app.success();
    await flush();
    assert.match(app.messages[0].message, /Copied to CMS clipboard/);
    assert.equal(app.reloads, 0);
});

test('slow export does not delay CMS completion or lock the editor', async () => {
    let resolveExport;
    const app = setup({fetch: () => new Promise(resolve => { resolveExport = resolve; })});
    await app.click('copy');
    assert.equal(app.success(), 'cms-result');
    assert.equal(app.context.CMS.API.locked, false);
    assert.equal(app.writes.length, 0);
    resolveExport({ok: true, text: async () => payload});
    await flush();
    assert.deepEqual(app.writes, [payload]);
});

test('copying between languages or pasting does not export browser content', async () => {
    const app = setup();
    app.copy(undefined, 'de');
    app.success('PASTE');
    app.copy({target: '100'});
    app.success();
    await flush();
    assert.equal(app.requests.length, 0);
    assert.equal(app.writes.length, 0);
});

test('a slow earlier export cannot overwrite a newer copy', async () => {
    const responses = [];
    const app = setup({fetch: () => new Promise(resolve => responses.push(resolve))});
    app.copy();
    app.success();
    app.copy();
    app.success();
    responses[1]({ok: true, text: async () => 'new content'});
    await flush();
    responses[0]({ok: true, text: async () => 'old content'});
    await flush();
    assert.deepEqual(app.writes, ['new content']);
});

test('missing clipboard API reports errors without making server requests', async () => {
    const app = setup();
    delete app.context.navigator.clipboard;
    await app.click('import');
    assert.match(app.messages[0].message, /unavailable/);
    assert.equal(app.copy(), 'copy-started');
    assert.equal(app.success(), 'cms-result');
    await flush();
    assert.match(app.messages[1].message, /Copied to CMS clipboard/);
    assert.equal(app.requests.length, 0);
    assert.equal(app.reloads, 0);
});

test('server validation errors and server failures do not reload the editor', async () => {
    for (const status of [400, 500]) {
        const app = setup({ok: false, status});
        await app.click('import');
        assert.match(app.messages[0].message, /could not be imported/);
        assert.equal(app.messages[0].error, true);
        assert.equal(app.reloads, 0);
        // A failed import must release the busy state so the user can retry.
        await app.click('import');
        assert.equal(app.requests.length, 2);
    }
});

test('network failure on import reports an error and permits retry', async () => {
    const app = setup({fetch: async () => { throw new Error('Network unavailable'); }});
    await app.click('import');
    assert.equal(app.messages[0].message, 'Network unavailable');
    assert.equal(app.reloads, 0);
    await app.click('import');
    assert.equal(app.requests.length, 2);
});

test('failed export never changes the browser clipboard or blocks CMS copy', async () => {
    for (const gestureWrite of [false, true]) {
        for (const networkFailure of [false, true]) {
            const app = setup({gestureWrite, ok: false,
                ...(networkFailure ? {fetch: async () => { throw new Error('Network unavailable'); }} : {})});
            assert.equal(app.copy(), 'copy-started');
            assert.equal(app.success(), 'cms-result');
            await flush();
            assert.equal(app.writes.length, 0);
            assert.equal(app.context.CMS.API.locked, false);
            assert.match(app.messages[0].message, /Copied to CMS clipboard/);
        }
    }
});

test('synchronous ClipboardItem write failure falls back to writeText', async () => {
    const app = setup({gestureWrite: true});
    app.clipboard.write = () => { throw new Error('Write unsupported'); };
    app.copy();
    app.success();
    await flush();
    assert.deepEqual(app.writes, [payload]);
    assert.equal(app.messages.length, 0);
});

test('denied gesture-based write reports failure without affecting CMS copy', async () => {
    const app = setup({gestureWrite: true});
    app.clipboard.write = async () => { throw new Error('Permission denied'); };
    assert.equal(app.copy(), 'copy-started');
    assert.equal(app.success(), 'cms-result');
    await flush();
    assert.equal(app.writes.length, 0);
    assert.match(app.messages[0].message, /Copied to CMS clipboard/);
    assert.equal(app.context.CMS.API.locked, false);
});

test('server validation and permission reasons are shown to the user', async () => {
    for (const status of [400, 403]) {
        const reason = status === 400 ? 'MissingPlugin is not installed on this site.' :
            'You do not have permission to add TextPlugin.';
        const app = setup({fetch: async () => ({ok: false, status, json: async () => ({error: reason})})});
        await app.click('import');
        assert.equal(app.messages[0].message, reason);
        assert.equal(app.messages[0].error, true);
        assert.equal(app.reloads, 0);
    }
});

test('server-provided plugin names are escaped before rendering CMS messages', async () => {
    const app = setup({fetch: async () => ({ok: false, status: 400,
        json: async () => ({error: 'Plugin "<img src=x onerror=alert(1)>" is not installed.'})})});
    await app.click('import');
    assert.match(app.messages[0].message, /&lt;img/);
    assert.match(app.messages[0].message, /&quot;/);
    assert.equal(app.messages[0].message.includes('<img'), false);
    assert.equal(app.reloads, 0);
});

test('malformed error responses and internal server errors use a generic message', async () => {
    for (const [status, body] of [[400, {error: {unexpected: true}}], [500, {error: 'Internal traceback'}]]) {
        const app = setup({fetch: async () => ({ok: false, status, json: async () => body})});
        await app.click('import');
        assert.match(app.messages[0].message, /could not be imported/);
        assert.equal(app.messages[0].message.includes('traceback'), false);
    }
});

test('cross-tab COPY cannot complete this tab copy or trigger an export', async () => {
    const app = setup();
    app.copy();
    app.success('COPY', {propagate: false});
    await flush();
    assert.equal(app.requests.length, 0);
    app.success();
    await flush();
    assert.match(app.requests[0].url, /\?plugin=123$/);
    assert.deepEqual(app.writes, [payload]);
});

test('timed-out browser write retries when a slow CMS copy completes', async () => {
    const app = setup({gestureWrite: true});
    app.copy();
    app.failure();
    assert.match(app.messages[0].message, /taking longer/);
    app.success();
    await flush();
    assert.deepEqual(app.writes, [payload]);
});

test('failed superseded exports do not report an error after a newer success', async () => {
    const requests = [];
    const app = setup({fetch: () => new Promise((resolve, reject) => requests.push({resolve, reject}))});
    app.copy(); app.success();
    app.copy(); app.success();
    requests[1].resolve({ok: true, text: async () => payload});
    await flush();
    requests[0].reject(new Error('Old export failed'));
    await flush();
    assert.deepEqual(app.writes, [payload]);
    assert.equal(app.messages.length, 0);
});

test('Cut also updates the browser clipboard', async () => {
    const app = setup();
    assert.equal(app.cut(), 'cut-started');
    app.success('CUT');
    await flush();
    assert.deepEqual(app.writes, [payload]);
});

test('import closes the menu before requesting clipboard permission', async () => {
    const app = setup();
    app.clipboard.readText = async () => {
        assert.equal(app.closedMenus, 1);
        throw Object.assign(new Error(), {name: 'NotAllowedError'});
    };
    await app.click('import');
    assert.equal(app.closedMenus, 1);
    assert.equal(app.reloads, 0);
});

test('upload-size errors from JSON or HTML responses explain the limit', async () => {
    for (const json of [async () => ({error: 'Clipboard upload limit exceeded.'}),
                        async () => { throw new Error('HTML proxy response'); }]) {
        const app = setup({fetch: async () => ({ok: false, status: 413, json})});
        await app.click('import');
        assert.match(app.messages[0].message, /limit/);
        assert.equal(app.reloads, 0);
    }
});

test('session expiry and login redirects are not mistaken for successful imports', async () => {
    for (const response of [{ok: true, status: 200, redirected: true}, {ok: false, status: 401}]) {
        const app = setup({fetch: async () => response});
        await app.click('import');
        assert.match(app.messages[0].message, /session has expired/);
        assert.equal(app.reloads, 0);
    }
});

test('a newer copy in another tab supersedes this tab slow export without errors', async () => {
    let resolveExport;
    const app = setup({gestureWrite: true, fetch: () => new Promise(resolve => { resolveExport = resolve; })});
    app.copy(); app.success();
    app.success('COPY', {propagate: false});
    resolveExport({ok: true, text: async () => payload});
    await flush();
    assert.equal(app.writes.length, 0);
    assert.equal(app.messages.length, 0);
});
