import functools
import json

from cms.utils.plugins import get_bound_plugins
from django.conf import settings
from django.core import serializers
from django.core.serializers.json import DjangoJSONEncoder

from . import get_serializer_name
from .utils import get_plugin_fields

dump_json = functools.partial(json.dumps, cls=DjangoJSONEncoder)


def get_plugin_data(plugin, only_meta=False):
    if only_meta:
        custom_data = None
    else:
        plugin_fields = get_plugin_fields(plugin.plugin_type)
        _plugin_data = serializers.serialize(
            get_serializer_name(), (plugin,), fields=plugin_fields
        )[0]
        custom_data = _plugin_data["fields"]

    plugin_data = {
        "pk": plugin.pk,
        "creation_date": plugin.creation_date,
        "position": plugin.position,
        "plugin_type": plugin.plugin_type,
        "parent_id": plugin.parent_id,
        "data": custom_data,
    }

    gpd = getattr(settings, "DJANGOCMS_TRANSFER_PROCESS_EXPORT_PLUGIN_DATA", None)
    if gpd:
        module, function = gpd.rsplit(".", 1)
        return getattr(__import__(module, fromlist=[""]), function)(plugin, plugin_data)
    else:
        return plugin_data

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
    descendants = plugin.get_descendants()
    plugin_data = [get_plugin_data(plugin=plugin)]
    plugin_data[0]["parent_id"] = None
    plugin_data.extend(
        get_plugin_data(plugin) for plugin in get_bound_plugins(descendants)
    )
    return plugin_data


def get_placeholder_export_data(placeholder, language):
    plugins = placeholder.get_plugins(language)
    # The following results in two queries;
    # First all the root plugins are fetched, then all child plugins.
    # This is needed to account for plugin path corruptions.

    return [get_plugin_data(plugin) for plugin in get_bound_plugins(list(plugins))]


def get_page_export_data(cms_pagecontent, language):
    data = []
    placeholders = cms_pagecontent.rescan_placeholders().values()

    for placeholder in list(placeholders):
        plugins = get_placeholder_export_data(placeholder, language)
        data.append({"placeholder": placeholder.slot, "plugins": plugins})
    return data
