"""Shared validation for file and browser imports."""

import json
from copy import deepcopy

from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models
from django.utils.translation import gettext as _

from cms.models import CMSPlugin
from cms.plugin_pool import plugin_pool
from cms.utils.permissions import has_plugin_permission

from .datastructures import ArchivedPlugin
from .utils import get_plugin_fields


def parse_plugins(rows, user=None):
    if not isinstance(rows, (list, tuple)):
        raise ValidationError(_("Invalid plugin data."))
    plugins = []
    seen = set()
    for row in rows:
        if row is None:
            continue
        if isinstance(row, ArchivedPlugin):
            row = row._asdict()
        if not isinstance(row, dict) or set(row) != set(ArchivedPlugin._fields):
            raise ValidationError(_("Invalid plugin data."))
        pk, parent = row["pk"], row["parent_id"]
        if type(pk) is not int or pk <= 0 or pk in seen:
            raise ValidationError(_("Invalid plugin identifier."))
        if parent is not None and (type(parent) is not int or parent not in seen):
            raise ValidationError(_("Invalid plugin tree."))
        plugin_type = row["plugin_type"]
        if not isinstance(plugin_type, str):
            raise ValidationError(_("Invalid plugin type."))
        try:
            plugin_class = plugin_pool.get_plugin(plugin_type)
        except KeyError:
            raise ValidationError(_("The plugin type \"%(plugin_type)s\" is not installed on this site."),
                                  params={"plugin_type": plugin_type})
        if plugin_class.system:
            raise ValidationError(_("The system plugin \"%(plugin_type)s\" cannot be imported."),
                                  params={"plugin_type": plugin_type})
        if user is not None and not has_plugin_permission(user, plugin_type, "add"):
            raise PermissionDenied(_("You do not have permission to add \"%(plugin_type)s\".") %
                                   {"plugin_type": plugin_type})
        data = row["data"]
        allowed = set(get_plugin_fields(plugin_type))
        # Never accept model identity or inheritance links from another site.
        allowed -= {field.name for field in plugin_class.model._meta.fields if field.primary_key}
        if not isinstance(data, dict) or not set(data).issubset(allowed):
            raise ValidationError(_("Invalid plugin fields."))
        if type(row["position"]) is not int or row["position"] < 1:
            raise ValidationError(_("Invalid plugin position."))
        plugins.append(ArchivedPlugin(**row))
        seen.add(pk)
    return plugins


def clean_plugin_data(archived, placeholder, language, parent=None, request=None):
    """Use the plugin's ModelForm, including custom field/model cleaners."""
    plugin_class = plugin_pool.get_plugin(archived.plugin_type)
    model = plugin_class.model
    instance = model(placeholder=placeholder, language=language,
                     plugin_type=archived.plugin_type, position=1, parent=parent)
    allowed = set(get_plugin_fields(archived.plugin_type))
    allowed -= {field.name for field in model._meta.fields if field.primary_key}
    for name, value in archived.data.items():
        field = model._meta.get_field(name)
        if isinstance(field, (models.CharField, models.TextField)) and value is not None and not isinstance(value, str):
            raise ValidationError(_("%(plugin)s.%(field)s must be text."),
                                  params={"plugin": archived.plugin_type, "field": name})
        if not field.many_to_many:
            # JSON-backed forms derive their virtual fields' initial values from
            # the instance. Isolate it: form cleaners can mutate nested config.
            setattr(instance, field.attname, deepcopy(value))
    form_class = plugin_class(model, admin.site).get_form(request) if request is not None else plugin_class.form
    for name in getattr(form_class._meta, "entangled_fields", {}):
        if name in archived.data and not isinstance(archived.data[name], dict):
            raise ValidationError(_("%(plugin)s.%(field)s must be a JSON object."),
                                  params={"plugin": archived.plugin_type, "field": name})
    form = form_class(instance=instance)
    model_fields = {field.name: field for field in model._meta.get_fields()}
    form.fields = {name: field for name, field in form.fields.items()
                   if name in allowed or name not in model_fields}
    values = {}
    for name, field in form.fields.items():
        model_field = model_fields.get(name)
        value = (archived.data.get(name, model_field.get_default()) if model_field is not None
                 else form.get_initial_for_field(field, name))
        if isinstance(field.widget, forms.MultiWidget):
            if isinstance(model_field, models.JSONField) and value is not None and not isinstance(value, (dict, list)):
                raise ValidationError(_("Invalid structured plugin field value."))
            try:
                if isinstance(model_field, models.JSONField):
                    value = {} if value is None else value
                elif model_field is not None:
                    value = model_field.to_python(value)
                prepared = field.prepare_value(value)
                if not isinstance(prepared, (list, tuple)):
                    prepared = field.widget.decompress(prepared)
            except (TypeError, ValueError, OverflowError):
                raise ValidationError(_("Invalid structured plugin field value."))
            if not isinstance(prepared, (list, tuple)) or len(prepared) != len(field.widget.widgets):
                raise ValidationError(_("Invalid structured plugin field value."))
            values[name] = prepared
        else:
            prepared = field.prepare_value(value)
            values[name] = (json.dumps(prepared) if isinstance(prepared, (dict, list))
                            and isinstance(field, forms.CharField) else prepared)
        # Uploaded values aren't browser widget submissions. Bypass widget key
        # conventions (e.g. attributes_key[name]) but retain field/form cleaners.
        field.widget.value_from_datadict = lambda data, files, key: data.get(key)
        field.widget.value_omitted_from_data = lambda data, files, key: key not in data
    form.data = values
    form.is_bound = True
    if not form.is_valid():
        raise ValidationError([f"{archived.plugin_type}.{name}: {message}"
                               for name, messages in form.errors.items() for message in messages])
    cleaned = {}
    for name in allowed:
        field = model._meta.get_field(name)
        if name in form.cleaned_data:
            value = form.cleaned_data[name]
            if field.many_to_many:
                value = [item.pk for item in value]
            elif field.is_relation and value is not None:
                value = value.pk
            else:
                value = getattr(form.instance, name)
            cleaned[name] = value
        else:
            value = field.clean(archived.data.get(name, field.get_default()), form.instance)
            setattr(form.instance, field.attname, value)
            cleaned[name] = value
    internal_fields = {field.name for field in CMSPlugin._meta.fields}
    internal_fields.update(field.name for field in model._meta.fields if field.primary_key)
    form.instance.full_clean(exclude=internal_fields, validate_unique=False, validate_constraints=False)
    for name, value in cleaned.items():
        field = model._meta.get_field(name)
        if not field.is_relation:
            cleaned[name] = getattr(form.instance, name)
    return cleaned
