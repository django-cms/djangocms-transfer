from django.core.serializers import serialize

from .utils import get_local_fields, get_related_fields


class BaseTransferConfig(object):
    excluded_fields = []

    def __init__(self, model):
        self.model = model
        self.local_fields = get_local_fields(self.model)
        self.related_fields = get_related_fields(self.model)

    def get_export_fields(self):
        fields  = set(self.local_fields + self.related_fields)
        return fields.difference(set(self.excluded_fields))

    def get_export_data(self, obj):
        fields = self.get_export_fields()
        serialized = serialize('python', (obj,), fields=fields)[0]
        data = serialized.pop('fields')
        export_data = {
            'local_data': {field: data[field] for field in self.local_fields if field in data},
            'related_data': {field: data[field] for field in self.related_fields if field in data},
        }
        export_data.update(serialized)
        return export_data


class PluginTransferConfig(BaseTransferConfig):
    excluded_fields = [
        'position',
        'placeholder',
        'cmsplugin_ptr',
    ]


class GenericTransferConfig(BaseTransferConfig):
    export_exclude_fields = [
        'placeholder',
        'cmsplugin_ptr',
    ]
