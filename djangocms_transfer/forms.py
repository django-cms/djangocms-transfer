from __future__ import unicode_literals
import json

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from cms.models import CMSPlugin, Placeholder, Page

from .datastructures import ArchivedPlaceholder, ArchivedPlugin
from .exporter import export_plugin, export_page, export_placeholder
from .importer import import_plugins, import_plugins_to_page


def _object_version_data_hook(data, for_page=False):
    if not data:
        return data

    if 'plugins' in data:
        return ArchivedPlaceholder(
            slot=data['placeholder'],
            plugins=data['plugins'],
        )

    if 'plugin_type' in data:
        return ArchivedPlugin(**data)
    return data


def _get_parsed_data(file_obj, for_page=False):
    raw = file_obj.read().decode('utf-8')
    return json.loads(raw, object_hook=_object_version_data_hook)


class ExportImportForm(forms.Form):
    plugin = forms.ModelChoiceField(
        CMSPlugin.objects.all(),
        required=False,
        widget=forms.HiddenInput(),
    )
    placeholder = forms.ModelChoiceField(
        queryset=Placeholder.objects.all(),
        required=False,
        widget=forms.HiddenInput(),
    )
    cms_page = forms.ModelChoiceField(
        queryset=Page.objects.drafts(),
        required=False,
        widget=forms.HiddenInput(),
    )
    language = forms.ChoiceField(
        choices=settings.LANGUAGES,
        required=True,
        widget=forms.HiddenInput(),
    )

    def clean(self):
        if self.errors:
            return self.cleaned_data

        plugin = self.cleaned_data.get('plugin')
        placeholder = self.cleaned_data.get('placeholder')
        cms_page = self.cleaned_data.get('cms_page')

        if not any([plugin, placeholder, cms_page]):
            message = 'A plugin, placeholder or page is required'
            raise forms.ValidationError(message)

        if cms_page and (plugin or placeholder):
            message = 'Plugins can be imported to pages, plugins or placeholders. Not all three.'
            raise forms.ValidationError(message)

        if placeholder and (cms_page or plugin):
            message = 'Plugins can be imported to pages, plugins or placeholders. Not all three.'
            raise forms.ValidationError(message)

        if plugin and (cms_page or placeholder):
            message = 'Plugins can be imported to pages, plugins or placeholders. Not all three.'
            raise forms.ValidationError(message)

        if plugin:
            plugin_model = plugin.get_plugin_class().model
            plugin_is_bound = plugin_model.objects.filter(cmsplugin_ptr=plugin).exists()
        else:
            plugin_is_bound = False

        if plugin and not plugin_is_bound:
            raise ValidationError('Plugin is unbound.')
        return self.cleaned_data


class PluginExportForm(ExportImportForm):

    def get_filename(self):
        if self.cleaned_data.get('cms_page'):
            return 'cms_page_plugins.json'
        return 'plugins.json'

    def run_export(self):
        data = self.cleaned_data
        language = data['language']
        plugin = data['plugin']
        placeholder = data['placeholder']

        if plugin:
            return export_plugin(plugin.get_bound_plugin())

        if placeholder:
            return export_placeholder(placeholder, language)
        return export_page(data['cms_page'], language)


class PluginImportForm(ExportImportForm):

    import_file = forms.FileField(required=True)

    def clean(self):
        if self.errors:
            return self.cleaned_data

        import_file = self.cleaned_data['import_file']

        try:
            data = _get_parsed_data(import_file)
        except (ValueError, TypeError):
            raise ValidationError('File is not valid')

        first_item = data[0]
        is_placeholder = isinstance(first_item, ArchivedPlaceholder)
        page_import = bool(self.cleaned_data['cms_page'])
        plugins_import = not page_import

        if (is_placeholder and plugins_import) or (page_import and not is_placeholder):
            raise ValidationError('Incorrect json format used.')

        self.cleaned_data['import_data'] = data
        return self.cleaned_data

    def run_import(self):
        data = self.cleaned_data
        language = data['language']
        target_page = data['cms_page']
        target_plugin = data['plugin']
        target_placeholder = data['placeholder']

        if target_plugin:
            target_plugin_id = target_plugin.pk
            target_placeholder = target_plugin.placeholder
        else:
            target_plugin_id = None

        if target_page:
            import_plugins_to_page(
                placeholders=data['import_data'],
                page=target_page,
                language=language,
            )
        else:
            import_plugins(
                plugins=data['import_data'],
                placeholder=target_placeholder,
                language=language,
                root_plugin_id=target_plugin_id,
            )
