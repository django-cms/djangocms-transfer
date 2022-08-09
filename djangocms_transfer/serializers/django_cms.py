import base64
import io

from django.core.files import File as DjangoFile
from django.core.serializers import base
from django.core.serializers.python import (
    Serializer as PythonSerializer,
    Deserializer as PythonDeserializer,
    _get_model,
)

try:
    from filer.fields.image import FilerImageField
    from filer.models import Image

    has_filer = True
except ImportError:
    has_filer = False


class FilerImageFieldSerializer:
    @classmethod
    def serialize(cls, field_instance):
        serializer = Serializer()
        _image_plugin_data = serializer.serialize((field_instance,))[0]
        _file_plugin_data = serializer.serialize(
            (field_instance.file_ptr,), fields=["original_filename", "mime_type"]
        )[0]
        base64_image = base64.b64encode(field_instance.file.read())

        _plugin_data = _image_plugin_data["fields"]
        _plugin_data.update(_file_plugin_data["fields"])
        _plugin_data["file_content"] = base64_image.decode()
        return _plugin_data

    @classmethod
    def deserialize(cls, serialized_data):
        base64_image = base64.b64decode(serialized_data.pop("file_content"))

        filename = serialized_data["original_filename"]
        file_obj = DjangoFile(io.BytesIO(base64_image), name=filename)
        image = Image.objects.create(
            **serialized_data,
            file=file_obj,
        )

        return image.pk


class Serializer(PythonSerializer):
    def handle_fk_field(self, obj, field):
        if has_filer and isinstance(field, FilerImageField):
            field_instance = getattr(obj, field.name)
            self._current[field.name] = FilerImageFieldSerializer.serialize(
                field_instance
            )
        else:
            super(Serializer, self).handle_fk_field(obj, field)


def Deserializer(object_list, **options):
    for d in object_list:
        # Look up the model and starting build a dict of data for it.
        try:
            Model = _get_model(d["model"])
        except base.DeserializationError:
            if options["ignorenonexistent"]:
                continue
            else:
                raise
        for (field_name, field_value) in d["fields"].items():
            field = Model._meta.get_field(field_name)
            if has_filer and isinstance(field, FilerImageField):
                value = FilerImageFieldSerializer.deserialize(field_value)
                d["fields"][field_name] = value

    yield from PythonDeserializer(object_list, **options)
