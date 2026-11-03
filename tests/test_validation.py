import json
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DataError
from django.test import Client, override_settings

from cms.models import CMSPlugin
from cms.models.placeholderpluginmodel import PlaceholderReference
from cms.plugin_pool import plugin_pool
from cms.utils.urlutils import admin_reverse

from djangocms_transfer.exporter import export_plugin

from .abstract import FunctionalityBaseTestCase


class ImportValidationTests(FunctionalityBaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = self._create_user("validation", True, True)
        self.plugin = self._create_plugin()
        self.rows = json.loads(export_plugin(self.plugin))

    def submit(self, rows, browser=True, multipart=False):
        if browser:
            payload = {"format": "djangocms-transfer", "version": 1, "kind": "plugin", "plugins": rows}
            if multipart:
                return self.client.post(admin_reverse("cms_transfer_clipboard"), {
                    "clipboard": SimpleUploadedFile("clipboard.json", json.dumps(payload).encode()),
                })
            return self.client.post(admin_reverse("cms_transfer_clipboard"),
                                    json.dumps(payload), content_type="application/json")
        return self.client.post(admin_reverse("cms_import_plugins"), {
            "placeholder": self.plugin.placeholder_id, "language": "en",
            "import_file": SimpleUploadedFile("plugins.json", json.dumps(rows).encode()),
        })

    def test_export_hook_null_rows_are_skipped_on_both_paths(self):
        with self.login_user_context(self.user):
            for browser in (True, False):
                with self.subTest(browser=browser):
                    before = CMSPlugin.objects.count()
                    response = self.submit([None, *self.rows, None], browser)
                    self.assertEqual(response.status_code, 200, response.content)
                    self.assertEqual(CMSPlugin.objects.count(), before + 1)

    def test_both_paths_reject_unsafe_urls_missing_fields_and_invalid_choices(self):
        link = self._create_plugin(plugin_type="LinkPlugin")
        link_row = json.loads(export_plugin(link))[0]
        unsafe = {**link_row, "data": {**link_row["data"], "link": {"external_link": "javascript:alert(1)"}}}
        attributes = {**link_row, "data": {**link_row["data"], "attributes": {"onclick": "alert(1)"}}}
        choice = {**link_row, "data": {**link_row["data"], "link_target": "invalid-choice"}}
        missing = {**self.rows[0], "plugin_type": "ArticlePlugin", "data": {"sections": []}}
        oversized = {**missing, "data": {"title": "x" * 51, "sections": []}}
        invalid_structured = [{**link_row, "data": {**link_row["data"], "link": value}}
                              for value in (123, "javascript:alert(1)", ["external_link"])]
        with self.login_user_context(self.user):
            for browser in (True, False):
                for row in (unsafe, attributes, choice, missing, oversized, *invalid_structured):
                    with self.subTest(browser=browser, row=row):
                        ids = list(CMSPlugin.objects.values_list("pk", flat=True))
                        response = self.submit([row], browser)
                        if browser:
                            self.assertEqual(response.status_code, 400, response.content)
                        else:
                            self.assertTrue(response.context["form"].non_field_errors())
                        self.assertEqual(list(CMSPlugin.objects.values_list("pk", flat=True)), ids)

    def test_custom_form_cleaners_are_applied_and_persisted(self):
        plugin_class = plugin_pool.get_plugin("TextPlugin")

        class CleanTextForm(plugin_class.form):
            def clean_body(self):
                return self.cleaned_data["body"].replace("Hello", "Cleaned")

        with self.login_user_context(self.user), patch.object(plugin_class, "form", CleanTextForm):
            for browser in (True, False):
                with self.subTest(browser=browser):
                    response = self.submit(self.rows, browser)
                    self.assertEqual(response.status_code, 200)
                    plugin = CMSPlugin.objects.order_by("-pk").first().get_bound_plugin()
                    self.assertEqual(plugin.body, "Cleaned World!")

    def test_nested_json_is_not_interpreted_as_plugin_metadata(self):
        value = {"plugin_type": "ordinary value", "plugins": [None, {"body": "nested data"}]}
        row = {**self.rows[0], "data": {**self.rows[0]["data"], "json": value}}
        with self.login_user_context(self.user):
            for browser in (True, False):
                response = self.submit([row], browser)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(CMSPlugin.objects.order_by("-pk").first().get_bound_plugin().json, value)

    def test_rich_text_uses_the_plugins_html_sanitizer_on_both_paths(self):
        row = {**self.rows[0], "data": {**self.rows[0]["data"],
               "body": '<p><strong>Safe</strong><script>alert(1)</script><img src=x onerror="alert(1)"></p>'}}
        with self.login_user_context(self.user):
            for browser in (True, False):
                response = self.submit([row], browser)
                self.assertEqual(response.status_code, 200)
                body = CMSPlugin.objects.order_by("-pk").first().get_bound_plugin().body
                self.assertIn("<strong>Safe</strong>", body)
                self.assertNotIn("<script", body)
                self.assertNotIn("onerror", body)

    def test_file_import_enforces_plugin_and_destination_permissions(self):
        with self.login_user_context(self.user):
            ids = list(CMSPlugin.objects.values_list("pk", flat=True))
            with patch("djangocms_transfer.validation.has_plugin_permission", return_value=False):
                self.assertEqual(self.submit(self.rows, False).status_code, 403)
            with patch("cms.models.Placeholder.has_add_plugins_permission", return_value=False):
                self.assertEqual(self.submit(self.rows, False).status_code, 403)
            with patch("cms.models.Placeholder.check_source", return_value=False):
                self.assertEqual(self.submit(self.rows, False).status_code, 403)
            system = {**self.rows[0], "plugin_type": "PluginImporter", "data": {}}
            response = self.submit([system], False)
            self.assertTrue(response.context["form"].non_field_errors())
            self.assertEqual(list(CMSPlugin.objects.values_list("pk", flat=True)), ids)

    def test_file_import_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(admin_reverse("cms_import_plugins"), {
            "placeholder": self.plugin.placeholder_id, "language": "en",
            "import_file": SimpleUploadedFile("plugins.json", json.dumps(self.rows).encode()),
        })
        self.assertEqual(response.status_code, 403)

    def test_staff_with_only_add_permission_can_import_into_their_own_clipboard(self):
        self.user.is_superuser = False
        self.user.save()
        self.user.user_permissions.add(Permission.objects.get(codename="add_text", content_type__app_label="djangocms_text"))
        with self.login_user_context(self.user):
            for kind in ("plugin", "placeholder"):
                with self.subTest(kind=kind):
                    response = self.client.post(admin_reverse("cms_transfer_clipboard"), json.dumps({
                        "format": "djangocms-transfer", "version": 1, "kind": kind, "plugins": self.rows,
                    }), content_type="application/json")
                    self.assertEqual(response.status_code, 200, response.content)

    def test_database_value_errors_are_reported_and_hook_bugs_are_logged(self):
        with self.login_user_context(self.user):
            for exception in (DataError("too large"), OverflowError("too large")):
                with self.subTest(exception=exception), patch("djangocms_transfer.clipboard.import_plugins", side_effect=exception):
                    response = self.submit(self.rows)
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("could not be stored", response.json()["error"])
            for exception in (AttributeError("hook bug"), KeyError("hook bug")):
                with self.subTest(exception=exception), self.assertLogs("djangocms_transfer.clipboard", level="ERROR"):
                    with patch("djangocms_transfer.clipboard.import_plugins", side_effect=exception):
                        response = self.submit(self.rows)
                    self.assertEqual(response.status_code, 500)
                    self.assertNotIn("hook bug", response.json()["error"])

    def test_model_validation_messages_are_preserved_on_both_paths(self):
        with self.login_user_context(self.user):
            for browser, path in ((True, "djangocms_transfer.clipboard.import_plugins"),
                                  (False, "djangocms_transfer.forms.import_plugins")):
                with self.subTest(browser=browser), patch(path, side_effect=ValidationError({"body": "Invalid authored body"})):
                    response = self.submit(self.rows, browser)
                    if browser:
                        self.assertEqual(response.status_code, 400)
                        self.assertIn("Invalid authored body", response.json()["error"])
                    else:
                        self.assertIn("Invalid authored body", str(response.context["form"].non_field_errors()))

    def test_post_copy_bugs_are_logged_and_rollback_both_paths(self):
        model = plugin_pool.get_plugin("TextPlugin").model
        with self.login_user_context(self.user):
            self.assertEqual(self.submit(self.rows).status_code, 200)
            for browser, logger in ((True, "djangocms_transfer.clipboard"), (False, "djangocms_transfer.cms_plugins")):
                ids = list(CMSPlugin.objects.values_list("pk", flat=True))
                with self.assertLogs(logger, level="ERROR"), patch.object(model, "post_copy", side_effect=KeyError("post-copy bug")):
                    response = self.submit(self.rows, browser)
                self.assertEqual(list(CMSPlugin.objects.values_list("pk", flat=True)), ids)
                if browser:
                    self.assertEqual(response.status_code, 500)
                    self.assertNotIn("post-copy bug", response.json()["error"])
                else:
                    self.assertIn("No content was changed", str(response.context["form"].non_field_errors()))

    @override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=1024)
    def test_multipart_import_bypasses_the_json_body_limit(self):
        row = {**self.rows[0], "data": {**self.rows[0]["data"], "body": "x" * 4096}}
        with self.login_user_context(self.user):
            self.assertEqual(self.submit([row]).status_code, 413)
            self.assertEqual(self.submit([row], multipart=True).status_code, 200)

    @override_settings(DJANGOCMS_TRANSFER_MAX_CLIPBOARD_SIZE=10)
    def test_multipart_limit_is_reported_without_replacing_clipboard(self):
        with self.login_user_context(self.user):
            ids = list(CMSPlugin.objects.values_list("pk", flat=True))
            response = self.submit(self.rows, multipart=True)
            self.assertEqual(response.status_code, 413)
            self.assertIn("upload limit", response.json()["error"])
            self.assertEqual(list(CMSPlugin.objects.values_list("pk", flat=True)), ids)

    def test_export_rejects_stale_copy_identity_and_empty_content(self):
        with self.login_user_context(self.user):
            response = self.submit(self.rows)
            clipboard = response.wsgi_request.toolbar.clipboard
            root = clipboard.get_plugins().get()
            url = admin_reverse("cms_transfer_clipboard")
            self.assertEqual(self.client.get(url, {"plugin": root.pk + 1}).status_code, 409)
            self.assertEqual(self.client.get(url, {"plugin": root.pk}).status_code, 200)
            with patch("djangocms_transfer.clipboard.get_plugin_export_data", return_value=[]):
                self.assertEqual(self.client.get(url).status_code, 400)
            clipboard.clear()
            PlaceholderReference.objects.create(
                placeholder=clipboard, language="en", plugin_type="PlaceholderPlugin", name="Empty",
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, 400)
            self.assertIn("no transferable plugins", response.json()["error"])
