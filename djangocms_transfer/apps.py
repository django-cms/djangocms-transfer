from __future__ import unicode_literals

from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class TranferConfig(AppConfig):
    name = 'djangocms_transfer'
    verbose_name = _('django CMS Transfer')
