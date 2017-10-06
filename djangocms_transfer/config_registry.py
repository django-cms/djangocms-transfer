# -*- coding: utf-8 -*-
from django.core.exceptions import ImproperlyConfigured
from django.utils.lru_cache import lru_cache

from cms.models import CMSPlugin
from cms.utils.django_load import load

from .base_config import (
    BaseTransferConfig,
    GenericTransferConfig,
    PluginTransferConfig,
)
from .exceptions import ConfigAlreadyRegistered, ConfigNotRegistered


class TransferConfigRegistry(object):

    def __init__(self):
        self.configs = {}
        self.discovered = False

    def discover(self):
        if not self.discovered:
            return
        load('cms_transfer')
        self.discovered = True

    def clear(self):
        self.discovered = False
        self.handlers = {}

    def register_config(self, model, config):
        if not issubclass(config, BaseTransferConfig):
            message = "config must be a subclass of BaseTransferConfig, %r is not."
            raise ImproperlyConfigured(message % config)

        if model in self.configs:
            message = (
                "Cannot register %r, a config with this model (%r) is already "
                "registered."
            )
            raise ConfigAlreadyRegistered(message % (config, model))

    def unregister_config(self, model):
        if model not in self.handlers:
            message = 'A config for %r has not been registered' % model
            raise ConfigNotRegistered(message)
        del self.handlers[model]

    def get_handlers(self):
        self.discover()
        return self.handlers

    @lru_cache()
    def get_config(self, model):
        try:
            cls = registry.get_config_class(model)
        except KeyError:
            plugin = issubclass(model, CMSPlugin)
            cls = PluginTransferConfig if plugin else GenericTransferConfig
        return cls(model=model)

    def get_config_class(self, model):
        """
        Retrieve a plugin from the cache.
        """
        self.discover()
        return self.configs[model]


registry = TransferConfigRegistry()
