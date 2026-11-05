(() => {
    'use strict';

    const initialize = () => {
        const cms = window.CMS;
        const selector = '.cms-transfer-clipboard-import';
        const item = document.querySelector(selector);
        if (!item || !cms?.StructureBoard?.prototype || !cms?.Plugin?.prototype ||
                document.documentElement.dataset.transferClipboardInitialized) {
            return;
        }
        document.documentElement.dataset.transferClipboardInitialized = 'true';
        const endpoint = (item.matches('a') ? item : item.querySelector('a')).href;
        const translate = window.gettext || (text => text);
        // CMS messages render HTML. Treat server-provided plugin names as text.
        const escape = text => text.replace(/[&<>"']/g, character => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        })[character]);
        const message = (text, error = false) => cms.API.Messages.open({
            message: escape(translate(text)), error,
            // CMS uses a negative delay to keep the close button visible.
            ...(error ? {delay: -1} : {})
        });
        let importing = false;
        let pendingCopy = null;
        let activeExport = null;
        let copyGeneration = 0;

        const cancelPendingCopy = () => {
            if (pendingCopy) {
                clearTimeout(pendingCopy.timeout);
                pendingCopy.reject?.(new Error('CMS copy did not complete'));
                pendingCopy = null;
            }
        };

        const beginCopy = () => {
            cancelPendingCopy();
            activeExport?.reject?.(new Error('A newer copy superseded this export'));
            const pending = {generation: ++copyGeneration};
            if (navigator.clipboard?.write && window.ClipboardItem) {
                // Start during the user gesture for Safari. Resolve the content
                // only after CMS successfully copies and the async export finishes.
                const data = new Promise((resolve, reject) => {
                    pending.resolve = resolve;
                    pending.reject = reject;
                });
                data.catch(() => {});
                try {
                    pending.write = navigator.clipboard.write([new ClipboardItem({'text/plain': data})]);
                    pending.write.catch(() => {});
                } catch (error) {
                    pending.reject(error);
                }
            }
            // CMS reports its own errors. Release an unfinished browser write if
            // the CMS request fails without invoking the completion callback.
            pending.timeout = setTimeout(() => {
                if (pendingCopy !== pending) { return; }
                pending.reject?.(new Error('Browser write timed out'));
                pending.write = null;
                message('CMS copy is taking longer than expected. Browser copying will be retried when it finishes.', true);
            }, 30000);
            pendingCopy = pending;
        };

        const exportClipboard = async (pending, rootId) => {
            try {
                if (!pending.write && !navigator.clipboard?.writeText) {
                    throw new Error('Browser clipboard access is unavailable');
                }
                const response = await fetch(`${endpoint}?plugin=${encodeURIComponent(rootId)}`, {credentials: 'same-origin', cache: 'no-store'});
                if (!response.ok) {
                    throw new Error('Clipboard export failed');
                }
                const text = await response.text();
                if (pending.generation !== copyGeneration) {
                    pending.reject?.(new Error('A newer copy superseded this export'));
                    return;
                }
                if (pending.write) {
                    pending.resolve(new Blob([text], {type: 'text/plain'}));
                    await pending.write;
                } else {
                    await navigator.clipboard.writeText(text);
                }
            } catch {
                pending.reject?.(new Error('Clipboard export failed'));
                if (pending.generation === copyGeneration) {
                    message('Copied to CMS clipboard, but the browser clipboard could not be updated.', true);
                }
            } finally {
                if (activeExport === pending) { activeExport = null; }
            }
        };

        // COPY is the CMS completion callback in 4.1+. Keep its return value and
        // synchronous UI update intact. The export runs independently: neither
        // this callback nor CMS.API.locked waits for the extra server roundtrip.
        const originalInvalidateState = cms.StructureBoard.prototype.invalidateState;
        cms.StructureBoard.prototype.invalidateState = function (action, ...args) {
            const result = originalInvalidateState.call(this, action, ...args);
            const [data, options] = args;
            if ((action === 'COPY' || action === 'CUT') && options?.propagate === false && activeExport && !pendingCopy) {
                ++copyGeneration;
                activeExport.reject?.(new Error('Another tab copied newer content'));
                activeExport = null;
            }
            if ((action === 'COPY' || action === 'CUT') && options?.propagate !== false && pendingCopy) {
                const pending = pendingCopy;
                clearTimeout(pending.timeout);
                pendingCopy = null;
                const plugins = Array.isArray(data?.plugins) ? data.plugins : [];
                const root = plugins.find(plugin => !plugin.plugin_parent) || plugins[plugins.length - 1];
                if (root?.plugin_id) {
                    activeExport = pending;
                    void exportClipboard(pending, root.plugin_id);
                } else {
                    pending.reject?.(new Error('CMS did not return a copied plugin'));
                    message('Copied to CMS clipboard, but the browser clipboard could not be updated.', true);
                }
            }
            return result;
        };

        // Also cover keyboard shortcuts and CMS's own synthetic click handlers.
        const originalCopyPlugin = cms.Plugin.prototype.copyPlugin;
        cms.Plugin.prototype.copyPlugin = function (options, sourceLanguage, ...args) {
            const target = (options || this.options).target;
            if (!cms.API.locked && !sourceLanguage &&
                    (!target || String(target) === String(cms.config.clipboard.id))) {
                beginCopy();
            }
            return originalCopyPlugin.call(this, options, sourceLanguage, ...args);
        };

        const originalCutPlugin = cms.Plugin.prototype.cutPlugin;
        if (originalCutPlugin) {
            cms.Plugin.prototype.cutPlugin = function (...args) {
                if (!cms.API.locked) { beginCopy(); }
                return originalCutPlugin.apply(this, args);
            };
        }

        // Capture before CMS's toolbar handler navigates to the endpoint.
        document.addEventListener('click', async event => {
            if (!event.target.closest(selector)) {
                return;
            }
            event.preventDefault();
            event.stopImmediatePropagation();
            // Let CMS's existing document click handler reset the dropdown
            // without navigating to the endpoint or depending on jQuery.
            document.body.dispatchEvent(new MouseEvent('click', {bubbles: true}));
            if (importing) {
                return;
            }
            if (!navigator.clipboard?.readText) {
                message('Browser clipboard access is unavailable. Use HTTPS and allow clipboard access.', true);
                return;
            }
            importing = true;
            try {
                const text = await navigator.clipboard.readText();
                let payload;
                try {
                    payload = JSON.parse(text);
                } catch {
                    throw new Error('The browser clipboard does not contain valid transfer JSON.');
                }
                if (!Array.isArray(payload) && (payload?.format !== 'djangocms-transfer' || payload.version !== 1)) {
                    throw new Error('The browser clipboard does not contain valid transfer JSON.');
                }
                const upload = new FormData();
                upload.append('clipboard', new Blob([text], {type: 'application/json'}), 'clipboard.json');
                const response = await fetch(endpoint, {
                    method: 'POST', credentials: 'same-origin',
                    headers: {'X-CSRFToken': cms.config.csrf},
                    body: upload
                });
                if (response.redirected || response.status === 401) {
                    throw new Error('Your session has expired. Reload the page and sign in before importing.');
                }
                if (!response.ok) {
                    let detail;
                    if ([400, 403, 413].includes(response.status)) {
                        try {
                            const body = await response.json();
                            if (typeof body?.error === 'string') {
                                detail = body.error;
                            }
                        } catch {
                            // CSRF failures and proxy errors may return HTML.
                        }
                    }
                    throw new Error(detail || (response.status === 403 ?
                        'Import was not authorized. Your session or CSRF token may have expired. Reload the page and try again.' :
                        (response.status === 413 ? 'Clipboard content exceeds the server upload limit. Use file import or ask your administrator to increase the limit.' : 'Clipboard content could not be imported. Your CMS clipboard has not changed.')));
                }
                const data = await response.json();
                // Apply the normal CMS copy response without exporting it again.
                originalInvalidateState.call(cms.API.StructureBoard, 'COPY', data);
            } catch (error) {
                message(error.name === 'NotAllowedError' ?
                    'Clipboard access was denied. Your CMS clipboard has not changed.' : error.message, true);
            } finally {
                importing = false;
            }
        }, true);
    };

    // CMS classes are exposed by toolbar.js before its ready callback. No CMS
    // config is needed until a user acts, after toolbar initialization completes.
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize);
    } else {
        initialize();
    }
    window.addEventListener('load', initialize, {once: true});
})();
