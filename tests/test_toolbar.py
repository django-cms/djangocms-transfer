from cms.toolbar_pool import toolbar_pool

from .abstract import FunctionalityBaseTestCase


class PluginImporterToolbarTestCase(FunctionalityBaseTestCase):
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
