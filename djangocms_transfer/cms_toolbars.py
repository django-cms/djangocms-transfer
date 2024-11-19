from django.utils.http import urlencode
from django.utils.translation import gettext

from cms.models import PageContent
from cms.toolbar_base import CMSToolbar
from cms.toolbar_pool import toolbar_pool
from cms.utils.page_permissions import user_can_change_page
from cms.utils.urlutils import admin_reverse


@toolbar_pool.register
class PluginImporter(CMSToolbar):
    class Media:
        css = {"all": ("djangocms_transfer/css/transfer.css",)}

    def populate(self):
        # always use draft if we have a page
        page = self.request.current_page

        if not page:
            return

        if not user_can_change_page(self.request.user, page):
            return

        page_menu = self.toolbar.get_menu("page")

        if not page_menu or page_menu.disabled:
            return

        obj = self.toolbar.get_object()
        if not obj:
            return
        if not isinstance(obj, PageContent):
            return

        data = urlencode(
            {
                "language": self.current_lang,
                "cms_pagecontent": obj.pk,
            }
        )

        not_edit_mode = not self.toolbar.edit_mode_active

        page_menu.add_break("Page menu importer break")
        page_menu.add_link_item(
            gettext("Export"),
            url=admin_reverse("cms_export_plugins") + "?" + data,
            disabled=not_edit_mode,
        )
        page_menu.add_modal_item(
            gettext("Import"),
            url=admin_reverse("cms_import_plugins") + "?" + data,
            disabled=not_edit_mode,
            on_close=getattr(self.toolbar, "request_path", self.request.path),
        )
