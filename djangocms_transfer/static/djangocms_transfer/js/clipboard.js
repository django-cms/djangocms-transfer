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
        const message = (text, error = false) => cms.API.Messages.open({message: translate(text), error});
        let importing = false;
        let pendingCopy = null;
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
            pending.timeout = setTimeout(cancelPendingCopy, 30000);
            pendingCopy = pending;
        };

        const exportClipboard = async pending => {
            try {
                if (!pending.write && !navigator.clipboard?.writeText) {
                    throw new Error('Browser clipboard access is unavailable');
                }
                const response = await fetch(endpoint, {credentials: 'same-origin', cache: 'no-store'});
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
                message('Copied to CMS clipboard, but the browser clipboard could not be updated.', true);
            }
        };

        // COPY is the CMS completion callback in 4.1+. Keep its return value and
        // synchronous UI update intact. The export runs independently: neither
        // this callback nor CMS.API.locked waits for the extra server roundtrip.
        const originalInvalidateState = cms.StructureBoard.prototype.invalidateState;
        cms.StructureBoard.prototype.invalidateState = function (action, ...args) {
            const result = originalInvalidateState.call(this, action, ...args);
            if (action === 'COPY' && pendingCopy) {
                const pending = pendingCopy;
                clearTimeout(pending.timeout);
                pendingCopy = null;
                void exportClipboard(pending);
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

        // Capture before CMS's toolbar handler navigates to the endpoint.
        document.addEventListener('click', async event => {
            if (!event.target.closest(selector)) {
                return;
            }
            event.preventDefault();
            event.stopImmediatePropagation();
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
                if (payload?.format !== 'djangocms-transfer' || payload.version !== 1) {
                    throw new Error('The browser clipboard does not contain valid transfer JSON.');
                }
                const response = await fetch(endpoint, {
                    method: 'POST', credentials: 'same-origin',
                    headers: {'Content-Type': 'application/json', 'X-CSRFToken': cms.config.csrf},
                    body: text
                });
                if (!response.ok) {
                    throw new Error(response.status === 403 ?
                        'You do not have permission to import these plugins.' :
                        'Clipboard content could not be imported. Your CMS clipboard has not changed.');
                }
                // Refresh clipboard controls and Paste availability from the server.
                window.location.reload();
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
