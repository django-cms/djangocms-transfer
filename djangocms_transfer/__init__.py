__version__ = "2.0.0"

default_app_config = "djangocms_transfer.apps.TranferConfig"


def get_serializer_name(default="python"):
    from django.conf import settings

    return getattr(settings, "DJANGO_CMS_TRANSFER_SERIALIZER", default)


def custom_process_hook(transfer_hook, plugin, plugin_data=None):
    from importlib import import_module

    from django.conf import settings

    hook = getattr(settings, transfer_hook, None)
    if not hook:
        return plugin_data

    module, function = hook.rsplit(".", 1)
    try:
        func = getattr(import_module(module), function)
    except (ImportError, AttributeError) as e:
        raise ImportError(f"Could not import '{hook}': {e}")

    if plugin_data:
        return func(plugin, plugin_data)
    else:
        return func(plugin)
