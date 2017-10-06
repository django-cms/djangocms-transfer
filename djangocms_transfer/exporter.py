from __future__ import unicode_literals
import json
import functools
from collections import defaultdict, deque

from django.core.serializers.json import DjangoJSONEncoder

from cms.models import CMSPlugin

from . import helpers
from .config_registry import registry


dump_json = functools.partial(json.dumps, cls=DjangoJSONEncoder)


def export_plugin(plugin):
    data = get_plugin_export_data(plugin)
    return dump_json(data)


def export_placeholder(placeholder, language):
    data = get_placeholder_export_data(placeholder, language)
    return dump_json(data)


def export_page(cms_page, language):
    data = get_page_export_data(cms_page, language)
    return dump_json(data)


def get_plugin_export_data(plugin):
    plugin_ids = []
    export_data = {}
    _registry = registry
    relationships = defaultdict(set)
    plugins = CMSPlugin.get_tree(plugin).order_by('path')

    for plugin in helpers.get_bound_plugins(plugins):
        model = plugin.__class__
        config = _registry.get_config(model)
        data = config.get_export_data(plugin)
        data['position'] = plugin.position
        data['plugin_type'] = plugin.plugin_type
        data['parent_id'] = plugin.parent_id
        plugin_id = '{}.{}'.format(data['model'], plugin.pk)
        plugin_ids.append(plugin_id)
        export_data[plugin_id] = data

        for field_name, ids in data['related_data'].items():
            field = model._meta.get_field(field_name)
            relationships[field.rel.to].add(ids)

    dependencies = deque(list(relationships.keys()))

    while dependencies:
        model = dependencies.pop()
        config = _registry.get_config(model)
        object_ids = relationships.pop(model)
        objects = model.objects.filter(pk__in=object_ids)

        for obj in objects.iterator():
            data = config.get_export_data(obj)
            obj_id = '{}.{}'.format(data['model'], plugin.pk)

            for field_name, ids in data['related_data'].items():
                field = model._meta.get_field(field_name)
                dep_model = field.rel.to
                relationships[dep_model].add(ids)

                if dep_model not in dependencies:
                    dependencies.append(dep_model)
            export_data[obj_id] = data
    return {'plugin_ids': plugin_ids, 'data': export_data}


def get_placeholder_export_data(placeholder, language):
    get_data = helpers.get_plugin_data
    plugins = placeholder.get_plugins(language)
    plugin_data = [get_data(plugin) for plugin in helpers.get_bound_plugins(plugins)]
    return plugin_data


def get_page_export_data(cms_page, language):
    data = []
    placeholders = cms_page.rescan_placeholders().values()

    for placeholder in list(placeholders):
        plugins = get_placeholder_export_data(placeholder, language)
        data.append({'placeholder': placeholder.slot, 'plugins': plugins})
    return data
