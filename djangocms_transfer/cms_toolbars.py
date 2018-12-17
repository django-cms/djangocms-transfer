# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.utils.http import urlencode
from django.utils.translation import ugettext

from cms.api import get_page_draft
from cms.utils.page_permissions import user_can_change_page
from cms.toolbar_base import CMSToolbar
from cms.toolbar_pool import toolbar_pool
from cms.utils.urlutils import admin_reverse

from .compat import GTE_CMS_3_6


@toolbar_pool.register
class PluginImporter(CMSToolbar):
    class Media:
        css = {
            'all': ('djangocms_transfer/css/transfer.css',)
        }

    def populate(self):
        # always use draft if we have a page
        page = get_page_draft(self.request.current_page)

        if not page:
            return

        if not user_can_change_page(self.request.user, page):
            return

        page_menu = self.toolbar.get_menu('page')

        if not page_menu or page_menu.disabled:
            return

        data = urlencode({
            'language': self.current_lang,
            'cms_page': page.pk,
        })

        if GTE_CMS_3_6:
            not_edit_mode = not self.toolbar.toolbar_language
        else:
            not_edit_mode = not self.toolbar.language

        page_menu.add_break('Page menu importer break')
        page_menu.add_link_item(
            ugettext('Export'),
            url=admin_reverse('cms_export_plugins') + '?' + data,
            disabled=not_edit_mode,
        )
        page_menu.add_modal_item(
            ugettext('Import'),
            url=admin_reverse('cms_import_plugins') + '?' + data,
            disabled=not_edit_mode,
            on_close=getattr(self.toolbar, 'request_path', self.request.path),
        )
