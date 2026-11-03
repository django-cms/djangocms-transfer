import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event, current_thread
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, close_old_connections, connection
from django.test import Client, RequestFactory, TransactionTestCase, override_settings, skipUnlessDBFeature

from cms.api import add_plugin
from cms.models import CMSPlugin, Placeholder
from cms.models.placeholderpluginmodel import PlaceholderReference
from cms.utils.urlutils import admin_reverse

from djangocms_transfer.clipboard import clipboard_view
from djangocms_transfer.exporter import export_plugin
from djangocms_transfer.importer import import_plugins

from .abstract import FunctionalityBaseTestCase


class BrowserClipboardTests(FunctionalityBaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = self._create_user("clipboard", True, True)
        self.plugin = self._create_plugin()
        self.payload = {
            "format": "djangocms-transfer", "version": 1,
            "kind": "plugin", "plugins": json.loads(export_plugin(self.plugin)),
        }

    def post(self, *args):
        return self.client.post(
            admin_reverse("cms_transfer_clipboard"),
            json.dumps(args[0] if args else self.payload),
            content_type="application/json",
        )

    def test_import_export_plugin_tree(self):
        self._create_plugin(parent=self.plugin)
        self.payload["plugins"] = json.loads(export_plugin(self.plugin))
        with self.login_user_context(self.user):
            response = self.post()
            self.assertEqual(response.status_code, 200)
            clipboard = response.wsgi_request.toolbar.clipboard
            self.assertEqual(clipboard.get_plugins().count(), 2)
            root, child = list(clipboard.get_plugins())
            self.assertEqual(child.parent_id, root.pk)
            self.assertNotEqual(root.pk, self.plugin.pk)
            response = self.client.get(admin_reverse("cms_transfer_clipboard"))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["kind"], "plugin")
            self.assertEqual(response.json()["plugins"][0]["data"]["body"], self.TEXT_BODY)
            self.assertIn("no-store", response["Cache-Control"])

    def test_placeholder_uses_cms_wrapper(self):
        self.payload["kind"] = "placeholder"
        with self.login_user_context(self.user):
            response = self.post()
            self.assertEqual(response.status_code, 200)
            root = response.wsgi_request.toolbar.clipboard.get_plugins().get().get_bound_plugin()
            self.assertIsInstance(root, PlaceholderReference)
            self.assertEqual(root.placeholder_ref.get_plugins().count(), 1)
            exported = self.client.get(admin_reverse("cms_transfer_clipboard")).json()
            self.assertEqual(exported["kind"], "placeholder")
            self.assertEqual(exported["plugins"][0]["plugin_type"], "TextPlugin")

    def test_imported_content_can_be_pasted_with_cms(self):
        for kind in ("plugin", "placeholder"):
            with self.subTest(kind=kind), self.login_user_context(self.user):
                self.payload["kind"] = kind
                response = self.post()
                clipboard = response.wsgi_request.toolbar.clipboard
                root = clipboard.get_plugins().get()
                target = self.plugin.placeholder
                before = target.get_plugins().count()
                response = self.client.post(admin_reverse("cms_placeholder_move_plugin"), {
                    "plugin_id": root.pk, "placeholder_id": target.pk,
                    "target_language": "en", "target_position": before + 1,
                    "plugin_parent": "", "move_a_copy": "true",
                })
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(target.get_plugins().count(), before + 1)
                self.assertEqual(clipboard.get_plugins().count(), 1)

    def test_csrf_is_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(admin_reverse("cms_transfer_clipboard"),
                               json.dumps(self.payload), content_type="application/json")
        self.assertEqual(response.status_code, 403)

    def test_invalid_content_preserves_clipboard(self):
        with self.login_user_context(self.user):
            clipboard = self.post().wsgi_request.toolbar.clipboard
            original_ids = list(clipboard.get_plugins().values_list("pk", flat=True))
            row = self.payload["plugins"][0]
            invalid = [None, [], {}, {**self.payload, "version": 2},
                       {**self.payload, "plugins": []},
                       {**self.payload, "kind": "unknown"},
                       {**self.payload, "plugins": {}},
                       {**self.payload, "plugins": [None]},
                       {**self.payload, "plugins": [{"plugin_type": "TextPlugin"}]},
                       {**self.payload, "plugins": [row, row]},
                       {**self.payload, "plugins": [row, {**row, "pk": row["pk"] + 1}]}]
            for field, value in [("plugin_type", "MissingPlugin"), ("parent_id", 99999),
                                 ("plugin_type", []), ("plugin_type", "PluginImporter"),
                                 ("parent_id", True), ("pk", 0), ("pk", True),
                                 ("pk", []), ("data", {"placeholder_id": 42}),
                                 ("data", None), ("data", []),
                                 ("data", {"cmsplugin_ptr": 42}), ("position", "bad"),
                                 ("position", 0), ("position", True)]:
                row = {**self.payload["plugins"][0], field: value}
                invalid.append({**self.payload, "plugins": [row]})
            for payload in invalid:
                with self.subTest(payload=payload):
                    self.assertEqual(self.post(payload).status_code, 400)
                    self.assertEqual(list(clipboard.get_plugins().values_list("pk", flat=True)), original_ids)

    def test_malformed_json_preserves_clipboard(self):
        with self.login_user_context(self.user):
            clipboard = self.post().wsgi_request.toolbar.clipboard
            original_ids = list(clipboard.get_plugins().values_list("pk", flat=True))
            for raw in (b"", b"{", b"not json", b"\xff"):
                with self.subTest(raw=raw):
                    response = self.client.post(admin_reverse("cms_transfer_clipboard"),
                                                raw, content_type="application/json")
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("does not contain valid JSON", response.json()["error"])
                    self.assertEqual(list(clipboard.get_plugins().values_list("pk", flat=True)), original_ids)

    def test_validation_errors_report_the_reason_and_preserve_clipboard(self):
        with self.login_user_context(self.user):
            clipboard = self.post().wsgi_request.toolbar.clipboard
            original_ids = list(clipboard.get_plugins().values_list("pk", flat=True))
            for field, value, reason in (
                ("plugin_type", "MissingPlugin", '"MissingPlugin" is not installed'),
                ("plugin_type", "PluginImporter", 'system plugin "PluginImporter"'),
                ("parent_id", 99999, "Invalid plugin tree"),
                ("data", {"unknown_field": 42}, "Invalid plugin fields"),
            ):
                with self.subTest(reason=reason):
                    row = {**self.payload["plugins"][0], field: value}
                    response = self.post({**self.payload, "plugins": [row]})
                    self.assertEqual(response.status_code, 400)
                    self.assertIn(reason, response.json()["error"])
                    self.assertIn("Your CMS clipboard has not changed", response.json()["error"])
                    self.assertEqual(list(clipboard.get_plugins().values_list("pk", flat=True)), original_ids)

    def test_partial_import_failure_rolls_back_plugins_and_placeholder_wrapper(self):
        def fail_after_import(*args, **kwargs):
            import_plugins(*args, **kwargs)
            raise IntegrityError("Failed after creating plugins")

        with self.login_user_context(self.user):
            clipboard = self.post().wsgi_request.toolbar.clipboard
            original_ids = list(CMSPlugin.objects.values_list("pk", flat=True))
            original_placeholders = list(Placeholder.objects.values_list("pk", flat=True))
            for kind in ("plugin", "placeholder"):
                with self.subTest(kind=kind):
                    self.payload["kind"] = kind
                    with patch("djangocms_transfer.clipboard.import_plugins", side_effect=fail_after_import):
                        self.assertEqual(self.post().status_code, 400)
                    self.assertEqual(list(CMSPlugin.objects.values_list("pk", flat=True)), original_ids)
                    self.assertEqual(list(Placeholder.objects.values_list("pk", flat=True)), original_placeholders)
                    self.assertEqual(clipboard.get_plugins().get().get_bound_plugin().body, self.TEXT_BODY)

    def test_missing_clipboard_is_forbidden(self):
        request = RequestFactory().get("/clipboard/")
        request.user = self.user
        request.toolbar = SimpleNamespace(clipboard=None)
        with self.assertRaises(PermissionDenied):
            clipboard_view(request)

    def test_inactive_or_nonstaff_users_are_forbidden(self):
        for active, staff in ((False, True), (True, False), (False, False)):
            with self.subTest(active=active, staff=staff):
                request = RequestFactory().get("/clipboard/")
                request.user = SimpleNamespace(is_active=active, is_staff=staff)
                with self.assertRaises(PermissionDenied):
                    clipboard_view(request)

    def test_unsupported_http_methods_do_not_modify_clipboard(self):
        with self.login_user_context(self.user):
            clipboard = self.post().wsgi_request.toolbar.clipboard
            original_ids = list(clipboard.get_plugins().values_list("pk", flat=True))
            for method in (self.client.put, self.client.patch, self.client.delete):
                response = method(admin_reverse("cms_transfer_clipboard"),
                                  json.dumps(self.payload), content_type="application/json")
                self.assertEqual(response.status_code, 405)
                self.assertEqual(list(clipboard.get_plugins().values_list("pk", flat=True)), original_ids)

    def test_failed_restore_rolls_back_clipboard(self):
        with self.login_user_context(self.user):
            clipboard = self.post().wsgi_request.toolbar.clipboard
            original_ids = list(clipboard.get_plugins().values_list("pk", flat=True))
            with patch("djangocms_transfer.clipboard.import_plugins", side_effect=ValueError("private failure details")):
                response = self.post()
                self.assertEqual(response.status_code, 500)
                self.assertIn("failed unexpectedly", response.json()["error"])
                self.assertNotIn("private failure details", response.json()["error"])
            self.assertEqual(list(clipboard.get_plugins().values_list("pk", flat=True)), original_ids)

    def test_plugin_permission_is_required(self):
        with self.login_user_context(self.user):
            clipboard = self.post().wsgi_request.toolbar.clipboard
            original_ids = list(clipboard.get_plugins().values_list("pk", flat=True))
            with patch("djangocms_transfer.validation.has_plugin_permission", return_value=False):
                response = self.post()
                self.assertEqual(response.status_code, 403)
                self.assertIn('permission to add "TextPlugin"', response.json()["error"])
            self.assertEqual(list(clipboard.get_plugins().values_list("pk", flat=True)), original_ids)

    def test_other_users_clipboard_is_untouched(self):
        other = self._create_user("other", True, True)
        with self.login_user_context(other):
            other_clipboard = self.post().wsgi_request.toolbar.clipboard
        with self.login_user_context(self.user):
            own_clipboard = self.post().wsgi_request.toolbar.clipboard
        self.assertNotEqual(other_clipboard.pk, own_clipboard.pk)
        self.assertEqual(other_clipboard.get_plugins().count(), 1)

    def test_nonstaff_cannot_import(self):
        self.user.is_staff = False
        self.user.save()
        with self.login_user_context(self.user):
            self.assertNotEqual(self.post().status_code, 200)

    def test_get_does_not_modify_clipboard(self):
        with self.login_user_context(self.user):
            count = CMSPlugin.objects.count()
            response = self.client.get(admin_reverse("cms_transfer_clipboard"))
            self.assertEqual(response.status_code, 400)
            self.assertEqual(CMSPlugin.objects.count(), count)

    def test_setting_disables_import_and_export(self):
        with self.login_user_context(self.user):
            clipboard = self.post().wsgi_request.toolbar.clipboard
            original_ids = list(clipboard.get_plugins().values_list("pk", flat=True))
            with override_settings(DJANGOCMS_TRANSFER_BROWSER_CLIPBOARD=False):
                self.assertEqual(self.post().status_code, 404)
                self.assertEqual(self.client.get(admin_reverse("cms_transfer_clipboard")).status_code, 404)
            self.assertEqual(list(clipboard.get_plugins().values_list("pk", flat=True)), original_ids)


