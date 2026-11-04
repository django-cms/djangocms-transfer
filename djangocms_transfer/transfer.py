"""The shared versioned file and browser clipboard format."""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from .datastructures import ArchivedPlaceholder, ArchivedPlugin
from .validation import parse_plugins


FORMAT = "djangocms-transfer"
VERSION = 1


def transfer_data(kind, data):
    key = "placeholders" if kind == "page" else "plugins"
    return {"format": FORMAT, "version": VERSION, "kind": kind, key: data}


def parse_transfer(payload, user=None):
    """Recognize legacy top-level lists by shape, then validate normally.

    A legacy plugin and a one-root placeholder are indistinguishable; both
    become a plugin tree. Multiple roots become a placeholder. Empty lists
    default to placeholders, and are only useful for file imports.
    """
    if isinstance(payload, list):
        rows = [row for row in payload if row is not None]
        if rows and all(isinstance(row, dict) and set(row) == {"placeholder", "plugins"} for row in rows):
            kind = "page"
        elif all(isinstance(row, dict) and set(row) == set(ArchivedPlugin._fields) for row in rows):
            kind = "plugin" if sum(row["parent_id"] is None for row in rows) == 1 else "placeholder"
        else:
            raise ValidationError(_("Unrecognized legacy transfer data."))
    elif isinstance(payload, dict):
        if payload.get("format") != FORMAT or type(payload.get("version")) is not int or payload["version"] != VERSION:
            raise ValidationError(_("This is not compatible transfer content."))
        kind = payload.get("kind")
        rows = payload.get("placeholders" if kind == "page" else "plugins")
    else:
        raise ValidationError(_("This is not compatible transfer content."))

    if kind == "page":
        if not isinstance(rows, list):
            raise ValidationError(_("Invalid page data."))
        placeholders = []
        slots = set()
        all_plugins = []
        for row in rows:
            if (not isinstance(row, dict) or set(row) != {"placeholder", "plugins"}
                    or not isinstance(row["placeholder"], str) or row["placeholder"] in slots):
                raise ValidationError(_("Invalid page placeholder data."))
            slots.add(row["placeholder"])
            plugins = parse_plugins(row["plugins"], user)
            placeholders.append(ArchivedPlaceholder(row["placeholder"], plugins))
            all_plugins.extend(plugins)
        # Identifiers must also be unique across the page's placeholders.
        parse_plugins(all_plugins, user)
        return kind, placeholders
    if kind not in ("plugin", "placeholder"):
        raise ValidationError(_("Invalid transfer kind."))
    plugins = parse_plugins(rows, user)
    if plugins and kind == "plugin" and sum(plugin.parent_id is None for plugin in plugins) != 1:
        raise ValidationError(_("A copied plugin must have one root."))
    return kind, plugins
