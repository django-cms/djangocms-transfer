import json

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from cms.models import CMSPlugin, PageContent, Placeholder

from .exporter import export_page, export_placeholder, export_plugin
from .importer import import_plugins, import_plugins_to_page
from .transfer import parse_transfer


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
    cms_pagecontent = forms.ModelChoiceField(
        queryset=PageContent.admin_manager.latest_content(),
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

        plugin = self.cleaned_data.get("plugin")
        placeholder = self.cleaned_data.get("placeholder")
        cms_pagecontent = self.cleaned_data.get("cms_pagecontent")

        if not any([plugin, placeholder, cms_pagecontent]):
            message = _("A plugin, placeholder or page is required.")
            raise forms.ValidationError(message)

        if cms_pagecontent and (plugin or placeholder):
            message = _(
                "Plugins can be imported to pages, plugins or placeholders. Not all three."
            )
            raise forms.ValidationError(message)

        if placeholder and (cms_pagecontent or plugin):
            message = _(
                "Plugins can be imported to pages, plugins or placeholders. Not all three."
            )
            raise forms.ValidationError(message)

        if plugin and (cms_pagecontent or placeholder):
            message = _(
                "Plugins can be imported to pages, plugins or placeholders. Not all three."
            )
            raise forms.ValidationError(message)

        plugin_is_bound = False
        if plugin:
            plugin_is_bound = plugin.get_bound_plugin()

        if plugin and not plugin_is_bound:
            raise ValidationError("Plugin is unbound.")
        return self.cleaned_data


class PluginExportForm(ExportImportForm):
    def get_filename(self):
        data = self.cleaned_data
        language = data["language"]
        cms_pagecontent = data["cms_pagecontent"]
        plugin = data["plugin"]
        placeholder = data["placeholder"]

        if cms_pagecontent:
            page = cms_pagecontent.page
            suffix = ""
        elif placeholder or plugin:
            source_placeholder = placeholder or plugin.placeholder
            page = source_placeholder.page
            cms_pagecontent = source_placeholder.source
            suffix = slugify(placeholder.slot if placeholder else plugin.get_short_description())
        else:
            return "plugins.json"

        if page is None:
            return "plugins.json"
        # Draft slugs belong to PageContent on newer CMS versions and may not
        # have a routable PageUrl yet. CMS 4.1 stores slugs on PageUrl only.
        slug = getattr(cms_pagecontent, "slug", None) if isinstance(cms_pagecontent, PageContent) else None
        slug = slug or page.get_slug(language=language) or f"page-{page.pk}"
        return f"{slug}_{suffix}.json" if suffix else f"{slug}.json"

    def run_export(self):
        data = self.cleaned_data
        language = data["language"]
        plugin = data["plugin"]
        placeholder = data["placeholder"]

        if plugin:
            return export_plugin(plugin.get_bound_plugin())

        if placeholder:
            return export_placeholder(placeholder, language)
        return export_page(data["cms_pagecontent"], language)


class PluginImportForm(ExportImportForm):
    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)

    import_file = forms.FileField(
        required=True,
        widget=forms.FileInput(attrs={"accept": "application/json"}),
    )

    def clean(self):
        super().clean()
        if self.errors:
            return self.cleaned_data

        import_file = self.cleaned_data["import_file"]

        try:
            payload = json.loads(import_file.read().decode("utf-8"))
        except (ValueError, TypeError):
            raise ValidationError("File is not valid")

        kind, data = parse_transfer(payload, getattr(self.request, "user", None))
        page_import = bool(self.cleaned_data["cms_pagecontent"])
        if page_import != (kind == "page") and not (page_import and payload == []):
            raise ValidationError("Incorrect json format used.")

        self.cleaned_data["import_data"] = data
        return self.cleaned_data

    def run_import(self):
        data = self.cleaned_data
        language = data["language"]
        target_page = data["cms_pagecontent"]
        target_plugin = data["plugin"]
        target_placeholder = data["placeholder"]

        if target_plugin:
            target_plugin_id = target_plugin.pk
            target_placeholder = target_plugin.placeholder
        else:
            target_plugin_id = None

        if target_page:
            import_plugins_to_page(
                placeholders=data["import_data"],
                pagecontent=target_page,
                language=language,
                request=self.request,
            )
        else:
            import_plugins(
                plugins=data["import_data"],
                placeholder=target_placeholder,
                language=language,
                root_plugin_id=target_plugin_id,
                request=self.request,
            )
