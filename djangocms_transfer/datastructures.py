from collections import namedtuple

from cms.api import add_plugin
from cms.models import CMSPlugin
from django.conf import settings
from django.core.serializers import deserialize
from django.db import transaction
from django.utils.encoding import force_str
from django.utils.functional import cached_property

from . import get_serializer_name
from .utils import get_plugin_model

BaseArchivedPlugin = namedtuple(
    "ArchivedPlugin",
    ["pk", "creation_date", "position", "plugin_type", "parent_id", "data"],
)

ArchivedPlaceholder = namedtuple("ArchivedPlaceholder", ["slot", "plugins"])


class ArchivedPlugin(BaseArchivedPlugin):
    @cached_property
    def model(self):
        return get_plugin_model(self.plugin_type)

    @cached_property
    def deserialized_instance(self):
        data = {
            "model": force_str(self.model._meta),
            "fields": self.data,
        }

        # TODO: Handle deserialization error
        return list(deserialize(get_serializer_name(), [data]))[0]

    @transaction.atomic
    def restore(self, placeholder, language, parent=None):
        m2m_data = {}
        data = self.data.copy()

        if self.model is not CMSPlugin:
            fields = self.model._meta.get_fields()
            for field in fields:
                if field.related_model is not None:
                    if field.many_to_many:
                        if data.get(field.name):
                            m2m_data[field.name] = data[field.name]
                        data.pop(field.name, None)
                    elif data.get(field.name):
                        try:
                            obj = field.related_model.objects.get(pk=data[field.name])
                        except field.related_model.DoesNotExist:
                            obj = None
                        data[field.name] = obj

        # The "data" field for LinkPlugin have key, "target"
        # which clashes with :func:add_plugin when unpacked.
        plugin_target = data.pop("target", "")

        plugin = add_plugin(
            placeholder,
            self.plugin_type,
            language,
            position="last-child",
            target=parent,
            **data,
        )

        field = ("target",) if plugin_target else ()
        # An empty *update_fields* iterable will skip the save
        plugin.target = plugin_target
        plugin.save(update_fields=field)

        if self.model is not CMSPlugin:
            fields = self.model._meta.get_fields()
            for field in fields:
                if field.related_model is not None and m2m_data.get(field.name):
                    if field.many_to_many:
                        objs = field.related_model.objects.filter(
                            pk__in=m2m_data[field.name]
                        )
                        attr = getattr(plugin, field.name)
                        attr.set(objs)

        # customize plugin-data on import with configured function
        pps = getattr(settings, "DJANGOCMS_TRANSFER_PROCESS_IMPORT_PLUGIN_DATA", None)
        if pps:
            module, function = pps.rsplit(".", 1)
            getattr(__import__(module, fromlist=[""]), function)(plugin)

        plugin.save()
        return plugin
