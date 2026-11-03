import json
from copy import deepcopy
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

from djangocms_transfer.datastructures import ArchivedPlugin
from djangocms_transfer.exporter import export_plugin

from .abstract import FunctionalityBaseTestCase
from .test_app.models import Article, Section


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

    def test_both_paths_reject_missing_model_fields_and_invalid_choices(self):
        link = self._create_plugin(plugin_type="LinkPlugin")
        link_row = json.loads(export_plugin(link))[0]
        choice = {**link_row, "data": {**link_row["data"], "link_target": "invalid-choice"}}
        missing = {**self.rows[0], "plugin_type": "ArticlePlugin", "data": {"sections": []}}
        oversized = {**missing, "data": {"title": "x" * 51, "sections": []}}
        with self.login_user_context(self.user):
            for browser in (True, False):
                for row in (choice, missing, oversized):
                    with self.subTest(browser=browser, row=row):
                        ids = list(CMSPlugin.objects.values_list("pk", flat=True))
                        response = self.submit([row], browser)
                        if browser:
                            self.assertEqual(response.status_code, 400, response.content)
                        else:
                            self.assertTrue(response.context["form"].non_field_errors())
                        self.assertEqual(list(CMSPlugin.objects.values_list("pk", flat=True)), ids)

    def test_model_cleaners_are_applied_without_constructing_forms(self):
        plugin_class = plugin_pool.get_plugin("TextPlugin")
        calls = []

        def clean(instance):
            calls.append(instance)
            instance.body = instance.body.replace("Hello", "Cleaned")

        with self.login_user_context(self.user), patch.object(plugin_class.model, "clean", clean):
            with patch.object(plugin_class, "get_form", side_effect=AssertionError("Import must not use forms")):
                with patch.object(plugin_class.form, "__init__", side_effect=AssertionError("Import must not use forms")):
                    for browser in (True, False):
                        with self.subTest(browser=browser):
                            before = len(calls)
                            response = self.submit(self.rows, browser)
                            self.assertEqual(response.status_code, 200, response.content)
                            plugin = CMSPlugin.objects.order_by("-pk").first().get_bound_plugin()
                            self.assertEqual(plugin.body, "Cleaned World!")
                            self.assertEqual(len(calls), before + 1)

    def test_model_clean_errors_rollback_both_import_paths(self):
        model = plugin_pool.get_plugin("TextPlugin").model
        with self.login_user_context(self.user):
            for browser in (True, False):
                ids = list(CMSPlugin.objects.values_list("pk", flat=True))
                with patch.object(model, "clean", side_effect=ValidationError({"body": "Rejected by model"})):
                    response = self.submit(self.rows, browser)
                if browser:
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("Rejected by model", response.json()["error"])
                else:
                    self.assertIn("Rejected by model", str(response.context["form"].non_field_errors()))
                self.assertEqual(list(CMSPlugin.objects.values_list("pk", flat=True)), ids)

    def test_model_clean_normalizes_json_without_mutating_the_export(self):
        source = deepcopy(self.rows[0])
        source["data"]["json"] = {"attributes": None}
        original = deepcopy(source)
        model = plugin_pool.get_plugin("TextPlugin").model

        def clean(instance):
            instance.json["attributes"] = {}

        with patch.object(model, "clean", clean):
            restored = ArchivedPlugin(**source).restore(self.plugin.placeholder, "en")
        restored.refresh_from_db()
        self.assertEqual(restored.json, {"attributes": {}})
        self.assertEqual(source, original)

    def test_missing_related_objects_are_rejected_on_both_paths(self):
        section = Section.objects.create(name="Existing")
        foreign = self._create_plugin(plugin_type="RandomPlugin", title="Article", section=section)
        many = self._create_plugin(plugin_type="ArticlePlugin", title="Article")
        foreign_row = json.loads(export_plugin(foreign))[0]
        many_row = json.loads(export_plugin(many))[0]
        foreign_row["data"]["section"] = section.pk + 10000
        many_row["data"]["sections"] = [section.pk + 10000]
        invalid_foreign = deepcopy(foreign_row)
        invalid_foreign["data"]["section"] = "not-an-id"
        invalid_many = deepcopy(many_row)
        invalid_many["data"]["sections"] = ["not-an-id"]
        with self.login_user_context(self.user):
            for browser in (True, False):
                for row in (foreign_row, many_row, invalid_foreign, invalid_many):
                    with self.subTest(browser=browser, plugin=row["plugin_type"]):
                        ids = list(CMSPlugin.objects.values_list("pk", flat=True))
                        response = self.submit([row], browser)
                        if browser:
                            self.assertEqual(response.status_code, 400, response.content)
                        else:
                            self.assertTrue(response.context["form"].non_field_errors())
                        self.assertEqual(list(CMSPlugin.objects.values_list("pk", flat=True)), ids)

    def test_model_clean_relation_changes_are_persisted_on_both_paths(self):
        original = Section.objects.create(name="Original")
        replacement = Section.objects.create(name="Validated")
        plugin = self._create_plugin(plugin_type="RandomPlugin", title="Article", section=original)
        rows = json.loads(export_plugin(plugin))

        def clean(instance):
            instance.section = replacement

        with self.login_user_context(self.user), patch.object(Article, "clean", clean):
            for browser in (True, False):
                with self.subTest(browser=browser):
                    response = self.submit(rows, browser)
                    self.assertEqual(response.status_code, 200, response.content)
                    restored = CMSPlugin.objects.order_by("-pk").first().get_bound_plugin()
                    self.assertEqual(restored.section_id, replacement.pk)

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
