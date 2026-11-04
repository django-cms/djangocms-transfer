import json
from copy import deepcopy

from django.core.files.uploadedfile import SimpleUploadedFile

from cms.models import CMSPlugin
from cms.models.placeholderpluginmodel import PlaceholderReference
from cms.utils.urlutils import admin_reverse

from djangocms_transfer.exporter import export_page, export_placeholder, export_plugin

from .abstract import FunctionalityBaseTestCase


class TransferFormatTests(FunctionalityBaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = self._create_user("format-editor", True, True)
        self.plugin = self._create_plugin()
        self.placeholder = self.plugin.placeholder

    def submit(self, payload, browser, page=False):
        if browser:
            return self.client.post(admin_reverse("cms_transfer_clipboard"), json.dumps(payload),
                                    content_type="application/json")
        destination = {"cms_pagecontent": self.page_content.pk} if page else {"placeholder": self.placeholder.pk}
        return self.client.post(admin_reverse("cms_import_plugins"), {
            **destination, "language": "en",
            "import_file": SimpleUploadedFile("transfer.json", json.dumps(payload).encode()),
        })

    def test_plugin_and_placeholder_exports_import_on_both_paths_in_both_formats(self):
        self._create_plugin(parent=self.plugin)
        exports = [json.loads(export_plugin(self.plugin)), json.loads(export_placeholder(self.placeholder, "en"))]
        with self.login_user_context(self.user):
            for payload in exports:
                self.assertEqual(payload["format"], "djangocms-transfer")
                self.assertEqual(payload["version"], 1)
                for legacy in (False, True):
                    content = payload["plugins"] if legacy else payload
                    for browser in (True, False):
                        with self.subTest(kind=payload["kind"], legacy=legacy, browser=browser):
                            before = self.placeholder.get_plugins().count()
                            response = self.submit(content, browser)
                            self.assertEqual(response.status_code, 200, response.content)
                            if browser:
                                clipboard = response.wsgi_request.toolbar.clipboard
                                exported = self.client.get(admin_reverse("cms_transfer_clipboard")).json()
                                self.assertEqual(exported["format"], payload["format"])
                                self.assertEqual(exported["version"], payload["version"])
                                root = clipboard.get_plugins().first().get_bound_plugin()
                                target = root.placeholder_ref if isinstance(root, PlaceholderReference) else clipboard
                                self.assertEqual(target.get_plugins().count(), 2)
                            else:
                                self.assertEqual(self.placeholder.get_plugins().count(), before + 2)

    def test_page_exports_import_from_file_and_clipboard_in_both_formats(self):
        payload = json.loads(export_page(self.page_content, "en"))
        self.assertEqual(payload["kind"], "page")
        with self.login_user_context(self.user):
            for legacy in (False, True):
                content = payload["placeholders"] if legacy else payload
                with self.subTest(legacy=legacy):
                    before = self.placeholder.get_plugins().count()
                    response = self.submit(content, False, page=True)
                    self.assertEqual(response.status_code, 200, response.content)
                    self.assertEqual(self.placeholder.get_plugins().count(), before + 1)
                    response = self.submit(content, True)
                    self.assertEqual(response.status_code, 200, response.content)
                    root = response.wsgi_request.toolbar.clipboard.get_plugins().get().get_bound_plugin()
                    self.assertIsInstance(root, PlaceholderReference)
                    self.assertEqual(root.placeholder_ref.get_plugins().count(), 1)

    def test_legacy_multiple_roots_and_page_slots_become_one_clipboard_placeholder(self):
        second = self._create_plugin()
        first_row = json.loads(export_plugin(self.plugin))["plugins"][0]
        second_row = json.loads(export_plugin(second))["plugins"][0]
        payloads = [
            [first_row, None, second_row],
            [{"placeholder": "content", "plugins": [first_row]},
             {"placeholder": "sidebar", "plugins": [second_row]}],
        ]
        with self.login_user_context(self.user):
            for payload in payloads:
                with self.subTest(payload=payload):
                    response = self.submit(payload, True)
                    self.assertEqual(response.status_code, 200, response.content)
                    root = response.wsgi_request.toolbar.clipboard.get_plugins().get().get_bound_plugin()
                    self.assertIsInstance(root, PlaceholderReference)
                    self.assertEqual(root.placeholder_ref.get_plugins().count(), 2)

    def test_invalid_versions_and_ambiguous_legacy_data_fail_on_both_paths(self):
        payload = json.loads(export_plugin(self.plugin))
        invalid = [
            {**payload, "version": 2}, {**payload, "version": True},
            {**payload, "version": None}, {**payload, "format": "other"},
            {key: value for key, value in payload.items() if key != "version"},
            [payload["plugins"][0], {"placeholder": "content", "plugins": []}],
            [{"plugin_type": "TextPlugin"}],
            {"format": "djangocms-transfer", "version": 1, "kind": "page", "placeholders": [
                {"placeholder": "content", "plugins": []}, {"placeholder": "content", "plugins": []}]},
        ]
        original = deepcopy(payload)
        with self.login_user_context(self.user):
            self.assertEqual(self.submit(payload, True).status_code, 200)
            for content in invalid:
                for browser in (True, False):
                    with self.subTest(payload=content, browser=browser):
                        ids = list(CMSPlugin.objects.values_list("pk", flat=True))
                        response = self.submit(content, browser)
                        if browser:
                            self.assertEqual(response.status_code, 400, response.content)
                        else:
                            self.assertTrue(response.context["form"].non_field_errors())
                        self.assertEqual(list(CMSPlugin.objects.values_list("pk", flat=True)), ids)
        self.assertEqual(payload, original)
