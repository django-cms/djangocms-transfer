from django.forms import Media
from django.utils.http import urlencode
from django.utils.translation import gettext

from cms.models import PageContent
from cms.toolbar_base import CMSToolbar
from cms.toolbar_pool import toolbar_pool
from cms.utils.page_permissions import user_can_change_page
from cms.utils.urlutils import admin_reverse

from . import browser_clipboard_enabled


@toolbar_pool.register
class PluginImporter(CMSToolbar):
    @property
    def media(self):
        return super().media + Media(
            css={"all": ("djangocms_transfer/css/transfer.css",)},
            js=("djangocms_transfer/js/clipboard.js",) if browser_clipboard_enabled() else (),
        )

    def post_template_populate(self):
        menu = self.toolbar.get_menu("admin-menu")
        if menu and self.toolbar.edit_mode_active and browser_clipboard_enabled():
            menu.add_link_item(
                gettext("Import clipboard from browser…"),
                url=admin_reverse("cms_transfer_clipboard"),
                extra_classes=["cms-transfer-clipboard-import"],
            )

    def populate(self):
        # always use draft if we have a page
        page = getattr(self.request, "current_page", None)
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
