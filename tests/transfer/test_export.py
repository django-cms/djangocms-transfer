import json

from djangocms_transfer.exporter import (
    export_page,
    export_placeholder,
    export_plugin,
)

from .abstract import FunctionalityBaseTestCase


class ExportTest(FunctionalityBaseTestCase):
    def test_export_plugin(self):
        plugin = self._create_plugin()

        actual = json.loads(export_plugin(plugin))

        self.assertEqual(self._get_expected_plugin_export_data(), actual)

    def test_export_placeholder(self):
        placeholder = self.page_content.get_placeholders().get(slot="content")

        with self.subTest("empty placeholder"):
            actual = json.loads(export_placeholder(placeholder, "en"))
            self.assertEqual([], actual)

        with self.subTest("placeholder with plugin"):
            self._create_plugin()
            actual = json.loads(export_placeholder(placeholder, "en"))
            self.assertEqual(self._get_expected_placeholder_export_data(), actual)

    def test_export_page(self):
        page = self.page

        with self.subTest("empty page"):
            actual = json.loads(export_page(self.page_content, "en"))
            self.assertEqual([{"placeholder": "content", "plugins": []}], actual)

        with self.subTest("page with plugin"):
            self._create_plugin()
            actual = json.loads(export_page(self.page_content, "en"))
            self.assertEqual(self._get_expected_page_export_data(), actual)
