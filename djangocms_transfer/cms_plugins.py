from __future__ import unicode_literals
import json

from django.conf.urls import url
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.utils.http import urlencode
from django.utils.translation import ugettext_lazy as _

from cms.plugin_base import CMSPluginBase
from cms.plugin_base import PluginMenuItem
from cms.plugin_pool import plugin_pool
from cms.utils import get_language_from_request
from cms.utils.urlutils import admin_reverse

from .compat import LTE_CMS_3_4
from .forms import (ExportImportForm, PluginExportForm, PluginImportForm)


class PluginImporter(CMSPluginBase):
    system = True
    render_plugin = False

    def get_plugin_urls(self):
        urlpatterns = [
            url(r'^export-plugins/$', self.export_plugins_view, name='cms_export_plugins'),
            url(r'^import-plugins/$', self.import_plugins_view, name='cms_import_plugins'),
        ]
        return urlpatterns

    def get_extra_placeholder_menu_items(self, request, placeholder):
        # django-cms 3.4 compatibility
        return self.get_extra_placeholder_menu_items(request, placeholder)

    def get_extra_global_plugin_menu_items(self, request, plugin):
        # django-cms 3.4 compatibility
        return self.get_extra_plugin_menu_items(request, plugin)

    @classmethod
    def get_extra_plugin_menu_items(cls, request, plugin):
        if plugin.plugin_type == cls.__name__:
            return

        data = urlencode({
            'language': get_language_from_request(request),
            'plugin': plugin.pk,
        })
        return [
            PluginMenuItem(
                _("Export plugins"),
                admin_reverse('cms_export_plugins') + '?' + data,
                data={},
                action='none',
                attributes={
                    'icon': 'export',
                },
            ),
            PluginMenuItem(
                _("Import plugins"),
                admin_reverse('cms_import_plugins') + '?' + data,
                data={},
                action='modal',
                attributes={
                    'icon': 'import',
                },
            ),
        ]

    @classmethod
    def get_extra_placeholder_menu_items(cls, request, placeholder):
        data = urlencode({
            'language': get_language_from_request(request),
            'placeholder': placeholder.pk,
        })
        return [
            PluginMenuItem(
                _("Export plugins"),
                admin_reverse('cms_export_plugins') + '?' + data,
                data={},
                action='none',
                attributes={
                    'icon': 'export',
                },
            ),
            PluginMenuItem(
                _("Import plugins"),
                admin_reverse('cms_import_plugins') + '?' + data,
                data={},
                action='modal',
                attributes={
                    'icon': 'import',
                },
            )
        ]

    @classmethod
    def import_plugins_view(cls, request):
        if not request.user.is_staff:
            raise PermissionDenied

        new_form = ExportImportForm(request.GET or None)

        if new_form.is_valid():
            initial_data = new_form.cleaned_data
        else:
            initial_data = None

        if request.method == 'GET' and not new_form.is_valid():
            return HttpResponseBadRequest('Form received unexpected values')

        import_form = PluginImportForm(
            data=request.POST or None,
            files=request.FILES or None,
            initial=initial_data,
        )

        if not import_form.is_valid():
            opts = cls.model._meta
            context = {
                'form': import_form,
                'has_change_permission': True,
                'opts': opts,
                'root_path': reverse('admin:index'),
                'is_popup': True,
                'app_label': opts.app_label,
                'media': (cls().media + import_form.media),
            }
            return render(request, 'djangocms_transfer/import_plugins.html', context)

        plugin = import_form.cleaned_data.get('plugin')
        language = import_form.cleaned_data['language']

        if plugin:
            root_id = plugin.pk
            placeholder = plugin.placeholder
        else:
            root_id = None
            placeholder = import_form.cleaned_data.get('placeholder')

        if not placeholder:
            # Page placeholders/plugins import
            # TODO: Check permissions
            import_form.run_import()
            return HttpResponse('<div><div class="messagelist"><div class="success"></div></div></div>')

        tree_order = placeholder.get_plugin_tree_order(language, parent_id=root_id)
        # TODO: Check permissions
        import_form.run_import()

        if LTE_CMS_3_4:
            return HttpResponse('<div><div class="messagelist"><div class="success"></div></div></div>')

        if plugin:
            new_plugins = plugin.reload().get_descendants().exclude(pk__in=tree_order)
            return plugin.get_plugin_class_instance().render_close_frame(request, obj=new_plugins[0])

        from cms.toolbar.utils import get_plugin_tree_as_json

        # Placeholder plugins import
        new_plugins = placeholder.get_plugins(language).exclude(pk__in=tree_order)
        data = json.loads(get_plugin_tree_as_json(request, list(new_plugins)))
        data['plugin_order'] = tree_order + ['__COPY__']
        data['target_placeholder_id'] = placeholder.pk
        context = {'structure_data': json.dumps(data)}
        return render(request, 'djangocms_transfer/placeholder_close_frame.html', context)

    @classmethod
    def export_plugins_view(cls, request):
        if not request.user.is_staff:
            raise PermissionDenied

        form = PluginExportForm(request.GET or None)

        if not form.is_valid():
            return HttpResponseBadRequest('Form received unexpected values')

        # TODO: Check permissions
        filename = form.get_filename()
        response = HttpResponse(form.run_export(), content_type='application/json')
        response['Content-Disposition'] = 'attachment; filename={}'.format(filename)
        return response


plugin_pool.register_plugin(PluginImporter)
