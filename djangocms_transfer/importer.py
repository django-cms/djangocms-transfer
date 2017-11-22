from __future__ import unicode_literals

from django.db import transaction

from cms.models import CMSPlugin
from cms.utils.plugins import reorder_plugins

from .utils import get_plugin_class


@transaction.atomic
def import_plugins(plugins, placeholder, language, root_plugin_id=None):
    source_map = {}
    new_plugins = []

    if root_plugin_id:
        root_plugin = CMSPlugin.objects.get(pk=root_plugin_id)
        source_map[root_plugin_id] = root_plugin
    else:
        root_plugin = None

    tree_order = placeholder.get_plugin_tree_order(language, parent_id=root_plugin_id)

    for archived_plugin in plugins:
        if archived_plugin.parent_id:
            parent = source_map[archived_plugin.parent_id]
        else:
            parent = root_plugin

        if parent and parent.__class__ != CMSPlugin:
            parent = parent.cmsplugin_ptr

        plugin = archived_plugin.restore(
            placeholder=placeholder,
            language=language,
            parent=parent,
        )
        source_map[archived_plugin.pk] = plugin

        if parent == root_plugin:
            tree_order.append(plugin.pk)
        new_plugins.append(plugin)

    for new_plugin in new_plugins:
        plugin_class = get_plugin_class(new_plugin.plugin_type)

        if getattr(plugin_class, '_has_do_post_copy', False):
            # getattr is used for django CMS 3.4 compatibility
            # apps on 3.4 wishing to leverage this callback will need
            # to manually set the _has_do_post_copy attribute.
            plugin_class.do_post_copy(new_plugin, source_map)

    reorder_plugins(
        placeholder,
        parent_id=root_plugin_id,
        language=language,
        order=tree_order,
    )
    placeholder.mark_as_dirty(language, clear_cache=False)


@transaction.atomic
def import_plugins_to_page(placeholders, page, language):
    page_placeholders = page.rescan_placeholders()

    for archived_placeholder in placeholders:
        plugins = archived_placeholder.plugins
        placeholder = page_placeholders.get(archived_placeholder.slot)

        if placeholder and plugins:
            import_plugins(plugins, placeholder, language)
