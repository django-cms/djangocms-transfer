from django.template.loader import render_to_string
from django.test import SimpleTestCase


class CloseFrameTests(SimpleTestCase):
    def test_success_frame_contains_only_cms_success_markers(self):
        markup = render_to_string("djangocms_transfer/placeholder_close_frame.html", {})
        self.assertIn('class="cms-close-frame"', markup)
        self.assertIn('class="messagelist"', markup)
        self.assertIn('class="success"', markup)
        self.assertNotIn("<script", markup)

    def test_structure_data_is_not_rendered(self):
        data = {"plugins": [], "html": '</script><script>alert("injected")</script>'}
        markup = render_to_string("djangocms_transfer/placeholder_close_frame.html", {"structure_data": data})
        self.assertNotIn("<script", markup)
        self.assertNotIn("structure-data", markup)
