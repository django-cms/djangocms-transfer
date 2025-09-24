from cms.models import CMSPlugin
from django.db import transaction


@transaction.atomic
def import_plugins(plugins, placeholder, language, root_plugin_id=None):
    source_map = {}
    new_plugins = []

    if root_plugin_id:
        root_plugin = CMSPlugin.objects.get(pk=root_plugin_id)
        source_map[root_plugin_id] = root_plugin
    else:
        root_plugin = None

    for archived_plugin in plugins:
        # custom handling via "get_plugin_data" can lead to "null"-values
        # instead of plugin-dictionaries. We skip those here.
        if archived_plugin is None:
            continue

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

        new_plugins.append((plugin, archived_plugin))

    for new_plugin, _ in new_plugins:
        # Replace all internal child plugins with their new ids
        new_plugin.post_copy(new_plugin, new_plugins)


@transaction.atomic
def import_plugins_to_page(placeholders, pagecontent, language):
    page_placeholders = pagecontent.rescan_placeholders()

    for archived_placeholder in placeholders:
        plugins = archived_placeholder.plugins
        placeholder = page_placeholders.get(archived_placeholder.slot)

        if placeholder and plugins:
            import_plugins(plugins, placeholder, language)
