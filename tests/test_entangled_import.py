import json
from copy import deepcopy

from django.core.files.uploadedfile import SimpleUploadedFile

from cms.models import CMSPlugin
from cms.utils.urlutils import admin_reverse

from djangocms_transfer.clipboard import parse_clipboard
from djangocms_transfer.validation import clean_plugin_data

from .abstract import FunctionalityBaseTestCase


def grid_payload():
    """The reported row/four-column/TextPlugin clipboard structure."""
    def plugin(pk, kind, parent, data):
        return {"pk": pk, "creation_date": "2026-04-28T22:54:07.025Z", "position": pk - 182,
                "plugin_type": kind, "parent_id": parent, "data": data}

    row = {"padding_x": "", "padding_y": "", "padding_devices": None,
           "margin_x": "", "margin_y": "", "margin_devices": None,
           "responsive_visibility": None, "plugin_title": {"show": False, "title": ""},
           "vertical_alignment": "", "horizontal_alignment": "", "gutters": "", "attributes": {}}
    row.update({f"row_cols_{size}": None for size in ("xs", "sm", "md", "lg", "xl", "xxl")})
    rows = [plugin(183, "GridRowPlugin", None, {"ui_item": "GridRow", "tag_type": "div", "config": row})]
    for pk in (184, 186, 188, 190):
        config = {"column_alignment": None}
        config.update({f"{size}_{key}": None for size in ("xs", "sm", "md", "lg", "xl", "xxl")
                       for key in ("col", "order", "offset", "ml", "mr")})
        rows.append(plugin(pk, "GridColumnPlugin", 183,
                           {"ui_item": "GridColumn", "tag_type": "div", "config": config}))
        rows.append(plugin(pk + 1, "TextPlugin", pk, {
            "body": "<p>Col</p><p></p>", "rte": "tiptap",
            "json": {"type": "doc", "content": [
                {"type": "paragraph", "attrs": {"textAlign": None}, "content": [{"type": "text", "text": "Col"}]},
                {"type": "paragraph", "attrs": {"textAlign": None}},
            ]},
        }))
    return {"format": "djangocms-transfer", "version": 1, "kind": "plugin", "plugins": rows}


class EntangledImportTests(FunctionalityBaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = self._create_user("grid-editor", True, True)
        self.payload = grid_payload()
        self.placeholder = self.page_content.get_placeholders().get(slot="content")

    def submit(self, payload, browser):
        if browser:
            return self.client.post(admin_reverse("cms_transfer_clipboard"),
                                    json.dumps(payload), content_type="application/json")
        return self.client.post(admin_reverse("cms_import_plugins"), {
            "language": "en", "placeholder": self.placeholder.pk,
            "import_file": SimpleUploadedFile("grid.json", json.dumps(payload["plugins"]).encode()),
        })

    def test_copied_grid_tree_imports_through_clipboard_and_file(self):
        with self.login_user_context(self.user):
            for browser in (True, False):
                with self.subTest(browser=browser):
                    response = self.submit(self.payload, browser)
                    self.assertEqual(response.status_code, 200, response.content)
                    target = response.wsgi_request.toolbar.clipboard if browser else self.placeholder
                    plugins = list(target.get_plugins("en"))
                    self.assertEqual(len(plugins), 9)
                    root = plugins[0]
                    self.assertEqual(root.plugin_type, "GridRowPlugin")
                    for column, text in zip(plugins[1::2], plugins[2::2]):
                        self.assertEqual(column.parent_id, root.pk)
                        self.assertEqual(text.parent_id, column.pk)
                        self.assertEqual(text.get_bound_plugin().json, self.payload["plugins"][2]["data"]["json"])
                    config = root.get_bound_plugin().config
                    self.assertEqual(config["plugin_title"], {"show": False, "title": ""})
                    self.assertIsNone(config["row_cols_xs"])
                    self.assertEqual(config["padding_x"], "")

    def test_nested_values_are_validated_on_both_import_paths(self):
        with self.login_user_context(self.user):
            for browser in (True, False):
                for key, value in (("vertical_alignment", "invalid"), ("row_cols_xs", 99),
                                   ("attributes", {"onclick": "alert(1)"})):
                    with self.subTest(browser=browser, key=key):
                        payload = deepcopy(self.payload)
                        payload["plugins"][0]["data"]["config"][key] = value
                        before = list(CMSPlugin.objects.values_list("pk", flat=True))
                        response = self.submit(payload, browser)
                        if browser:
                            self.assertEqual(response.status_code, 400)
                            self.assertIn(key, response.json()["error"])
                        else:
                            self.assertTrue(response.context["form"].non_field_errors())
                        self.assertEqual(list(CMSPlugin.objects.values_list("pk", flat=True)), before)

    def test_virtual_cleaners_and_prepare_value_preserve_source_configuration(self):
        self.payload["plugins"][0]["data"]["config"].update({
            "plugin_title": {"show": False, "title": "  Title  "}, "devices": None,
        })
        original = deepcopy(self.payload)
        _, plugins = parse_clipboard(self.payload, self.user)
        cleaned = clean_plugin_data(plugins[0], self.placeholder, "en")
        self.assertEqual(cleaned["config"]["plugin_title"], {"show": False, "title": "Title"})
        self.assertIsNone(cleaned["config"]["devices"])
        self.assertEqual(self.payload, original)
