from __future__ import unicode_literals
from collections import defaultdict

from django.core import serializers

from .utils import get_plugin_fields, get_plugin_model


def get_bound_plugins(plugins):
    # COMPAT: CMS<3.5
    # When we drop support for CMS3.4 we can replace all this method by
    # from cms.utils.plugins import get_bound_plugins
    plugin_types_map = defaultdict(list)
    plugin_ids = []
    plugin_lookup = {}

    # make a map of plugin types, needed later for downcasting
    for plugin in plugins:
        plugin_ids.append(plugin.pk)
        plugin_types_map[plugin.plugin_type].append(plugin.pk)

    for plugin_type, pks in plugin_types_map.items():
        plugin_model = get_plugin_model(plugin_type)
        plugin_queryset = plugin_model.objects.filter(pk__in=pks)

        # put them in a map so we can replace the base CMSPlugins with their
        # downcasted versions
        for instance in plugin_queryset.iterator():
            plugin_lookup[instance.pk] = instance

    for plugin in plugins:
        parent_not_available = (not plugin.parent_id or plugin.parent_id not in plugin_ids)
        # The plugin either has no parent or needs to have a non-ghost parent
        valid_parent = (parent_not_available or plugin.parent_id in plugin_lookup)

        if valid_parent and plugin.pk in plugin_lookup:
            yield plugin_lookup[plugin.pk]


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
