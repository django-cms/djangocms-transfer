from django import forms

from djangocms_attributes_field.fields import AttributesFormField
from entangled.forms import EntangledModelForm

from .models import LayoutPluginModel


class DeviceChoiceField(forms.MultipleChoiceField):
    """Like Frontend's optional device selector: None means all devices."""
    def prepare_value(self, value):
        return ["xs", "md"] if value is None else value

    def clean(self, value):
        value = super().clean(value)
        return None if len(value) == 2 else value


class GridForm(EntangledModelForm):
    vertical_alignment = forms.ChoiceField(choices=[("", "Default"), ("center", "Center")], required=False)
    row_cols_xs = forms.IntegerField(min_value=1, max_value=12, required=False)
    attributes = AttributesFormField(required=False)
    devices = DeviceChoiceField(choices=[("xs", "Small"), ("md", "Medium")], required=False)
    caption = forms.CharField(required=False)

    class Meta:
        model = LayoutPluginModel
        untangled_fields = ["tag_type"]
        entangled_fields = {"config": ["vertical_alignment", "row_cols_xs", "attributes", "devices", "caption"]}
        retangled_fields = {"caption": "plugin_title.title"}

    def clean_caption(self):
        return self.cleaned_data["caption"].strip()
