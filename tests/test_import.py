import json
import unittest

from cms.models import CMSPlugin
from djangocms_text.utils import plugin_to_tag

from djangocms_transfer.datastructures import (
    ArchivedPlaceholder,
    ArchivedPlugin,
)
from djangocms_transfer.exporter import export_placeholder, export_plugin
from djangocms_transfer.importer import import_plugins, import_plugins_to_page

from .abstract import FunctionalityBaseTestCase
from .test_app.models import Section


class ImportTest(FunctionalityBaseTestCase):
    def test_archivedplugin_restore_for_m2m_field(self):
        plugin = self._create_plugin(plugin_type="ArticlePlugin", title="Test")
        plugin.sections.set([
            Section.objects.create(name="body"),
            Section.objects.create(name="inner-body")
        ])
        archived_plugin = ArchivedPlugin(**json.loads(export_plugin(plugin))[0])

        placeholder = self.page_content.placeholders.create(slot="test")
        restored_plugin = archived_plugin.restore(placeholder, "en")
        self.assertEqual(restored_plugin.title, "Test")
        # second ArticlePluginModel instance in a new placeholder
        self.assertEqual(restored_plugin.position, 1)
        self.assertEqual(
            restored_plugin.sections.get(name="body"),
            plugin.sections.get(name="body")
        )

    def test_archivedplugin_restore_for_existing_related_field(self):
        placeholder = self.page_content.placeholders.create(slot="test")
        article_data = {"title": "Test",
                        "section": Section.objects.create(name="body")}
        plugin = self._create_plugin(plugin_type="RandomPlugin", **article_data)
        plugin_data = json.loads(export_plugin(plugin))[0]
        archived_plugin = ArchivedPlugin(**plugin_data)

        restored_plugin = archived_plugin.restore(placeholder, "en")
        self.assertEqual(restored_plugin.title, "Test")
        self.assertEqual(restored_plugin.position, 1)
        self.assertEqual(restored_plugin.section, plugin.section)

    @unittest.skip("TODO: fix 'field.related_model.DoesNotExist' on ArchivedPlugin.restore")
    def test_archivedplugin_restore_for_non_existing_related_field(self):
        placeholder = self.page_content.placeholders.create(slot="test")
        article_data = {"title": "Test",
                        "section": Section.objects.create(name="body")}
        plugin = self._create_plugin(plugin_type="RandomPlugin", **article_data)
        plugin_data = json.loads(export_plugin(plugin))[0]
        plugin_data["data"].pop("section") # remove section from the plugin's data
        no_section_archived_plugin = ArchivedPlugin(**plugin_data)

        no_section_restored_plugin = no_section_archived_plugin.restore(placeholder, "en")
        self.assertEqual(no_section_restored_plugin.section, None)

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
