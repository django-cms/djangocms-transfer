import logging

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DataError, IntegrityError
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.urls import re_path, reverse
from django.utils.decorators import method_decorator
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_protect

from cms.constants import REFRESH_PAGE
from cms.plugin_base import CMSPluginBase, PluginMenuItem
from cms.plugin_pool import plugin_pool
from cms.utils import get_language_from_request
from cms.utils.urlutils import admin_reverse

from . import file_transfer_enabled
from .clipboard import clipboard_view
from .forms import ExportImportForm, PluginExportForm, PluginImportForm


class PluginImporter(CMSPluginBase):
    system = True
    render_plugin = False

    def get_plugin_urls(self):
        urlpatterns = [
            re_path(r"^browser-clipboard/$", clipboard_view, name="cms_transfer_clipboard"),
            re_path(
                r"^export-plugins/$",
                self.export_plugins_view,
                name="cms_export_plugins",
            ),
            re_path(
                r"^import-plugins/$",
                self.import_plugins_view,
                name="cms_import_plugins",
            ),
        ]
        return urlpatterns

    @staticmethod
    def _get_extra_menu_items(query_params, request):
        if not file_transfer_enabled():
            return []

        data = urlencode({
            "language": get_language_from_request(request),
            **query_params
        })
        return [
            PluginMenuItem(
                _("Export plugins"),
                admin_reverse("cms_export_plugins") + "?" + data,
                data={},
                action="none",
                attributes={
                    "icon": "export",
                },
            ),
            PluginMenuItem(
                _("Import plugins"),
                admin_reverse("cms_import_plugins") + "?" + data,
                data={},
                action="modal",
                attributes={
                    "icon": "import",
                    "on-close": REFRESH_PAGE,
                },
            ),
        ]

    @classmethod
    def get_extra_plugin_menu_items(cls, request, plugin):
        if plugin.plugin_type == cls.__name__:
            return

        data = {"plugin": plugin.pk}
        return cls._get_extra_menu_items(data, request)

    @classmethod
    def get_extra_placeholder_menu_items(cls, request, placeholder):  # noqa
        data = {"placeholder": placeholder.pk}
        return cls._get_extra_menu_items(data, request)

    @classmethod
    @method_decorator(csrf_protect)
    def import_plugins_view(cls, request):
        if not request.user.is_staff:
            raise PermissionDenied

        new_form = ExportImportForm(request.GET or None)

        if new_form.is_valid():
            initial_data = new_form.cleaned_data
        else:
            initial_data = None

        if request.method == "GET" and not new_form.is_valid():
            return HttpResponseBadRequest(_("Form received unexpected values."))

        import_form = PluginImportForm(
            data=request.POST or None,
            files=request.FILES or None,
            initial=initial_data,
            request=request,
        )

        valid = import_form.is_valid()
        if valid:
            try:
                import_form.run_import()
            except PermissionDenied:
                raise
            except ValidationError as error:
                import_form.add_error(None, ValidationError(error.messages))
                valid = False
            except (DataError, IntegrityError, OverflowError):
                import_form.add_error(None, _("Plugin values could not be stored."))
                valid = False
            except Exception:
                logging.getLogger(__name__).exception("Plugin file import failed")
                import_form.add_error(None, _("Plugin import failed. No content was changed."))
                valid = False

        if not valid:
            opts = cls.model._meta
            context = {
                "form": import_form,
                "has_change_permission": True,
                "opts": opts,
                "root_path": reverse("admin:index"),
                "is_popup": True,
                "app_label": opts.app_label,
                "media": (cls().media + import_form.media),
            }
            return render(request, "djangocms_transfer/import_plugins.html", context)

        return render(request, "djangocms_transfer/placeholder_close_frame.html", {})

    @classmethod
    def export_plugins_view(cls, request):
        if not request.user.is_staff:
            raise PermissionDenied

        form = PluginExportForm(request.GET or None)

        if not form.is_valid():
            return HttpResponseBadRequest(_("Form received unexpected values."))

        # TODO: Check permissions
        filename = form.get_filename()
        response = HttpResponse(form.run_export(), content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename={filename}'
        return response


plugin_pool.register_plugin(PluginImporter)
