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
