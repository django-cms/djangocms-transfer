import functools
import json

from django.core.serializers.json import DjangoJSONEncoder

from . import helpers

dump_json = functools.partial(json.dumps, cls=DjangoJSONEncoder)


def export_plugin(plugin):
    data = get_plugin_export_data(plugin)
    return dump_json(data)


def export_placeholder(placeholder, language):
    data = get_placeholder_export_data(placeholder, language)
    return dump_json(data)


def export_page(cms_pagecontent, language):
    data = get_page_export_data(cms_pagecontent, language)
    return dump_json(data)


def get_plugin_export_data(plugin):
    get_data = helpers.get_plugin_data
    descendants = plugin.get_descendants()
    plugin_data = [get_data(plugin=plugin)]
    plugin_data[0]["parent_id"] = None
    plugin_data.extend(
        get_data(plugin) for plugin in helpers.get_bound_plugins(descendants)
    )
    return plugin_data


def get_placeholder_export_data(placeholder, language):
    get_data = helpers.get_plugin_data
    plugins = placeholder.get_plugins(language)
    # The following results in two queries;
    # First all the root plugins are fetched, then all child plugins.
    # This is needed to account for plugin path corruptions.

    return [get_data(plugin) for plugin in helpers.get_bound_plugins(list(plugins))]


def get_page_export_data(cms_pagecontent, language):
    data = []
    placeholders = cms_pagecontent.rescan_placeholders().values()

    for placeholder in list(placeholders):
        plugins = get_placeholder_export_data(placeholder, language)
        data.append({"placeholder": placeholder.slot, "plugins": plugins})
    return data
