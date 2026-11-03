from collections import namedtuple
from copy import deepcopy

from django.core.exceptions import ValidationError
from django.core.serializers import deserialize
from django.core.serializers.base import DeserializationError
from django.db import transaction
from django.utils.encoding import force_str
from django.utils.functional import cached_property
from django.utils.translation import gettext as _

from cms.models import CMSPlugin

from . import custom_process_hook, get_serializer_name
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

        try:
            return list(deserialize(get_serializer_name(), [data]))[0]
        except DeserializationError as error:
            raise ValidationError(_("Invalid plugin field values: %(error)s"),
                                  params={"error": str(error)}) from error

    @transaction.atomic
    def restore(self, placeholder, language, parent=None, request=None):
        from .validation import parse_plugins

        parse_plugins([self._replace(parent_id=None)], getattr(request, "user", None))
        deserialized = deepcopy(self.deserialized_instance)
        plugin = deserialized.object

        # The destination owns CMS identity and tree fields. Imported values
        # are validated on the model before the instance is saved.
        plugin.placeholder = placeholder
        plugin.language = language
        plugin.plugin_type = self.plugin_type
        plugin.parent = parent
        plugin.position = placeholder.get_next_plugin_position(language, parent=parent, insert_order="last")
        internal_fields = {field.name for field in CMSPlugin._meta.fields}
        internal_fields.update(field.name for field in self.model._meta.fields if field.primary_key)
        plugin.full_clean(exclude=internal_fields)
        # Model.full_clean() does not validate many-to-many references on an
        # unsaved instance. Check them before inserting either side of the tree.
        for name, values in deserialized.m2m_data.items():
            field = self.model._meta.get_field(name)
            related = field.remote_field.model
            if related._default_manager.filter(pk__in=values).count() != len(set(values)):
                raise ValidationError({name: _("One or more related objects do not exist.")})
        placeholder.add_plugin(plugin)
        for name, values in deserialized.m2m_data.items():
            getattr(plugin, name).set(values)

        # customize plugin-data on import with configured function
        custom_process_hook(
            "DJANGOCMS_TRANSFER_PROCESS_IMPORT_PLUGIN_DATA",
            plugin, self.data
        )
        return plugin
