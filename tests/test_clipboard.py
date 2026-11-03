import json
from unittest.mock import patch

from django.test import Client, override_settings

from cms.models import CMSPlugin
from cms.models.placeholderpluginmodel import PlaceholderReference
from cms.utils.urlutils import admin_reverse

from djangocms_transfer.exporter import export_plugin

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
            invalid = [None, [], {}, {**self.payload, "version": 2},
                       {**self.payload, "plugins": []}]
            for field, value in [("plugin_type", "MissingPlugin"), ("parent_id", 99999),
                                 ("pk", []), ("data", {"placeholder_id": 42}),
                                 ("data", {"cmsplugin_ptr": 42}), ("position", "bad")]:
                row = {**self.payload["plugins"][0], field: value}
                invalid.append({**self.payload, "plugins": [row]})
            for payload in invalid:
                with self.subTest(payload=payload):
                    self.assertEqual(self.post(payload).status_code, 400)
                    self.assertEqual(list(clipboard.get_plugins().values_list("pk", flat=True)), original_ids)

    def test_failed_restore_rolls_back_clipboard(self):
        with self.login_user_context(self.user):
            clipboard = self.post().wsgi_request.toolbar.clipboard
            original_ids = list(clipboard.get_plugins().values_list("pk", flat=True))
            with patch("djangocms_transfer.clipboard.import_plugins", side_effect=ValueError):
                self.assertEqual(self.post().status_code, 400)
            self.assertEqual(list(clipboard.get_plugins().values_list("pk", flat=True)), original_ids)

    def test_plugin_permission_is_required(self):
        with self.login_user_context(self.user):
            with patch("djangocms_transfer.clipboard.has_plugin_permission", return_value=False):
                self.assertEqual(self.post().status_code, 403)

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
