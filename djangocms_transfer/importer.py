from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from cms.models import CMSPlugin

from .validation import parse_plugins


@transaction.atomic
def import_plugins(plugins, placeholder, language, root_plugin_id=None, user=None, request=None,
                   permission_placeholder=None):
    user = user or getattr(request, "user", None)
    plugins = parse_plugins(plugins, user)
    # A private clipboard wrapper is authorized through the user's actual
    # clipboard, rather than requiring change permission on the system plugin.
    permission_target = permission_placeholder or placeholder
    if user is not None and (not permission_target.has_add_plugins_permission(user, plugins)
                             or not permission_target.check_source(user)):
        raise PermissionDenied(_("You do not have permission to import into this placeholder."))
    source_map = {}
    new_plugins = []

    if root_plugin_id:
        try:
            root_plugin = CMSPlugin.objects.get(pk=root_plugin_id, placeholder=placeholder, language=language)
        except CMSPlugin.DoesNotExist:
            raise ValidationError(_("The parent plugin does not belong to the destination placeholder and language."))
        source_map[root_plugin_id] = root_plugin
    else:
        root_plugin = None

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
            request=request,
        )
        source_map[archived_plugin.pk] = plugin

        new_plugins.append((plugin, archived_plugin))

    for new_plugin, archived_plugin in new_plugins:
        # Replace all internal child plugins with their new ids
        new_plugin.post_copy(new_plugin, new_plugins)


@transaction.atomic
def import_plugins_to_page(placeholders, pagecontent, language, user=None, request=None):
    page_placeholders = pagecontent.rescan_placeholders()

    for archived_placeholder in placeholders:
        plugins = archived_placeholder.plugins
        placeholder = page_placeholders.get(archived_placeholder.slot)

        if placeholder and plugins:
            import_plugins(plugins, placeholder, language, user=user, request=request)
