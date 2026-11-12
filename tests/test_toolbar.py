from django.test import override_settings

from cms.constants import REFRESH_PAGE
from cms.toolbar.items import LinkItem
from cms.toolbar.utils import get_object_edit_url
from cms.toolbar_pool import toolbar_pool

from .abstract import FunctionalityBaseTestCase


class PluginImporterToolbarTestCase(FunctionalityBaseTestCase):
    @override_settings(DJANGOCMS_TRANSFER_MODE="files-only")
    def test_browser_clipboard_setting_removes_menu_and_script(self):
        with self.login_user_context(self.get_superuser()):
            response = self.client.get(get_object_edit_url(self.page_content))
            toolbar = response.wsgi_request.toolbar
            self.assertNotIn("cms-transfer-clipboard-import", toolbar.render())
            self.assertNotIn("djangocms_transfer/js/clipboard.js", str(toolbar.media))
            self.assertIn("djangocms_transfer/css/transfer.css", str(toolbar.media))

    def test_transfer_mode_controls_page_menu_and_clipboard(self):
        with self.login_user_context(self.get_superuser()):
            for mode in ("all", "files-only", "clipboard-only"):
                with self.subTest(mode=mode), override_settings(DJANGOCMS_TRANSFER_MODE=mode):
                    response = self.client.get(get_object_edit_url(self.page_content))
                    toolbar = response.wsgi_request.toolbar
                    markup = toolbar.render()
                    page_menu = toolbar.get_menu("page")
                    file_items = [
                        item for item in page_menu.items
                        if getattr(item, "name", "") == "Export"
                        or getattr(item, "name", "").startswith("Import")
                    ]
                    self.assertEqual(len(file_items), 0 if mode == "clipboard-only" else 2)
                    self.assertEqual("cms-transfer-clipboard-import" in markup, mode != "files-only")
                    self.assertEqual(
                        "djangocms_transfer/js/clipboard.js" in str(toolbar.media),
                        mode != "files-only",
                    )

    def test_browser_clipboard_menu_and_script_in_edit_mode(self):
        with self.login_user_context(self.get_superuser()):
            response = self.client.get(get_object_edit_url(self.page_content))
            self.assertEqual(response.status_code, 200)
            toolbar = response.wsgi_request.toolbar
            markup = toolbar.render()
            self.assertIn("Import clipboard from browser", markup)
            self.assertIn("cms-transfer-clipboard-import", markup)
            self.assertIn("djangocms_transfer/js/clipboard.js", str(toolbar.media))
            menu = toolbar.get_menu("admin-menu")
            clipboard_item = menu.find_first(LinkItem, extra_classes=["cms-clipboard-trigger"])
            import_item = menu.find_first(LinkItem, extra_classes=["cms-transfer-clipboard-import"])
            clear_item = menu.find_first(LinkItem, extra_classes=["cms-clipboard-empty"])
            self.assertEqual(import_item.index, clipboard_item.index + 1)
            self.assertEqual(clear_item.index, import_item.index + 1)

    def test_browser_clipboard_menu_omitted_without_clipboard_section(self):
        with self.login_user_context(self.get_superuser()):
            response = self.client.get(get_object_edit_url(self.page_content))
            toolbar = response.wsgi_request.toolbar
            toolbar.populate()
            menu = toolbar.get_menu("admin-menu")
            for classes in (["cms-clipboard-trigger"], ["cms-clipboard-empty"]):
                item = menu.find_first(LinkItem, extra_classes=classes)
                menu.remove_item(item.item)
            self.assertNotIn("cms-transfer-clipboard-import", toolbar.render())
            self.assertIsNone(menu.find_first(LinkItem, extra_classes=["cms-transfer-clipboard-import"]))

    def setUp(self):
        super().setUp()
        self.toolbars = toolbar_pool.get_toolbars()
        self.plugin_toolbar = next(
            (toolbar for toolbar in self.toolbars if toolbar.split(".")[-1] == "PluginImporter"),
            None
        )

    def tearDown(self):
        toolbar_pool.clear()
        [toolbar_pool.register(toolbar) for _, toolbar in self.toolbars.items()]

    def _only_plugin_importer_toolbar(self):
        toolbar_pool.clear()
        toolbar_pool.register(self.toolbars[self.plugin_toolbar])

    def test_toolbar_populate_no_page(self):
        self._only_plugin_importer_toolbar()
        with self.login_user_context(self.get_staff_user_with_std_permissions()):
            response = self.client.get("/en/admin/cms/pagecontent/")
            self.assertEqual(response.status_code, 200)
            page_menu = response.wsgi_request.toolbar.get_menu("page")
            self.assertEqual(page_menu, None)

    def test_toolbar_populate_user_cannot_change_page(self):
        self._only_plugin_importer_toolbar()
        with self.login_user_context(self.get_staff_user_with_no_permissions()):
            response = self.client.get(self.get_pages_root())
            self.assertEqual(response.status_code, 200)
            page_menu = response.wsgi_request.toolbar.get_menu("page")
            self.assertEqual(page_menu, None)

    def test_toolbar_populate_page_menu_doesnot_exist(self):
        self._only_plugin_importer_toolbar()
        with self.login_user_context(self.get_staff_user_with_std_permissions()):
            response = self.client.get(self.get_pages_root())
            self.assertEqual(response.status_code, 200)
            page_menu = response.wsgi_request.toolbar.get_menu("page")
            self.assertEqual(page_menu, None)

    def test_toolbar_populate_no_obj_in_toolbar(self):
        self._only_plugin_importer_toolbar()
        with self.login_user_context(self.get_staff_user_with_std_permissions()):
            response = self.client.get(self.get_pages_root())
            self.assertEqual(response.status_code, 200)
            response.wsgi_request.toolbar.obj = None
            page_menu = response.wsgi_request.toolbar.get_menu("page")
            self.assertEqual(page_menu, None)

    def test_toolbar_populate_no_pagecontent_obj(self):
        with self.login_user_context(self.get_staff_user_with_std_permissions()):
            response = self.client.get(self.get_pages_root())
            self.assertEqual(response.status_code, 200)
            response.wsgi_request.toolbar.obj = "not page content"
            page_menu = response.wsgi_request.toolbar.get_menu("page")
            self.assertFalse([
                item for item in page_menu.items
                if getattr(item, "identifier", "") == "Page menu importer break"
            ])
    def test_toolbar_populate_pagecontent_obj(self):
        with self.login_user_context(self.get_staff_user_with_std_permissions()):
            response = self.client.get(self.get_pages_root())
            self.assertEqual(response.status_code, 200)
            page_menu = response.wsgi_request.toolbar.get_menu("page")
            self.assertTrue([
                item for item in page_menu.items
                if getattr(item, "identifier", "") == "Page menu importer break"
            ])
            self.assertTrue([
                item for item in page_menu.items
                if getattr(item, "name", "") == "Export"
            ])
            self.assertTrue([
                item for item in page_menu.items
                if getattr(item, "name", "").startswith("Import")
            ])
            import_item = next(item for item in page_menu.items if getattr(item, "name", "").startswith("Import"))
            self.assertEqual(import_item.on_close, REFRESH_PAGE)
