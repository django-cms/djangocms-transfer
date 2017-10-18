from __future__ import unicode_literals
from collections import defaultdict

from django.core import serializers

from .utils import get_plugin_fields, get_plugin_model


def get_bound_plugins(plugins):
    plugins = list(plugins)
    plugin_types_map = defaultdict(list)
    plugin_lookup = {}

    # make a map of plugin types, needed later for downcasting
    for plugin in plugins:
        plugin_types_map[plugin.plugin_type].append(plugin.pk)

    for plugin_type, pks in plugin_types_map.items():
        plugin_model = get_plugin_model(plugin_type)
        plugin_queryset = plugin_model.objects.filter(pk__in=pks)

        # put them in a map so we can replace the base CMSPlugins with their
        # downcasted versions
        for instance in plugin_queryset.iterator():
            plugin_lookup[instance.pk] = instance

    for plugin in plugins:
        yield plugin_lookup.get(plugin.pk, plugin)


def get_plugin_data(plugin, only_meta=False):
    if only_meta:
        custom_data = None
    else:
        plugin_fields = get_plugin_fields(plugin.plugin_type)
        _plugin_data = serializers.serialize('python', (plugin,), fields=plugin_fields)[0]
        custom_data = _plugin_data['fields']

    plugin_data = {
        'pk': plugin.pk,
        'creation_date': plugin.creation_date,
        'position': plugin.position,
        'plugin_type': plugin.plugin_type,
        'parent_id': plugin.parent_id,
        'data': custom_data,
    }
    return plugin_data
