import json

from cms.plugin_pool import plugin_pool
from cms.utils.urlutils import admin_reverse
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile

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
        self.assertEqual(len(urlpatterns), 2)
        self.assertEqual(urlpatterns[0].name, "cms_export_plugins")
        self.assertEqual(urlpatterns[1].name, "cms_import_plugins")

    def test_get_extra_menu_items(self):
        request = self.get_request()

        with self.subTest("extra plugin menu items"):
            text_plugin = self._create_plugin()
            pluginimporter_plugin = self._add_plugin_to_page("PluginImporter")
            menu_items = self.plugin_importer.get_extra_plugin_menu_items(request, text_plugin)
            self.assertEqual(len(menu_items), 2)
            self.assertEqual(menu_items[0].name, "Export plugins")
            self.assertEqual(menu_items[1].name, "Import plugins")
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
            with self.assertRaises(IndexError):
                self.client.post(path=request_path, data=post_data)

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
            self.assertEqual(response.context[2].template_name, "djangocms_transfer/placeholder_close_frame.html")

            structure_data = json.loads(response.context["structure_data"])
            # Since the import file is empty, only child plugins gets
            # passed to the frontend data bridge
            self.assertEqual(len(structure_data["plugins"]), 1)

            # POST placeholder import: simple data
            post_data["import_file"] = SimpleUploadedFile(
                "file.txt",
                bytes(json.dumps(self._get_expected_placeholder_export_data()), "utf-8")
            )
            response = self.client.post(path=request_path, data=post_data)
            self.assertIn(b'<div class="success"></div>', response.content)

            structure_data = json.loads(response.context["structure_data"])
            # newly imported plugin and child plugin gets passed to the frontend data bridge
            self.assertEqual(len(structure_data["plugins"]), 2)

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
            with self.assertRaises(IndexError):
                self.client.post(path=request_path, data=post_data)

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
