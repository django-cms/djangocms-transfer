"""Transfer the current user's CMS clipboard across instances."""

import json
import logging

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, RequestDataTooBig, ValidationError
from django.db import DataError, IntegrityError, transaction
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, JsonResponse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from cms.models import Placeholder
from cms.models.placeholderpluginmodel import PlaceholderReference
from cms.toolbar.utils import get_toolbar_from_request

from . import browser_clipboard_enabled
from .exporter import dump_json, get_placeholder_export_data, get_plugin_export_data
from .importer import import_plugins
from .transfer import parse_transfer, transfer_data


try:
    from cms.toolbar.utils import get_plugin_tree
except ImportError:  # django CMS 4.1
    from cms.toolbar.utils import get_plugin_tree_as_json

    def get_plugin_tree(request, plugins):
        return json.loads(get_plugin_tree_as_json(request, plugins))


def parse_clipboard(payload, user):
    kind, plugins = parse_transfer(payload, user)
    if kind == "page":
        # A CMS clipboard has one tree, so page slots become one placeholder.
        plugins = [plugin for placeholder in plugins for plugin in placeholder.plugins]
        kind = "placeholder"
    if not plugins:
        raise ValidationError(_("The clipboard must contain plugins."))
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
        return export_clipboard(request, clipboard)
    try:
        upload = request.FILES.get("clipboard") if request.content_type == "multipart/form-data" else None
        limit = getattr(settings, "DJANGOCMS_TRANSFER_MAX_CLIPBOARD_SIZE", 20 * 1024 * 1024)
        if upload is not None:
            if limit is not None and upload.size > limit:
                return import_error(_("Clipboard content exceeds the configured clipboard upload limit."), status=413)
            payload = json.load(upload)
        else:
            raw = request.body
            if limit is not None and len(raw) > limit:
                return import_error(_("Clipboard content exceeds the configured clipboard upload limit."), status=413)
            payload = json.loads(raw)
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
            import_plugins(plugins, target, language, request=request, permission_placeholder=clipboard)
            data = get_plugin_tree(request, [clipboard.get_plugins(language).first()])
    except RequestDataTooBig:
        limit = settings.DATA_UPLOAD_MAX_MEMORY_SIZE
        return import_error(_("Clipboard content exceeds the upload limit (%(limit)s bytes). Use file import or ask your administrator to increase DATA_UPLOAD_MAX_MEMORY_SIZE.") % {"limit": limit}, status=413)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return import_error(_("The browser clipboard does not contain valid JSON."))
    except ValidationError as error:
        return import_error(" ".join(error.messages))
    except PermissionDenied as error:
        return import_error(str(error), status=403)
    except (DataError, IntegrityError, OverflowError):
        return import_error(_("Plugin values could not be stored."))
    except Exception:
        logging.getLogger(__name__).exception("Browser clipboard import failed")
        return import_error(_("Clipboard import failed unexpectedly."), status=500)
    message = _("Browser content imported into your clipboard.")
    messages.success(request, message)
    return JsonResponse({**data, "message": message})


@transaction.atomic
def export_clipboard(request, clipboard):
    root = clipboard.get_plugins().select_for_update().first()
    if root is None:
        return HttpResponseBadRequest(_("Your CMS clipboard is empty."))
    expected = request.GET.get("plugin")
    if expected is not None and expected != str(root.pk):
        return JsonResponse({"error": _("The CMS clipboard changed before this copy could be exported. Copy again.")}, status=409)
    bound = root.get_bound_plugin()
    if isinstance(bound, PlaceholderReference):
        kind = "placeholder"
        plugins = get_placeholder_export_data(bound.placeholder_ref, root.language)
    else:
        kind = "plugin"
        plugins = get_plugin_export_data(bound)
    if not any(plugin is not None for plugin in plugins):
        return JsonResponse({"error": _("The copied content contains no transferable plugins.")}, status=400)
    response = HttpResponse(dump_json(transfer_data(kind, plugins)), content_type="application/json")
    response["Cache-Control"] = "no-store"
    return response
