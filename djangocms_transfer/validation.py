"""Shared validation for file and browser imports."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils.translation import gettext as _

from cms.models import CMSPlugin
from cms.plugin_pool import plugin_pool
from cms.utils.permissions import has_plugin_permission

from .datastructures import ArchivedPlugin
from .utils import get_plugin_fields


def parse_plugins(rows, user=None):
    if not isinstance(rows, (list, tuple)):
        raise ValidationError(_("Invalid plugin data."))
    plugins = []
    seen = set()
    for row in rows:
        if row is None:
            continue
        if isinstance(row, ArchivedPlugin):
            row = row._asdict()
        if not isinstance(row, dict) or set(row) != set(ArchivedPlugin._fields):
            raise ValidationError(_("Invalid plugin data."))
        pk, parent = row["pk"], row["parent_id"]
        if type(pk) is not int or pk <= 0 or pk in seen:
            raise ValidationError(_("Invalid plugin identifier."))
        if parent is not None and (type(parent) is not int or parent not in seen):
            raise ValidationError(_("Invalid plugin tree."))
        plugin_type = row["plugin_type"]
        if not isinstance(plugin_type, str):
            raise ValidationError(_("Invalid plugin type."))
        try:
            plugin_class = plugin_pool.get_plugin(plugin_type)
        except KeyError:
            raise ValidationError(_("The plugin type \"%(plugin_type)s\" is not installed on this site."),
                                  params={"plugin_type": plugin_type})
        if plugin_class.system:
            raise ValidationError(_("The system plugin \"%(plugin_type)s\" cannot be imported."),
                                  params={"plugin_type": plugin_type})
        if user is not None and not has_plugin_permission(user, plugin_type, "add"):
            raise PermissionDenied(_("You do not have permission to add \"%(plugin_type)s\".") %
                                   {"plugin_type": plugin_type})
        data = row["data"]
        allowed = set(get_plugin_fields(plugin_type))
        # Never accept model identity or inheritance links from another site.
        allowed -= {field.name for field in plugin_class.model._meta.fields if field.primary_key}
        if not isinstance(data, dict) or not set(data).issubset(allowed):
            raise ValidationError(_("Invalid plugin fields."))
        if type(row["position"]) is not int or row["position"] < 1:
            raise ValidationError(_("Invalid plugin position."))
        plugins.append(ArchivedPlugin(**row))
        seen.add(pk)
    return plugins
