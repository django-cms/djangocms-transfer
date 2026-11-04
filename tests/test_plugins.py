import json

from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile

from cms.constants import REFRESH_PAGE
from cms.plugin_pool import plugin_pool
from cms.utils.urlutils import admin_reverse

from .abstract import FunctionalityBaseTestCase


class PluginImporterTestCase(FunctionalityBaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = self._create_user("test", True, True)
        self.plugin_importer = next(
            (
                plugin
                for plugin in plugin_pool.get_all_plugins()
                if plugin.__name__ == "PluginImporter"
            ),
            None
        )

    def test_get_plugin_urls(self):
        urlpatterns = self.plugin_importer().get_plugin_urls()
        self.assertEqual(
            [pattern.name for pattern in urlpatterns],
            ["cms_transfer_clipboard", "cms_export_plugins", "cms_import_plugins"],
        )

    def test_get_extra_menu_items(self):
        request = self.get_request()

        with self.subTest("extra plugin menu items"):
            text_plugin = self._create_plugin()
            pluginimporter_plugin = self._add_plugin_to_page("PluginImporter")
            menu_items = self.plugin_importer.get_extra_plugin_menu_items(request, text_plugin)
            self.assertEqual(len(menu_items), 2)
            self.assertEqual(menu_items[0].name, "Export plugins")
            self.assertEqual(menu_items[1].name, "Import plugins")
            self.assertEqual(menu_items[1].attributes["on-close"], REFRESH_PAGE)
            self.assertEqual(
                menu_items[0].url,
                "/en/admin/cms/page/plugin/plugin_importer/export-plugins/?language=en&plugin=1"
            )
            self.assertEqual(
                menu_items[1].url,
                "/en/admin/cms/page/plugin/plugin_importer/import-plugins/?language=en&plugin=1"
            )
            # no menu item for PluginImporter itself
            self.assertIsNone(self.plugin_importer.get_extra_plugin_menu_items(request, pluginimporter_plugin))

        with self.subTest("extra placeholder menu items"):
            placeholder = self.page_content.get_placeholders().get(slot="content")
            menu_items = self.plugin_importer.get_extra_placeholder_menu_items(request, placeholder)
            self.assertEqual(menu_items[1].attributes["on-close"], REFRESH_PAGE)
            self.assertEqual(
                menu_items[0].url,
                "/en/admin/cms/page/plugin/plugin_importer/export-plugins/?language=en&placeholder=1"
            )
            self.assertEqual(
                menu_items[1].url,
                "/en/admin/cms/page/plugin/plugin_importer/import-plugins/?language=en&placeholder=1"
            )

    def test_import_plugin_views(self):
        with self.login_user_context(self.user):
            response = self.client.get(admin_reverse("cms_import_plugins"))
            self.assertEqual(response.content, b"Form received unexpected values.")

        del self.user # self.get_request() checks for "user" attribute
        self.assertRaises(
            PermissionDenied,
            self.plugin_importer.import_plugins_view,
            self.get_request()
        )

    def test_import_plugin_views_for_page(self):
        with self.login_user_context(self.user):
            # GET page import
            response = self.client.get(
                admin_reverse("cms_import_plugins") + f"?language=en&cms_pagecontent={self.page_content.id}"
            )
            self.assertEqual(response.templates[0].name, "djangocms_transfer/import_plugins.html")
            self.assertEqual(response.context["form"].initial["cms_pagecontent"], self.page_content)

            # POST page import
            post_data = {
                "language": "en", "cms_pagecontent": [self.page_content.id],
                "import_file": SimpleUploadedFile("file.txt", bytes(json.dumps(self._get_expected_page_export_data()), "utf-8"))
            }
            response = self.client.post(
                admin_reverse("cms_import_plugins") + f"?language=en&cms_pagecontent={self.page_content.id}",
                post_data
            )
            self.assertIn(b'<div class="success"></div>', response.content)

    def test_import_plugin_views_for_placeholder(self):
        placeholder = self.page_content.get_placeholders().get(slot="content")
        with self.login_user_context(self.user):
            # GET placeholder import
            response = self.client.get(
                admin_reverse("cms_import_plugins") + f"?language=en&placeholder={placeholder.id}"
            )
            self.assertEqual(response.templates[0].name, "djangocms_transfer/import_plugins.html")
            self.assertEqual(response.context["form"].initial["placeholder"], placeholder)

            # empty placeholder import (no existing plugin)
            request_path = admin_reverse("cms_import_plugins") + f"?language=en&placeholder={placeholder.id}"
            post_data = {
                "language": "en", "placeholder": [placeholder.id],
                "import_file": SimpleUploadedFile("file.txt", b"[null, null]")
            }
            response = self.client.post(path=request_path, data=post_data)
            self.assertEqual(response.status_code, 200)

            # create plugins in the placeholder
            text_plugin = self._create_plugin()
            self._add_plugin_to_page("PluginImporter")
            self._create_plugin(plugin_type="LinkPlugin", parent=text_plugin)

            # empty placeholder import
            request_path = admin_reverse("cms_import_plugins") + f"?language=en&placeholder={placeholder.id}"
            post_data = {
                "language": "en", "placeholder": [placeholder.id],
                "import_file": SimpleUploadedFile("file.txt", b"[null, null]")
            }
            response = self.client.post(path=request_path, data=post_data)
            self.assertIn(b'<div class="success"></div>', response.content)
            self.assertTemplateUsed(response, "djangocms_transfer/placeholder_close_frame.html")

            self.assertNotIn("structure_data", response.context)
            self.assertContains(response, 'class="cms-close-frame"')
            self.assertNotContains(response, "<script")

            # POST placeholder import: simple data
            post_data["import_file"] = SimpleUploadedFile(
                "file.txt",
                bytes(json.dumps(self._get_expected_placeholder_export_data()), "utf-8")
            )
            response = self.client.post(path=request_path, data=post_data)
            self.assertIn(b'<div class="success"></div>', response.content)

            self.assertNotIn("structure_data", response.context)
            self.assertNotContains(response, "<script")
            self.assertEqual(placeholder.get_plugins("en").count(), 4)

    def test_import_plugin_views_for_plugin(self):
        # create plugins
        text_plugin = self._create_plugin()
        pluginimporter_plugin = self._create_plugin("PluginImporter")
        self._create_plugin(plugin_type="LinkPlugin", parent=text_plugin)

        with self.login_user_context(self.user):
            # GET plugin import
            response = self.client.get(
                admin_reverse("cms_import_plugins") + f"?language=en&plugin={text_plugin.pk}"
            )
            self.assertEqual(response.templates[0].name, "djangocms_transfer/import_plugins.html")
            self.assertEqual(response.context["form"].initial["plugin"], text_plugin.cmsplugin_ptr)

            # empty POST plugin import
            request_path = admin_reverse("cms_import_plugins") + f"?language=en&plugin={text_plugin.pk}"
            post_data = {
                "language": "en", "plugin": [text_plugin.id],
                "import_file": SimpleUploadedFile("file.txt", b"[null, null]")
            }
            response = self.client.post(path=request_path, data=post_data)
            self.assertEqual(response.status_code, 200)

            # plugin import on TextPlugin
            post_data["import_file"] = SimpleUploadedFile(
                "file.txt",
                bytes(json.dumps(self._get_expected_placeholder_export_data()), "utf-8")
            )
            response = self.client.post(path=request_path, data=post_data)
            self.assertIn(b'<div class="success"></div>', response.content)

            # plugin import on PluginImporterPlugin
            request_path = admin_reverse("cms_import_plugins") + f"?language=en&plugin={pluginimporter_plugin.pk}"
            post_data = {"language": "en", "plugin": [pluginimporter_plugin.id]}
            post_data["import_file"] = SimpleUploadedFile(
                "file.txt",
                bytes(json.dumps(self._get_expected_placeholder_export_data()), "utf-8")
            )
            response = self.client.post(path=request_path, data=post_data)
            self.assertIn(b'<div class="success"></div>', response.content)

    def test_export_plugin_views(self):
        with self.login_user_context(self.user):
            response = self.client.get(admin_reverse("cms_export_plugins"))
            self.assertEqual(response.content, b"Form received unexpected values.")

        del self.user # self.get_request() checks for "user" attribute
        self.assertRaises(
            PermissionDenied,
            self.plugin_importer.export_plugins_view,
            self.get_request()
        )

    def test_export_plugin_views_for_plugin(self):
        # create plugins
        text_plugin = self._create_plugin()
        self._create_plugin(plugin_type="LinkPlugin", parent=text_plugin)

        with self.login_user_context(self.user):
            response = self.client.get(
                admin_reverse("cms_export_plugins") + f"?language=en&plugin={text_plugin.pk}"
            )
            self.assertEqual(response.status_code, 200)
            exported_data = json.loads(response.content)["plugins"]
            # exported content should be TextPlugin and its child (LinkPlugin).
            self.assertEqual(len(exported_data), 2)
            self.assertEqual(list(map(lambda i: i["plugin_type"], exported_data)), ["TextPlugin", "LinkPlugin"])

    def test_export_plugin_views_for_placeholder(self):
        placeholder = self.page_content.get_placeholders().get(slot="content")
        # create plugins in the placeholder
        text_plugin = self._create_plugin()
        self._add_plugin_to_page("PluginImporter")
        self._create_plugin(plugin_type="LinkPlugin", parent=text_plugin)

        with self.login_user_context(self.user):
            response = self.client.get(
                admin_reverse("cms_export_plugins") + f"?language=en&placeholder={placeholder.pk}"
            )
            self.assertEqual(response.status_code, 200)
            exported_data = json.loads(response.content)["plugins"]
            self.assertEqual(len(exported_data), 3)
            self.assertEqual(list(map(lambda i: i["plugin_type"], exported_data)), ["TextPlugin", "LinkPlugin", "PluginImporter"])

    def test_export_plugin_views_for_page(self):
        with self.login_user_context(self.user):
            response = self.client.get(
                admin_reverse("cms_export_plugins") + f"?language=en&cms_pagecontent={self.page_content.pk}"
            )
            self.assertEqual(response.status_code, 200)
            exported_data = json.loads(response.content)["placeholders"]
            self.assertEqual(exported_data[0]["placeholder"], "content")
            self.assertEqual(len(exported_data[0]["plugins"]), 0)
