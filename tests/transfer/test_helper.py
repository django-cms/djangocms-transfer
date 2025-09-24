import pytest

from djangocms_transfer import custom_process_hook

from .abstract import FunctionalityBaseTestCase


class CustomProcessHookTest(FunctionalityBaseTestCase):
    def setUp(self):
        super().setUp()
        self.plugin = self._create_plugin()
        self.plugin_data = self._get_expected_page_export_data

    def test_empty_nonexistent_custom_process_hook(self):
        self.assertEqual(
            custom_process_hook("", self.plugin, self.plugin_data),
            self.plugin_data
        )
        self.assertEqual(
            custom_process_hook("UNKNOWN_TRANSFER", self.plugin, self.plugin_data),
            self.plugin_data
        )

    @pytest.mark.usefixtures("use_nonexistent_transfer_hook")
    def test_nonexistent_module(self):
        self.assertRaises(
            ImportError,
            custom_process_hook,
            "DJANGOCMS_TRANSFER_PROCESS_IMPORT_PLUGIN_DATA",
            self.plugin
        )
        self.assertRaises(
            ImportError,
            custom_process_hook,
            "DJANGOCMS_TRANSFER_PROCESS_EXPORT_PLUGIN_DATA",
            self.plugin, self.plugin_data
        )

    @pytest.mark.usefixtures("use_existent_transfer_hook")
    def test_existent_module(self):
        self.assertTrue(
            custom_process_hook(
                "DJANGOCMS_TRANSFER_PROCESS_IMPORT_PLUGIN_DATA",
                self.plugin
            ),
            self.plugin
        )
        self.assertTrue(
            custom_process_hook(
                "DJANGOCMS_TRANSFER_PROCESS_EXPORT_PLUGIN_DATA",
                self.plugin, self.plugin_data
            ),
            (self.plugin, self.plugin_data)
        )
