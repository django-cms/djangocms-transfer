"""Transfer the current user's CMS clipboard across instances."""

import json

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, JsonResponse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from cms.models import Placeholder
from cms.models.placeholderpluginmodel import PlaceholderReference
from cms.plugin_pool import plugin_pool
from cms.toolbar.utils import get_toolbar_from_request
from cms.utils.permissions import has_plugin_permission

from . import browser_clipboard_enabled
from .datastructures import ArchivedPlugin
from .exporter import dump_json, get_placeholder_export_data, get_plugin_export_data
from .importer import import_plugins
from .utils import get_plugin_fields


def parse_clipboard(payload, user):
    if not isinstance(payload, dict) or payload.get("format") != "djangocms-transfer" or payload.get("version") != 1:
        raise ValidationError(_("This is not compatible clipboard content."))
    kind = payload.get("kind")
    rows = payload.get("plugins")
    if kind not in ("plugin", "placeholder") or not isinstance(rows, list) or not rows:
        raise ValidationError(_("The clipboard must contain plugins."))
    plugins = []
    seen = set()
    roots = 0
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(ArchivedPlugin._fields):
            raise ValidationError(_("Invalid plugin data."))
        pk, parent = row["pk"], row["parent_id"]
        if type(pk) is not int or pk <= 0 or pk in seen:
            raise ValidationError(_("Invalid plugin identifier."))
        if parent is not None and (type(parent) is not int or parent not in seen):
            raise ValidationError(_("Invalid plugin tree."))
        if parent is None:
            roots += 1
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
        if not has_plugin_permission(user, plugin_type, "add"):
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
    if kind == "plugin" and roots != 1:
        raise ValidationError(_("A copied plugin must have one root."))
    return kind, plugins


def import_error(message, status=400):
    return JsonResponse({"error": " ".join((message, _("Your CMS clipboard has not changed.")))}, status=status)


@require_http_methods(["GET", "POST"])
@csrf_protect
def clipboard_view(request):
    if not browser_clipboard_enabled():
        return HttpResponseNotFound()
    if not request.user.is_active or not request.user.is_staff:
        raise PermissionDenied
    toolbar = get_toolbar_from_request(request)
    clipboard = toolbar.clipboard
    if clipboard is None:
        raise PermissionDenied
    if request.method == "GET":
        root = clipboard.get_plugins().first()
        if root is None:
            return HttpResponseBadRequest(_("Your CMS clipboard is empty."))
        bound = root.get_bound_plugin()
        if isinstance(bound, PlaceholderReference):
            kind = "placeholder"
            plugins = get_placeholder_export_data(bound.placeholder_ref, root.language)
        else:
            kind = "plugin"
            plugins = get_plugin_export_data(bound)
        response = HttpResponse(dump_json({
            "format": "djangocms-transfer", "version": 1,
            "kind": kind, "plugins": plugins,
        }), content_type="application/json")
        response["Cache-Control"] = "no-store"
        return response
    try:
        payload = json.loads(request.body)
        kind, plugins = parse_clipboard(payload, request.user)
        language = toolbar.request_language
        with transaction.atomic():
            # Lock the stable placeholder row, including when the clipboard is
            # empty, so concurrent imports replace rather than merge content.
            clipboard = Placeholder.objects.select_for_update().get(pk=clipboard.pk)
            clipboard.clear()
            target = clipboard
            if kind == "placeholder":
                reference = PlaceholderReference.objects.create(
                    name=_("Imported placeholder"), plugin_type="PlaceholderPlugin",
                    language=language, placeholder=clipboard,
                )
                target = reference.placeholder_ref
            import_plugins(plugins, target, language)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return import_error(_("The browser clipboard does not contain valid JSON."))
    except ValidationError as error:
        return import_error(" ".join(error.messages))
    except PermissionDenied as error:
        return import_error(str(error), status=403)
    except (ValueError, TypeError, KeyError, AttributeError, IntegrityError):
        return import_error(_("Clipboard content could not be imported."))
    message = _("Browser content imported into your clipboard.")
    messages.success(request, message)
    return JsonResponse({"message": message})