@skipUnlessDBFeature("has_select_for_update")
class ConcurrentBrowserClipboardTests(TransactionTestCase):
    def test_concurrent_imports_replace_instead_of_combining_trees(self):
        user = get_user_model().objects.create(username="concurrent", is_staff=True, is_superuser=True)
        clipboard = Placeholder.objects.create(slot="clipboard")
        source = Placeholder.objects.create(slot="source")
        plugin = add_plugin(source, "TextPlugin", "en", body="first import")
        payload = {
            "format": "djangocms-transfer", "version": 1, "kind": "plugin",
            "plugins": json.loads(export_plugin(plugin)),
        }
        first_import_started = Event()
        second_lock_attempted = Event()
        second_import_started = Event()
        release_first = Event()

        def delayed_import(*args, **kwargs):
            if current_thread().name.endswith("_0"):
                first_import_started.set()
                if not release_first.wait(10):
                    raise RuntimeError("Timed out waiting to finish the first import")
            else:
                second_import_started.set()
            return import_plugins(*args, **kwargs)

        def observe_lock(execute, sql, params, many, context):
            if "FOR UPDATE" in sql:
                second_lock_attempted.set()
            return execute(sql, params, many, context)

        def send_import(second=False):
            close_old_connections()
            try:
                request = RequestFactory().post("/clipboard/", json.dumps(payload), content_type="application/json")
                request.user = user
                request.toolbar = SimpleNamespace(
                    clipboard=Placeholder.objects.get(pk=clipboard.pk), request_language="en",
                )
                request.session = {}
                request._messages = FallbackStorage(request)
                request._dont_enforce_csrf_checks = True
                with connection.execute_wrapper(observe_lock if second else lambda execute, *args: execute(*args)):
                    return clipboard_view(request).status_code
            finally:
                close_old_connections()

        # Start with an empty clipboard: locking its plugins would not protect it.
        with patch("djangocms_transfer.clipboard.import_plugins", side_effect=delayed_import):
            with ThreadPoolExecutor(max_workers=2, thread_name_prefix="clipboard") as executor:
                first = executor.submit(send_import)
                try:
                    self.assertTrue(first_import_started.wait(10))
                    second = executor.submit(send_import, True)
                    self.assertTrue(second_lock_attempted.wait(10))
                    self.assertFalse(second_import_started.wait(0.2))
                finally:
                    release_first.set()
                self.assertEqual(first.result(timeout=10), 200)
                self.assertEqual(second.result(timeout=10), 200)
        self.assertTrue(second_import_started.is_set())
        self.assertEqual(clipboard.get_plugins().count(), 1)
