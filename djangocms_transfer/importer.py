from __future__ import unicode_literals

from cms.models import CMSPlugin
from cms.utils.plugins import reorder_plugins


def import_plugins(plugins, placeholder, language, root_plugin_id=None):
    plugins_by_id = {}

    if root_plugin_id:
        root_plugin = CMSPlugin.objects.get(pk=root_plugin_id)
        plugins_by_id[root_plugin_id] = root_plugin
    else:
        root_plugin = None

    tree_order = placeholder.get_plugin_tree_order(language, parent_id=root_plugin_id)

    for archived_plugin in plugins:
        if archived_plugin.parent_id:
            parent = plugins_by_id[archived_plugin.parent_id]
        else:
            parent = root_plugin

        plugin = archived_plugin.restore(
            placeholder=placeholder,
            language=language,
            parent=parent,
        )
        plugins_by_id[archived_plugin.pk] = plugin

        if parent == root_plugin:
            tree_order.append(plugin.pk)

    reorder_plugins(
        placeholder,
        parent_id=root_plugin_id,
        language=language,
        order=tree_order,
    )
    placeholder.mark_as_dirty(language, clear_cache=False)


def import_plugins_to_page(placeholders, page, language):
    page_placeholders = page.rescan_placeholders()

    for archived_placeholder in placeholders:
        plugins = archived_placeholder.plugins
        placeholder = page_placeholders.get(archived_placeholder.slot)

        if placeholder and plugins:
            import_plugins(plugins, placeholder, language)
