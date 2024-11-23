import json

from djangocms_transfer.datastructures import (
    ArchivedPlaceholder,
    ArchivedPlugin,
)
from djangocms_transfer.exporter import export_placeholder, export_plugin
from djangocms_transfer.importer import import_plugins, import_plugins_to_page

from .abstract import FunctionalityBaseTestCase


class ImportTest(FunctionalityBaseTestCase):
    def test_import(self):
        page = self.page
        placeholder = self.page_content.get_placeholders().get(slot="content")
        plugin = self._create_plugin()

        plugin_data = ArchivedPlugin(**json.loads(export_plugin(plugin))[0])
        placeholder_data = ArchivedPlaceholder(
            "content",
            [ArchivedPlugin(**data) for data in json.loads(export_placeholder(placeholder, "en"))],
        )

        with self.subTest("import plugins"):
            import_plugins([plugin_data], placeholder, "en")

        with self.subTest("import placeholder"):
            import_plugins(placeholder_data.plugins, placeholder, "en")

        with self.subTest("import page"):
            import_plugins_to_page([placeholder_data], page, "en")
