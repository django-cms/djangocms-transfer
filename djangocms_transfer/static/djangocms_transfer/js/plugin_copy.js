function getPluginFromEventTarget(tgt) {
    var pluginEl = CMS.$(tgt).closest('.cms-draggable');
    if (!pluginEl.length) return;
    
    const pluginId = (function () {
        const draggables = pluginEl.attr('class').split(/\s+/);
        for (var i=0; i<draggables.length; i++){
            var m = draggables[i].match(/^cms-draggable-(\d+)$/);
            if (m) return parseInt(m[1], 10);
        }
        return null;
    })();

    if (!pluginId) return;
    const plugin = CMS._instances.find(
        plugin => plugin && plugin.options.plugin_id == pluginId
    );
    return plugin
}

CMS.$(window).on('load', function () {
    CMS.$(document).find('.cms-submenu-item a[data-plugin="copy"]').on(
        'click', function (e) {
            e.preventDefault();
            e.stopImmediatePropagation();
	    
	    CMS.Plugin._hideSettingsMenu();

	    var data = getPluginFromEventTarget(this);
	    const options = data.options;
	    console.log("OPTIONS: ", options);
	    var request = {
                type: 'POST',
                url: CMS.API.Helpers.updateUrlWithPath(options.urls.copy_plugin),
                data: {
		    source_placeholder_id: options.placeholder_id,
		    source_plugin_id: options.plugin_id || '',
		    source_language: CMS.config.request.language,
		    target_plugin_id: options.parent || '',
		    target_placeholder_id: options.target,
		    csrfmiddlewaretoken: CMS.config.csrf,
		    target_language: CMS.config.request.language,
		},
                success(response) {
                    // CMS.API.Messages.open({
                    //     message: CMS.config.lang.success
                    // });
		    console.log("RESPONSE: ", response);
                    // if (copyingFromLanguage) {
                    //     CMS.API.StructureBoard.invalidateState('PASTE', $.extend({}, data, response));
                    // } else {
                    //     CMS.API.StructureBoard.invalidateState('COPY', response);
                    // }
                    // CMS.API.locked = false;
                    // hideLoader();
                },
                error(jqXHR) {
                    CMS.API.locked = false;
                    var msg = CMS.config.lang.error;

                    // trigger error
                    CMS.API.Messages.open({
                        message: msg + jqXHR.responseText || jqXHR.status + ' ' + jqXHR.statusText,
                        error: true
                    });
                }
            };
	    CMS.$.ajax(request);

        });
});
