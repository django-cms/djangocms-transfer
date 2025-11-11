import json

from cms.models import CMSPlugin
from djangocms_text.utils import plugin_to_tag

from djangocms_transfer.datastructures import (
    ArchivedPlaceholder,
    ArchivedPlugin,
)
from djangocms_transfer.exporter import export_placeholder, export_plugin
from djangocms_transfer.importer import import_plugins, import_plugins_to_page

from .abstract import FunctionalityBaseTestCase


class ImportTest(FunctionalityBaseTestCase):
    def test_import(self):
        pagecontent = self.page_content
        placeholder = pagecontent.get_placeholders().get(slot="content")
        plugin = self._create_plugin()

        # create link plugin
        link_plugin = self._create_plugin(plugin_type="LinkPlugin", parent=plugin)

        # Add plugin to text body
        plugin.body = f"{plugin.body} {plugin_to_tag(link_plugin)}"
        plugin.save()

        link_plugin_data = ArchivedPlugin(
            **json.loads(export_plugin(link_plugin))[0]
        )
        plugin_data = ArchivedPlugin(**json.loads(export_plugin(plugin))[0])
        placeholder_data = ArchivedPlaceholder(
            "content",
            [ArchivedPlugin(**data) for data in json.loads(export_placeholder(placeholder, "en"))],
        )

        with self.subTest("import plugins"):
            import_plugins([plugin_data, link_plugin_data], placeholder, "en")

            # test import updates child plugin
            new_plugin, new_link_plugin = map(
                lambda plugin: plugin.get_bound_plugin(), CMSPlugin.objects.filter(pk__in=[3,4])
            )
            self.assertEqual(
                new_plugin.body,
                f"{self.TEXT_BODY} {plugin_to_tag(new_link_plugin)}"
            )

        with self.subTest("import placeholder"):
            import_plugins(placeholder_data.plugins, placeholder, "en")

        with self.subTest("import page"):
            import_plugins_to_page([placeholder_data], pagecontent, "en")
