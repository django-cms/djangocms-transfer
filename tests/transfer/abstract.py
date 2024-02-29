from freezegun import freeze_time

from app_helper.base_test import BaseTestCase
from cms.api import add_plugin, create_page


@freeze_time("2024-02-28 00:00:00")
class FunctionalityBaseTestCase(BaseTestCase):
    def setUp(self):
        self.page = self._create_page()
        self.page.set_as_homepage()

    def _create_plugin(self, parent=None):
        return self._add_plugin_to_page(
            "TextPlugin",
            "last-child",
            parent,
            body="Hello World!",
        )

    def _create_page(self, **kwargs):
        if "template" not in kwargs:
            kwargs["template"] = "page.html"
        if "title" not in kwargs:
            kwargs["title"] = "Home"
        if "language" not in kwargs:
            kwargs["language"] = "en"
        return create_page(**kwargs)

    def _add_plugin_to_page(self, plugin_publisher, *args, page=None, **kwargs):
        if page is None:
            page = self.page
        return add_plugin(
            page.placeholders.get(slot="content"),
            plugin_publisher,
            "en",
            *args,
            **kwargs,
        )

    def _render_page(self, page=None):
        if page is None:
            page = self.page
        page.publish("en")
        response = self.client.get(page.get_absolute_url())
        return response.content.decode("utf-8")

    def _get_expected_plugin_export_data(self):
        return [
            {
                "pk": 1,
                "creation_date": "2024-02-28T00:00:00Z",
                "position": 0,
                "plugin_type": "TextPlugin",
                "parent_id": None,
                "data": {"body": "Hello World!"},
            },
        ]

    def _get_expected_placeholder_export_data(self):
        return self._get_expected_plugin_export_data()

    def _get_expected_page_export_data(self):
        return [
            {
                "placeholder": "content",
                "plugins": self._get_expected_plugin_export_data(),
            },
        ]
