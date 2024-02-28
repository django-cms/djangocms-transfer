import json
import os
from tempfile import mkdtemp

from django.core.files import File

from djangocms_transfer.forms import PluginExportForm, PluginImportForm


from .abstract import FunctionalityBaseTestCase


class PluginExportFormTest(FunctionalityBaseTestCase):
    def test_get_filename(self):
        page = self.page
        placeholder = page.placeholders.get(slot="content")
        plugin = self._create_plugin()

        data = {
            "plugin": plugin,
            "placeholder": placeholder,
            "cms_page": page,
            "language": "en",
        }

        with self.subTest("filename from page"):
            form = PluginExportForm(data=data)
            form.clean()
            self.assertEqual("home.json", form.get_filename())

        with self.subTest("filename from placeholder"):
            data["cms_page"] = None
            form = PluginExportForm(data=data)
            form.clean()
            self.assertEqual("home_content.json", form.get_filename())

        with self.subTest("filename from plugin"):
            data["placeholder"] = None
            form = PluginExportForm(data=data)
            form.clean()
            self.assertEqual("home_hello-world.json", form.get_filename())

        with self.subTest("filename from fallback"):
            data["plugin"] = None
            form = PluginExportForm(data=data)
            form.clean()
            self.assertEqual("plugins.json", form.get_filename())

    def test_validation(self):
        page = self.page
        placeholder = page.placeholders.get(slot="content")
        plugin = self._create_plugin()

        with self.subTest("language missing"):
            form = PluginExportForm(data={})
            self.assertEqual(["This field is required."], form.errors["language"])

        with self.subTest("one of plugin/placeholder/page required"):
            form = PluginExportForm(data={"language": "en"})
            self.assertEqual(["A plugin, placeholder or page is required."], form.errors["__all__"])

        with self.subTest("cms_page + plugin given"):
            form = PluginExportForm(data={"language": "en", "cms_page": page, "plugin": plugin})
            self.assertEqual(
                ["Plugins can be imported to pages, plugins or placeholders. Not all three."],
                form.errors["__all__"],
            )

        with self.subTest("cms_page + placeholder given"):
            form = PluginExportForm(data={"language": "en", "cms_page": page, "placeholder": placeholder})
            self.assertEqual(
                ["Plugins can be imported to pages, plugins or placeholders. Not all three."],
                form.errors["__all__"],
            )

        with self.subTest("plugin + placeholder given"):
            form = PluginExportForm(data={"language": "en", "plugin": plugin, "placeholder": placeholder})
            self.assertEqual(
                ["Plugins can be imported to pages, plugins or placeholders. Not all three."],
                form.errors["__all__"],
            )

    def test_run_export(self):
        page = self.page
        placeholder = page.placeholders.get(slot="content")
        plugin = self._create_plugin()

        data = {
            "plugin": plugin,
            "placeholder": None,
            "cms_page": None,
            "language": "en",
        }

        with self.subTest("export plugin"):
            form = PluginExportForm(data=data)
            form.clean()
            actual = json.loads(form.run_export())
            self.assertEqual(self._get_expected_plugin_export_data(), actual)

        with self.subTest("export placeholder"):
            data["placeholder"] = placeholder
            data["plugin"] = None
            form = PluginExportForm(data=data)
            form.clean()
            actual = json.loads(form.run_export())
            self.assertEqual(self._get_expected_placeholder_export_data(), actual)

        with self.subTest("export page"):
            data["cms_page"] = page
            data["placeholder"] = None
            form = PluginExportForm(data=data)
            form.clean()
            actual = json.loads(form.run_export())
            self.assertEqual(self._get_expected_page_export_data(), actual)


class PluginImportFormTest(FunctionalityBaseTestCase):
    def test_validation(self):
        page = self.page
        placeholder = page.placeholders.get(slot="content")
        plugin = self._create_plugin()
        file_ = self._get_file()

        with self.subTest("file missing"):
            form = PluginImportForm(data={})
            self.assertEqual(["This field is required."], form.errors["import_file"])

        with self.subTest("language missing"):
            form = PluginImportForm(data={"import_file": file_})
            self.assertEqual(["This field is required."], form.errors["language"])

    def _get_file(self):
        content = json.dumps(self._get_expected_plugin_export_data())

        tmp_dir = mkdtemp()
        filename = os.path.join(tmp_dir, "dummy-test.json")
        with open(filename, "w") as f:
            f.write(content)

        return File(open(filename, "rb"), name=filename)
