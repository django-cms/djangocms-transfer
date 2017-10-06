from cms.plugin_pool import plugin_pool

from django.utils.lru_cache import lru_cache


@lru_cache()
def get_local_fields(model):
    opts = model._meta.concrete_model._meta
    fields = opts.fields
    return [field.name for field in fields
            if not field.is_relation and not field.primary_key]


@lru_cache()
def get_related_fields(model):
    opts = model._meta.concrete_model._meta
    fields = opts._get_fields(reverse=False)
    return [field.name for field in fields if field.is_relation]


@lru_cache()
def get_plugin_class(plugin_type):
    return plugin_pool.get_plugin(plugin_type)


@lru_cache()
def get_plugin_model(plugin_type):
    return get_plugin_class(plugin_type).model
