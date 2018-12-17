#!/usr/bin/env python
# -*- coding: utf-8 -*-

HELPER_SETTINGS = {
    'INSTALLED_APPS': [],
    'LANGUAGE_CODE': 'en',
    'CMS_LANGUAGES': {
        1: [{
            'code': 'en',
            'name': 'English',
        }]
    },
    'ALLOWED_HOSTS': ['localhost'],
}


def run():
    from djangocms_helper import runner
    runner.cms('djangocms_transfer')


if __name__ == '__main__':
    run()
